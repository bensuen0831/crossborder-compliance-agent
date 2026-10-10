"""Live northbound authentication, binding and atomic gateway governance."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text

from crossborder_compliance.application.integrations import IntegrationFailure
from crossborder_compliance.domain.integrations import (
    CANONICAL_SCOPE_MAP,
    ClientCredentialView,
    ClientView,
    IntegrationPrincipal,
    IntegrationScope,
    TokenView,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationAccessTokenEntity as Token,
)
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationClientEntity as Client,
)
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationCredentialEntity as Credential,
)
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationProjectBindingEntity as Binding,
)
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationUsageCounterEntity as Counter,
)
from crossborder_compliance.infrastructure.persistence.models import (
    ApiIdempotencyEntity,
    AuditEventEntity,
    ProjectEntity,
)


def hash_credential(value):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(value.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return (
        "scrypt$16384$8$1$"
        + base64.b64encode(salt).decode()
        + "$"
        + base64.b64encode(digest).decode()
    )


def verify_credential(value, encoded):
    try:
        name, n, r, p, salt, digest = encoded.split("$")
        if name != "scrypt" or (n, r, p) != ("16384", "8", "1"):
            return False
        actual = hashlib.scrypt(
            value.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalized_hash(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str))


class PostgresIntegrationRepository:
    def __init__(self, sessions, policy, context=None):
        self.sessions, self.policy, self.admin_context = sessions, policy, context

    def _admin(self):
        if (
            not self.admin_context
            or "integration:manage" not in self.admin_context.permission.scopes
        ):
            raise IntegrationFailure("FORBIDDEN")
        return self.admin_context

    def _admin_client(self, s, identity, lock=False):
        ctx = self._admin()
        q = select(Client).where(
            Client.client_id == str(identity), Client.tenant_id == str(ctx.tenant_id)
        )
        row = s.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise IntegrationFailure("FORBIDDEN", 404)
        return row

    @staticmethod
    def _view(row):
        return ClientView(
            client_id=row.client_id,
            display_name=row.display_name,
            status=row.status,
            allowed_scopes=row.allowed_scopes_json,
            credential_type=row.credential_type,
            record_version=row.record_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_used_at=row.last_used_at,
            credential_configured=True,
        )

    def clients(self):
        ctx = self._admin()
        with self.sessions() as s:
            return tuple(
                self._view(row)
                for row in s.scalars(
                    select(Client)
                    .where(Client.tenant_id == str(ctx.tenant_id))
                    .order_by(Client.created_at)
                )
            )

    def _key(self, s, tenant, client, operation, key, payload):
        if not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise IntegrationFailure("INVALID_INPUT", 422)
        namespace = "external:" + normalized_hash([operation, key])
        identity = "integration:" + str(client)
        s.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k,0))"),
            {"k": identity + ":" + namespace},
        )
        row = s.scalar(
            select(ApiIdempotencyEntity).where(
                ApiIdempotencyEntity.tenant_id == str(tenant),
                ApiIdempotencyEntity.api_client_id == identity,
                ApiIdempotencyEntity.idempotency_key == namespace,
            )
        )
        hashed = normalized_hash(payload)
        if row:
            if row.request_hash != hashed:
                raise IntegrationFailure("IDEMPOTENCY_CONFLICT", 409)
            return row, True
        row = ApiIdempotencyEntity(
            api_idempotency_id=str(uuid4()),
            tenant_id=str(tenant),
            api_client_id=identity,
            idempotency_key=namespace,
            request_hash=hashed,
        )
        s.add(row)
        return row, False

    def _credential(self, s, row):
        cid = str(uuid4())
        raw = (
            ("sa." if row.credential_type == "SERVICE_ACCOUNT" else "cc.")
            + cid
            + "."
            + secrets.token_urlsafe(32)
        )
        cred = Credential(
            credential_id=cid,
            client_id=row.client_id,
            tenant_id=row.tenant_id,
            generation=row.credential_generation,
            credential_type=row.credential_type,
            credential_hash=hash_credential(raw),
            status="ACTIVE",
            expires_at=datetime.now(UTC)
            + timedelta(seconds=self.policy.service_account_ttl_seconds)
            if row.credential_type == "SERVICE_ACCOUNT"
            else None,
        )
        s.add(cred)
        return cred, raw

    def create_client(self, command, key):
        ctx = self._admin()
        with self.sessions() as s, s.begin():
            record, duplicate = self._key(
                s,
                ctx.tenant_id,
                ctx.permission.actor_id,
                "admin-create",
                key,
                command.model_dump(mode="json"),
            )
            if duplicate:
                cred = s.get(Credential, record.response_ref)
                return ClientCredentialView(
                    client=self._view(self._admin_client(s, cred.client_id)),
                    credential_id=cred.credential_id,
                )
            row = Client(
                client_id=str(uuid4()),
                tenant_id=str(ctx.tenant_id),
                display_name=command.display_name,
                allowed_scopes_json=list(command.allowed_scopes),
                credential_type=command.credential_type,
                credential_generation=1,
                status="ACTIVE",
                record_version=1,
                created_by=ctx.permission.actor_id,
                updated_by=ctx.permission.actor_id,
            )
            s.add(row)
            s.flush()
            cred, raw = self._credential(s, row)
            record.response_ref = cred.credential_id
            s.flush()
            return ClientCredentialView(
                client=self._view(row), credential_id=cred.credential_id, credential=raw
            )

    def update_client(self, client_id, command, key):
        ctx = self._admin()
        with self.sessions() as s, s.begin():
            record, duplicate = self._key(
                s,
                ctx.tenant_id,
                ctx.permission.actor_id,
                "admin-update:" + str(client_id),
                key,
                command.model_dump(mode="json"),
            )
            row = self._admin_client(s, client_id, True)
            if duplicate:
                return self._view(row)
            if row.record_version != command.expected_version:
                raise IntegrationFailure("VERSION_CONFLICT", 409)
            if row.status == "REVOKED" and command.status != "REVOKED":
                raise IntegrationFailure("FORBIDDEN")
            row.status = command.status
            if command.allowed_scopes is not None:
                row.allowed_scopes_json = list(command.allowed_scopes)
            row.record_version += 1
            row.updated_by = ctx.permission.actor_id
            row.updated_at = datetime.now(UTC)
            record.response_ref = row.client_id
            return self._view(row)

    def rotate_client(self, client_id, command, key):
        ctx = self._admin()
        with self.sessions() as s, s.begin():
            record, duplicate = self._key(
                s,
                ctx.tenant_id,
                ctx.permission.actor_id,
                "admin-rotate:" + str(client_id),
                key,
                command.model_dump(mode="json"),
            )
            row = self._admin_client(s, client_id, True)
            if duplicate:
                return ClientCredentialView(
                    client=self._view(row), credential_id=record.response_ref
                )
            if row.record_version != command.expected_version:
                raise IntegrationFailure("VERSION_CONFLICT", 409)
            if row.status != "ACTIVE":
                raise IntegrationFailure("FORBIDDEN")
            for cred in s.scalars(select(Credential).where(Credential.client_id == row.client_id)):
                cred.status = "REVOKED"
            row.credential_generation += 1
            row.record_version += 1
            row.updated_at = datetime.now(UTC)
            row.updated_by = ctx.permission.actor_id
            cred, raw = self._credential(s, row)
            record.response_ref = cred.credential_id
            return ClientCredentialView(
                client=self._view(row), credential_id=cred.credential_id, credential=raw
            )

    def bind_project(self, client_id, command, key):
        ctx = self._admin()
        with self.sessions() as s, s.begin():
            record, duplicate = self._key(
                s,
                ctx.tenant_id,
                ctx.permission.actor_id,
                "admin-bind:" + str(client_id),
                key,
                command.model_dump(mode="json"),
            )
            row = self._admin_client(s, client_id, True)
            project = s.get(ProjectEntity, str(command.project_id))
            if project is None or project.tenant_id != row.tenant_id:
                raise IntegrationFailure("PROJECT_ACCESS_DENIED", 404)
            if not duplicate:
                if row.record_version != command.expected_version:
                    raise IntegrationFailure("VERSION_CONFLICT", 409)
                binding = s.scalar(
                    select(Binding).where(
                        Binding.client_id == row.client_id, Binding.project_id == project.project_id
                    )
                )
                if binding is None:
                    binding = Binding(
                        binding_id=str(uuid4()),
                        tenant_id=row.tenant_id,
                        client_id=row.client_id,
                        project_id=project.project_id,
                        binding_type="EXPLICITLY_GRANTED",
                        created_by=ctx.permission.actor_id,
                        updated_by=ctx.permission.actor_id,
                    )
                    s.add(binding)
                binding.status = command.status
                row.record_version += 1
                record.response_ref = project.project_id
            return self._view(row)

    def bind_created(self, principal, project_id):
        with self.sessions() as s, s.begin():
            client = self._live(s, principal)
            project = s.get(ProjectEntity, str(project_id))
            if project is None or project.tenant_id != client.tenant_id:
                raise IntegrationFailure("PROJECT_ACCESS_DENIED", 404)
            existing = s.scalar(
                select(Binding).where(
                    Binding.client_id == client.client_id, Binding.project_id == str(project_id)
                )
            )
            if existing is None:
                s.add(
                    Binding(
                        binding_id=str(uuid4()),
                        tenant_id=client.tenant_id,
                        client_id=client.client_id,
                        project_id=str(project_id),
                        status="ACTIVE",
                        binding_type="CREATED_BY_CLIENT",
                        created_by="integration:" + client.client_id,
                        updated_by="integration:" + client.client_id,
                    )
                )
            elif existing.status != "ACTIVE":
                raise IntegrationFailure("PROJECT_ACCESS_DENIED", 404)

    def _live(self, s, principal):
        client = s.get(Client, str(principal.client_id))
        cred = s.get(Credential, str(principal.credential_id))
        now = datetime.now(UTC)
        if (
            not client
            or not cred
            or client.tenant_id != str(principal.tenant_id)
            or cred.tenant_id != client.tenant_id
            or cred.client_id != client.client_id
            or client.status != "ACTIVE"
            or cred.status != "ACTIVE"
            or cred.generation != client.credential_generation
            or (cred.expires_at is not None and cred.expires_at <= now)
        ):
            raise IntegrationFailure("UNAUTHORIZED", 401)
        return client

    def context(self, principal, required, project_id=None):
        with self.sessions() as s:
            client = self._live(s, principal)
            active = set(principal.scopes) & set(client.allowed_scopes_json)
            if required not in active:
                raise IntegrationFailure("INVALID_SCOPE")
            grants = set().union(
                *(CANONICAL_SCOPE_MAP[IntegrationScope(scope)] for scope in active)
            )
            if project_id is not None:
                binding = s.scalar(
                    select(Binding).where(
                        Binding.client_id == client.client_id,
                        Binding.tenant_id == client.tenant_id,
                        Binding.project_id == str(project_id),
                        Binding.status == "ACTIVE",
                    )
                )
                project = s.get(ProjectEntity, str(project_id))
                if (
                    not binding
                    or not project
                    or project.tenant_id != client.tenant_id
                    or project.status != "ACTIVE"
                ):
                    raise IntegrationFailure("PROJECT_ACCESS_DENIED", 404)
                grants |= {
                    f"project:{project_id}:read",
                    f"project:{project_id}:comply",
                    f"project:{project_id}:classify",
                }
            return RepositoryContext.user(
                UUID(client.tenant_id), "integration:" + client.client_id, grants
            )

    def token(self, command):
        self.consume_auth(command.client_id)
        with self.sessions() as s, s.begin():
            client = s.get(Client, str(command.client_id))
            cred = None
            if client:
                cred = s.scalar(
                    select(Credential).where(
                        Credential.client_id == client.client_id,
                        Credential.credential_type == "OAUTH2",
                        Credential.status == "ACTIVE",
                        Credential.generation == client.credential_generation,
                    )
                )
            # Unknown identities still perform the expensive one-way primitive.
            encoded = cred.credential_hash if cred else hash_credential("unusable")
            valid = verify_credential(command.client_secret.get_secret_value(), encoded)
            if (
                not valid
                or not client
                or not cred
                or client.status != "ACTIVE"
                or (cred.expires_at is not None and cred.expires_at <= datetime.now(UTC))
            ):
                raise IntegrationFailure("UNAUTHORIZED", 401)
            granted = (
                set(command.scope.split())
                if command.scope is not None
                else set(client.allowed_scopes_json)
            )
            if not granted or not granted <= set(client.allowed_scopes_json):
                raise IntegrationFailure("INVALID_SCOPE")
            raw = secrets.token_urlsafe(48)
            s.add(
                Token(
                    token_digest=digest(raw),
                    client_id=client.client_id,
                    tenant_id=client.tenant_id,
                    credential_id=cred.credential_id,
                    scopes_json=sorted(granted),
                    expires_at=datetime.now(UTC) + timedelta(seconds=self.policy.token_ttl_seconds),
                )
            )
            client.last_used_at = datetime.now(UTC)
            return TokenView(
                access_token=raw,
                expires_in=self.policy.token_ttl_seconds,
                scope=" ".join(sorted(granted)),
            )

    def authenticate(self, bearer):
        if not isinstance(bearer, str) or not 1 <= len(bearer) <= 512:
            raise IntegrationFailure("UNAUTHORIZED", 401)
        with self.sessions() as s, s.begin():
            if bearer.startswith("sa."):
                try:
                    identity = str(UUID(bearer.split(".")[1]))
                except (ValueError, IndexError):
                    raise IntegrationFailure("UNAUTHORIZED", 401) from None
                cred = s.get(Credential, identity)
                if (
                    not cred
                    or cred.credential_type != "SERVICE_ACCOUNT"
                    or not verify_credential(bearer, cred.credential_hash)
                ):
                    raise IntegrationFailure("UNAUTHORIZED", 401)
                client = s.get(Client, cred.client_id)
                scopes = client.allowed_scopes_json if client else []
                principal = IntegrationPrincipal(
                    client_id=cred.client_id,
                    tenant_id=cred.tenant_id,
                    credential_id=cred.credential_id,
                    scopes=scopes,
                )
            else:
                row = s.get(Token, digest(bearer))
                if not row or row.expires_at <= datetime.now(UTC):
                    raise IntegrationFailure("UNAUTHORIZED", 401)
                principal = IntegrationPrincipal(
                    client_id=row.client_id,
                    tenant_id=row.tenant_id,
                    credential_id=row.credential_id,
                    scopes=row.scopes_json,
                )
            self._live(s, principal).last_used_at = datetime.now(UTC)
            return principal

    def consume(self, principal, endpoint_class):
        """Both dimensions atomically committed, including denied-attempt accounting."""
        failure = None
        with self.sessions() as s, s.begin():
            client = self._live(s, principal)
            now = int(datetime.now(UTC).timestamp())
            rate_window = now // self.policy.rate_window_seconds * self.policy.rate_window_seconds
            quota_window = (
                now // self.policy.quota_window_seconds * self.policy.quota_window_seconds
            )
            counters = [
                (
                    f"rate:tenant:{client.tenant_id}:{endpoint_class}",
                    rate_window,
                    self.policy.tenant_rate_limit,
                    "RATE_LIMITED",
                    self.policy.rate_window_seconds,
                ),
                (
                    f"rate:client:{client.client_id}:{endpoint_class}",
                    rate_window,
                    self.policy.client_rate_limits.get(endpoint_class, 1),
                    "RATE_LIMITED",
                    self.policy.rate_window_seconds,
                ),
                (
                    f"quota:client:{client.client_id}:requests",
                    quota_window,
                    self.policy.client_quotas["requests"],
                    "QUOTA_EXCEEDED",
                    self.policy.quota_window_seconds,
                ),
            ]
            if endpoint_class in {"start", "upload"}:
                counters.append(
                    (
                        f"quota:client:{client.client_id}:{endpoint_class}",
                        quota_window,
                        self.policy.client_quotas[endpoint_class],
                        "QUOTA_EXCEEDED",
                        self.policy.quota_window_seconds,
                    )
                )
            failure = self._consume_counters(s, client.tenant_id, counters, now)
        if failure:
            raise failure

    @staticmethod
    def _consume_counters(s, tenant, counters, now):
        failure = None
        for key, window, maximum, code, seconds in sorted(counters):
            s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k,0))"), {"k": key})
            row = s.get(Counter, (key, window))
            if row is None:
                row = Counter(counter_key=key, tenant_id=tenant, window_start=window, value=0)
                s.add(row)
            row.value += 1
            if row.value > maximum and failure is None:
                failure = IntegrationFailure(
                    code, 429, retryable=True, retry_after=window + seconds - now
                )
        return failure

    def consume_auth(self, client_id):
        # Persist failed attempts too; unknown UUIDs share one bounded bucket,
        # rather than allowing attacker-controlled counter cardinality.
        with self.sessions() as s, s.begin():
            client = s.get(Client, str(client_id))
            tenant = client.tenant_id if client else str(UUID(int=0))
            identity = client.client_id if client else "unknown"
            now = int(datetime.now(UTC).timestamp())
            seconds = self.policy.rate_window_seconds
            window = now // seconds * seconds
            failure = self._consume_counters(
                s,
                tenant,
                [
                    (
                        f"rate:tenant:{tenant}:auth",
                        window,
                        self.policy.tenant_rate_limit,
                        "RATE_LIMITED",
                        seconds,
                    ),
                    (
                        f"rate:client:{identity}:auth",
                        window,
                        self.policy.client_rate_limits.get("auth", 30),
                        "RATE_LIMITED",
                        seconds,
                    ),
                ],
                now,
            )
        if failure:
            raise failure

    def project_bindings(self, client_id):
        from crossborder_compliance.domain.integrations import ProjectBindingView

        with self.sessions() as s:
            client = self._admin_client(s, client_id)
            return tuple(
                ProjectBindingView(
                    project_id=r.project_id, binding_type=r.binding_type, status=r.status
                )
                for r in s.scalars(
                    select(Binding)
                    .where(
                        Binding.client_id == client.client_id, Binding.tenant_id == client.tenant_id
                    )
                    .order_by(Binding.project_id)
                )
            )

    def audit(
        self,
        principal,
        operation,
        correlation_id,
        outcome,
        error_code=None,
        project_id=None,
        run_id=None,
        snapshot_id=None,
        scope=None,
        claimed_client_id=None,
    ):
        with self.sessions() as s, s.begin():
            ctx = self.admin_context
            tenant = (
                str(principal.tenant_id if principal else ctx.tenant_id)
                if principal or ctx
                else str(UUID(int=0))
            )
            actor = (
                "integration:" + str(principal.client_id)
                if principal
                else (ctx.permission.actor_id if ctx else "unauthenticated")
            )
            claimed = (
                s.get(Client, str(claimed_client_id))
                if claimed_client_id and not principal and not ctx
                else None
            )
            if claimed is not None:
                tenant = claimed.tenant_id
            s.add(
                AuditEventEntity(
                    audit_event_id=str(uuid4()),
                    tenant_id=tenant,
                    workflow_run_id=str(run_id or ""),
                    analysis_snapshot_id=str(snapshot_id or ""),
                    event_type="EXTERNAL_OPERATION",
                    provenance_json={
                        "integration_client_id": str(principal.client_id)
                        if principal
                        else (claimed.client_id if claimed else None),
                        "authentication_verified": principal is not None,
                        "actor_id": actor,
                        "project_id": str(project_id) if project_id else None,
                        "operation": operation,
                        "scope": scope,
                        "correlation_id": correlation_id,
                        "outcome": outcome,
                        "error_code": error_code,
                    },
                )
            )
