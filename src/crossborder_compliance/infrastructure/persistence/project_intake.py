"""Intake operations for the existing PostgresProjectRepository, no new store."""

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from crossborder_compliance.application.intake_services import IntakeView
from crossborder_compliance.domain.contracts import ProjectIntakeContext, ProvenanceDTO
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    ApiIdempotencyEntity,
    OrganizationEntity,
    ProjectEntity,
    ProjectVersionEntity,
)


class IntakeConflict(ValueError):
    pass


class ProjectIntakeOperations:
    """Mixin of the canonical project adapter; immutable payloads, row-lock CAS."""

    def _intake_permission(self, operation):
        if (
            not self._context.permission.system
            and f"project:{operation}" not in self._context.permission.scopes
        ):
            raise PermissionError("intake not found")

    def _intake_project(self, s, project_id, lock=False):
        q = select(ProjectEntity).where(
            ProjectEntity.tenant_id == self.tenant_id,
            ProjectEntity.project_id == str(project_id),
            ProjectEntity.status == "ACTIVE",
        )
        row = s.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise LookupError("intake not found")
        # Current creator provenance or a current explicit project grant. No
        # browser-supplied tenant/permissions, no snapshot permission bypass.
        first = s.scalar(
            select(ProjectVersionEntity).where(
                ProjectVersionEntity.tenant_id == self.tenant_id,
                ProjectVersionEntity.project_id == row.project_id,
                ProjectVersionEntity.version_no == 1,
            )
        )
        actor = first.intake_json.get("provenance", {}).get("actor_ref") if first else None
        if not self._context.permission.system and not (
            actor == self._context.permission.actor_id
            or f"project:{project_id}:comply" in self._context.permission.scopes
        ):
            raise LookupError("intake not found")
        return row

    def _intake_current(self, s, project):
        row = self._scoped_get(
            s,
            ProjectVersionEntity,
            ProjectVersionEntity.project_version_id,
            UUID(project.active_version_id),
        )
        if row is None or row.project_id != project.project_id:
            raise LookupError("intake not found")
        return row

    def _intake_view(self, s, row):
        snapshot = s.scalar(
            select(AnalysisSnapshotEntity).where(
                AnalysisSnapshotEntity.tenant_id == self.tenant_id,
                AnalysisSnapshotEntity.project_version_id == row.project_version_id,
            )
        )
        return IntakeView(
            project_id=row.project_id,
            project_version_id=row.project_version_id,
            version=row.version_no,
            status=row.status,
            intake=ProjectIntakeContext.model_validate(row.intake_json),
            analysis_snapshot_id=snapshot.analysis_snapshot_id if snapshot else None,
            workflow_run_id=snapshot.provenance_json.get("workflow_run_id") if snapshot else None,
            retrieval_policy_id=(snapshot.provenance_json.get("formal_workflow_plan", {})
                                 .get("retrieval_query", {}).get("policy_id") if snapshot else None),
        )

    def _intake_key(self, s, operation, key, payload):
        client = sha256(
            f"{self.tenant_id}:{self._context.permission.actor_id}".encode()
        ).hexdigest()
        digest = sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        request_key = f"intake:{operation}:{key}"
        # Serialize absent-key creation as well as duplicate retries.
        s.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"{client}:{request_key}"},
        )
        existing = s.scalar(
            select(ApiIdempotencyEntity).where(
                ApiIdempotencyEntity.tenant_id == self.tenant_id,
                ApiIdempotencyEntity.api_client_id == client,
                ApiIdempotencyEntity.idempotency_key == request_key,
            )
        )
        if existing:
            if existing.request_hash != digest:
                raise IntakeConflict("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return existing, True
        record = ApiIdempotencyEntity(
            api_idempotency_id=str(uuid4()),
            tenant_id=self.tenant_id,
            api_client_id=client,
            idempotency_key=request_key,
            request_hash=digest,
        )
        s.add(record)
        return record, False

    def _intake_payload(self, facts, project, version):
        return ProjectIntakeContext(
            **facts.model_dump(),
            project_id=project.project_id,
            project_name=project.name,
            record_version=version,
            provenance=ProvenanceDTO(
                source_type="USER_INPUT",
                source_ref=str(project.project_id),
                source_version=str(version),
                actor_ref=self._context.permission.actor_id,
                generated_by="CreateProjectFromIntake",
                request_id=str(uuid4()),
            ),
        ).model_dump(mode="json")

    def create_intake(self, request):
        self._intake_permission("create")
        with self._sessions() as s, s.begin():
            key, duplicate = self._intake_key(
                s, "create", request.idempotency_key, request.model_dump(mode="json")
            )
            if duplicate:
                version = self._scoped_get(
                    s,
                    ProjectVersionEntity,
                    ProjectVersionEntity.project_version_id,
                    UUID(key.response_ref),
                )
                self._intake_project(s, UUID(version.project_id))
                return self._intake_view(s, version)
            org = self._context.user_context.organization_id
            if (
                org
                and self._scoped_get(s, OrganizationEntity, OrganizationEntity.organization_id, org)
                is None
            ):
                raise LookupError("organization not found")
            project = ProjectEntity(
                project_id=str(uuid4()),
                tenant_id=self.tenant_id,
                organization_id=str(org) if org else None,
                name=request.name.strip(),
            )
            if not project.name:
                raise ValueError("PROJECT_NAME_REQUIRED")
            s.add(project)
            s.flush()
            version = ProjectVersionEntity(
                project_version_id=str(uuid4()),
                project_id=project.project_id,
                tenant_id=self.tenant_id,
                version_no=1,
                status="DRAFT",
                intake_json=self._intake_payload(request.facts, project, 1),
            )
            s.add(version)
            s.flush()
            project.active_version_id = version.project_version_id
            key.response_ref = version.project_version_id
            return self._intake_view(s, version)

    def read_intake(self, project_id, version=None):
        self._intake_permission("read")
        with self._sessions() as s:
            project = self._intake_project(s, project_id)
            row = (
                self._intake_current(s, project)
                if version is None
                else s.scalar(
                    select(ProjectVersionEntity).where(
                        ProjectVersionEntity.tenant_id == self.tenant_id,
                        ProjectVersionEntity.project_id == str(project_id),
                        ProjectVersionEntity.version_no == version,
                    )
                )
            )
            if row is None:
                raise LookupError("intake not found")
            return self._intake_view(s, row)

    def update_intake(self, project_id, request):
        self._intake_permission("update")
        with self._sessions() as s, s.begin():
            key, duplicate = self._intake_key(
                s, f"save:{project_id}", request.idempotency_key, request.model_dump(mode="json")
            )
            project = self._intake_project(s, project_id, True)
            if duplicate:
                row = self._scoped_get(
                    s,
                    ProjectVersionEntity,
                    ProjectVersionEntity.project_version_id,
                    UUID(key.response_ref),
                )
                return self._intake_view(s, row)
            old = self._intake_current(s, project)
            if old.version_no != request.expected_version:
                raise IntakeConflict("STALE_INTAKE_VERSION")
            if old.status != "DRAFT":
                raise IntakeConflict("CONFIRMED_INTAKE_IMMUTABLE")
            old.status = "SUPERSEDED"  # payload/version provenance remains immutable
            row = ProjectVersionEntity(
                project_version_id=str(uuid4()),
                project_id=str(project_id),
                tenant_id=self.tenant_id,
                version_no=old.version_no + 1,
                status="DRAFT",
                intake_json=self._intake_payload(request.facts, project, old.version_no + 1),
            )
            s.add(row)
            s.flush()
            project.active_version_id = row.project_version_id
            project.record_version += 1
            key.response_ref = row.project_version_id
            return self._intake_view(s, row)

    def confirm_intake(self, project_id, expected_version, prepare):
        self._intake_permission("confirm")
        with self._sessions() as s, s.begin():
            # Scope-first retrieval requires REPEATABLE READ. Establish its
            # existing isolation contract before the confirmation's first read.
            s.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            project = self._intake_project(s, project_id, True)
            row = self._intake_current(s, project)
            if row.version_no != expected_version:
                raise IntakeConflict("STALE_INTAKE_VERSION")
            if row.status == "CONFIRMED":
                return self._intake_view(s, row)
            if row.status != "DRAFT":
                raise IntakeConflict("INTAKE_NOT_DRAFT")
            facts = ProjectIntakeContext.model_validate(row.intake_json)
            snapshot_id = uuid5(UUID(row.project_version_id), "analysis-snapshot")
            run_id = uuid5(snapshot_id, "canonical-workflow")
            snapshot = AnalysisSnapshotEntity(
                analysis_snapshot_id=str(snapshot_id),
                tenant_id=self.tenant_id,
                project_version_id=row.project_version_id,
                snapshot_version="1.0",
                analysis_as_of_date=facts.analysis_as_of_date,
                provenance_json={
                    **facts.provenance.model_dump(mode="json"),
                    "intake_version": row.version_no,
                    "confirmed_by": self._context.permission.actor_id,
                    "confirmed_at": datetime.now(UTC).isoformat(),
                    "workflow_run_id": str(run_id),
                },
            )
            row.status = "CONFIRMED"
            s.add(snapshot)
            s.flush()
            connection = s.connection()

            # Owning services retain their ports/transaction APIs. Each short
            # session joins this one confirmation transaction via savepoints.
            @contextmanager
            def joined_sessions():
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as child:
                    yield child

            prepare(joined_sessions, self._context, facts, snapshot_id, run_id)
            s.refresh(snapshot)
            return self._intake_view(s, row)
