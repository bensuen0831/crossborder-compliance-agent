"""Isolated acceptance composition of canonical routes, not the synthetic UAT host.

No fixture imports, legal seeds, dependency overrides or default system identity.
Account provisioning is an offline local operator action. It does not appoint a
legal expert or constitute formal security approval.
"""

import hashlib
import hmac
import json
import secrets
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from crossborder_compliance.domain.security import RepositoryContext


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256, repr=False)


def password_record(password):
    if len(password) < 16:
        raise ValueError("ACCEPTANCE_PASSWORD_MINIMUM_16_CHARACTERS")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000)
    return {"salt": salt, "password_hash": digest.hex()}


def private_json(path):
    path = Path(path)
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("ACCEPTANCE_PRIVATE_FILE_REQUIRED")
    if path.stat().st_mode & 0o077 or path.stat().st_size > 128 * 1024:
        raise ValueError("ACCEPTANCE_PRIVATE_FILE_PERMISSIONS")
    return json.loads(path.read_text())


def profile(path):
    value = private_json(path)
    if value.get("schema_version") != "STAGE1_LOCAL_ACCEPTANCE_V1":
        raise ValueError("ACCEPTANCE_PROFILE_VERSION")
    UUID(value["tenant_id"])
    UUID(value["technical_worker_actor_id"])
    if not isinstance(value.get("users"), dict) or len(value["users"]) > 100:
        raise ValueError("ACCEPTANCE_PROFILE_USERS")
    for name, user in value["users"].items():
        if not name or not user["actor_id"] or "system" in user["scopes"]:
            raise ValueError("ACCEPTANCE_PROFILE_AUTHORITY")
        if len(user["scopes"]) > 1000 or not all(isinstance(s, str) for s in user["scopes"]):
            raise ValueError("ACCEPTANCE_PROFILE_SCOPES")
        if len(bytes.fromhex(user["salt"])) != 16 or len(bytes.fromhex(user["password_hash"])) != 32:
            raise ValueError("ACCEPTANCE_PASSWORD_RECORD")
    return value


def native_safety(tool_path):
    """A scan result is not approval. Unsafe tools never process real uploads."""
    if not tool_path:
        return {"status": "BLOCKED", "reason": "NATIVE_TOOL_EVIDENCE_REQUIRED"}
    try:
        tool = json.loads(Path(tool_path).read_text())
        provenance_path = Path(tool["provenance_path"])
        provenance = json.loads(provenance_path.read_text())
        report_path = provenance_path.parent / "vulnerabilities.json"
        raw = report_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != provenance["security"]["report_sha256"]:
            raise ValueError("scan hash")
        if provenance["oci"]["config_digest"] != tool["image_id"]:
            raise ValueError("image identity")
        report = json.loads(raw)
        counts = {severity: sum(v.get("Severity") == severity for r in report["Results"]
                               for v in r.get("Vulnerabilities", []))
                  for severity in ("HIGH", "CRITICAL")}
        from scripts.kb01.rc1 import validate_tool_sources
        validate_tool_sources(tool)
        for relative, digest in tool["source_sha256"].items():
            source = Path(__file__).resolve().parents[2] / "src/crossborder_compliance" / relative
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError("parser source")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(report["CreatedAt"].replace("Z", "+00:00"))).total_seconds()
        clear = not any(counts.values()) and 0 <= age <= 86400
        return {"status": "TECHNICALLY_CLEAR" if clear else "BLOCKED",
                "reason": "ZERO_HIGH_CRITICAL_FRESH_SCAN" if clear else "APPLICABLE_SECURITY_DECISION_OR_SUPPORTED_FIX_REQUIRED",
                "image_id": tool["image_id"], "scan_sha256": hashlib.sha256(raw).hexdigest(),
                "counts": counts, "formal_security_acceptance": "PENDING"}
    except (OSError, KeyError, ValueError, TypeError, RuntimeError):
        return {"status": "BLOCKED", "reason": "NATIVE_TOOL_EVIDENCE_INVALID"}


def verified_native_database(root, image_id):
    """Read exact installer-verified CVDs inside the existing scanner boundary."""
    root = Path(root)
    proof = private_json(root / "official-signatures.json")
    names = {"main.cvd", "daily.cvd", "bytecode.cvd"}
    if (proof.get("signature_verification") != "PASS" or proof.get("image_id") != image_id
            or set(proof.get("files", {})) != names):
        raise ValueError("ACCEPTANCE_OFFICIAL_DATABASE_PROVENANCE_REQUIRED")
    database = root / "processing/scanner/official-signatures"
    for name in names:
        path = database / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("ACCEPTANCE_OFFICIAL_DATABASE_PROVENANCE_REQUIRED")
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if path.stat().st_size != proof["files"][name]["bytes"] or digest != proof["files"][name]["sha256"]:
            raise ValueError("ACCEPTANCE_OFFICIAL_DATABASE_CHANGED")
    return database


def install_sessions(app, path, *, api_port, frontend_port):
    """Thin local authentication adapter; current profile owns all grants."""
    sessions = {}
    attempts = {}
    origins = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")
               for port in (api_port, frontend_port)}
    hosts = {origin.removeprefix("http://") for origin in origins}

    def current(request):
        token = request.cookies.get("stage1_acceptance_session")
        entry = sessions.get(token)
        users = profile(path)
        if not entry or time.monotonic() >= entry["expires"]:
            raise HTTPException(401, "ACCEPTANCE_LOGIN_REQUIRED")
        user = users["users"].get(entry["username"])
        fingerprint = hashlib.sha256(json.dumps(user, sort_keys=True).encode()).hexdigest()
        if not user or entry["fingerprint"] != fingerprint or entry["tenant"] != users["tenant_id"]:
            sessions.pop(token, None)
            raise HTTPException(401, "ACCEPTANCE_SESSION_CHANGED")
        return entry, users, user

    def presentation(entry, config, user):
        scopes = user["scopes"]
        result = {"identity_key": entry["identity"], "display_name": user["display_name"],
                  "tenant_label": config["tenant_label"], "organization_label": None,
                  "department_label": None, "permissions": scopes, "contexts": [], "demo": False}
        if "metadata:admin" in scopes or any(s.startswith("knowledge:") for s in scopes):
            grants = {}
            if "metadata:admin" in scopes:
                from crossborder_compliance.interfaces.api.routes.admin_metadata import _ALL_RESOURCES
                for resource in _ALL_RESOURCES:
                    grants[resource] = ["VIEW", "EDIT"]
                    if "metadata:review" in scopes:
                        grants[resource].extend(["REVIEW", "APPROVE"])
                    if "metadata:publish" in scopes:
                        grants[resource].append("PUBLISH")
            result["admin_context"] = {"actorId": user["actor_id"], "tenantId": config["tenant_id"],
                                       "roles": [user["role"]], "backendScopes": scopes, "grants": grants}
        return result

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if (not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}
                or request.headers.get("host") not in hosts
                or (request.headers.get("origin") and request.headers["origin"] not in origins)):
            return Response(status_code=403)
        try:
            _, config, user = current(request)
            request.state.repository_context = RepositoryContext.user(
                UUID(config["tenant_id"]), user["actor_id"], set(user["scopes"]))
        except HTTPException:
            pass
        except (OSError, ValueError, KeyError, TypeError):
            return JSONResponse(status_code=503, content={"detail": "ACCEPTANCE_IDENTITY_CONFIGURATION_UNAVAILABLE"},
                                headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                 "Referrer-Policy": "no-referrer"})
        return response

    @app.post("/api/v1/login")
    def login(body: Login, request: Request, response: Response):
        # No request field may supply tenant, actor, role, grant or approval.
        now = time.monotonic()
        for name, timestamps in list(attempts.items()):
            fresh = [t for t in timestamps if now - t < 60]
            if fresh:
                attempts[name] = fresh
            else:
                attempts.pop(name, None)
        if len(attempts.get(body.username, [])) >= 5 or (body.username not in attempts and len(attempts) >= 1000):
            raise HTTPException(429, "ACCEPTANCE_LOGIN_RATE_LIMIT")
        attempts.setdefault(body.username, []).append(now)
        config = profile(path)
        user = config["users"].get(body.username)
        salt = bytes.fromhex(user["salt"]) if user else bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", body.password.encode(), salt, 310_000).hex()
        if not user or not hmac.compare_digest(digest, user["password_hash"]):
            raise HTTPException(401, "ACCEPTANCE_LOGIN_FAILED")
        old = request.cookies.get("stage1_acceptance_session")
        sessions.pop(old, None)
        for expired in [key for key, value in sessions.items() if now >= value["expires"]]:
            sessions.pop(expired, None)
        token = secrets.token_urlsafe(32)
        entry = {"username": body.username, "tenant": config["tenant_id"],
                 "fingerprint": hashlib.sha256(json.dumps(user, sort_keys=True).encode()).hexdigest(),
                 "identity": secrets.token_hex(16), "expires": now + 3600}
        sessions[token] = entry
        response.set_cookie("stage1_acceptance_session", token, httponly=True, samesite="strict", max_age=3600)
        return presentation(entry, config, user)

    @app.get("/api/v1/session")
    def session(request: Request):
        return presentation(*current(request))

    @app.post("/api/v1/logout")
    def logout(request: Request, response: Response):
        sessions.pop(request.cookies.get("stage1_acceptance_session"), None)
        response.delete_cookie("stage1_acceptance_session")
        return {"status": "signed_out"}


def create_app(path, sessions_factory, *, secret_factory, binary_storage=None, document_root=None,
               tool_evidence=None, native_configuration=None, api_port=18011, frontend_port=15174):
    from crossborder_compliance.interfaces.api import main as baseline
    # Importing this module composes the existing intake/workflow/review/external routers.
    from crossborder_compliance.interfaces.api.workflow_app import app as canonical
    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
    from crossborder_compliance.infrastructure.persistence import metadata_models as m

    config = profile(path)
    app = FastAPI(title="Stage1 isolated business acceptance", lifespan=baseline.lifespan)
    app.include_router(canonical.router)
    app.state.knowledge_session_factory = sessions_factory
    app.state.llm_secret_store_factory = secret_factory
    app.state.knowledge_binary_store = binary_storage
    if document_root:
        app.state.document_object_storage = FileObjectStorageAdapter(str(document_root))
    # No clean scanner, permissive file policy, seeded plans or native-parser bypass.
    # Multipart originals may remain quarantined in the canonical upload store;
    # a real security-cleared scanner is required before attach/parse/publication.
    app.state.knowledge_management_worker = None
    app.state.document_file_policy = None
    tool_safety = native_safety(tool_evidence)
    if tool_safety["status"] == "TECHNICALLY_CLEAR" and native_configuration:
        if native_configuration["image_id"] != tool_safety["image_id"]:
            raise ValueError("ACCEPTANCE_NATIVE_IMAGE_IDENTITY_MISMATCH")
        install_native_pipeline(app, sessions_factory, path, binary_storage, native_configuration, tool_evidence)
    install_sessions(app, path, api_port=api_port, frontend_port=frontend_port)

    @app.exception_handler(RequestValidationError)
    async def protected_validation(_request, _error):
        return JSONResponse(status_code=422, content={"detail": "ACCEPTANCE_REQUEST_INVALID"})

    @app.get("/api/v1/acceptance-readiness")
    def readiness(case_version_id: UUID | None = None, gold_review_version_id: UUID | None = None,
                  context: RepositoryContext = Depends(get_repository_context)):
        with sessions_factory() as s:
            tenant = str(context.tenant_id)
            provider_count = s.scalar(select(func.count()).select_from(m.ModelProviderEntity).where(
                m.ModelProviderEntity.tenant_id == tenant, m.ModelProviderEntity.enabled.is_(True)))
            deployment_count = s.scalar(select(func.count()).select_from(m.ModelDeploymentEntity).where(
                m.ModelDeploymentEntity.tenant_id == tenant, m.ModelDeploymentEntity.enabled.is_(True),
                m.ModelDeploymentEntity.lifecycle_status == "ACTIVE"))
        legal = None
        if case_version_id is not None:
            from crossborder_compliance.infrastructure.persistence.regulatory_acceptance import PostgresRegulatoryAcceptance
            legal = PostgresRegulatoryAcceptance(sessions_factory, context).readiness(case_version_id, gold_review_version_id)
        legal_ready = bool(legal and legal["dataset_kind"] == "L2_REAL_REGULATORY" and
                           legal["decision"] == "READY_FOR_INDEPENDENT_ACCEPTANCE")
        return {"scope": "LOCAL_ISOLATED_ACCEPTANCE_ONLY", "entry": "OPERABLE",
                "business_ui_e2e": "BLOCKED", "real_regulatory_data": "BLOCKED",
                "live_model_workflow": "BLOCKED_UNTIL_MEASURED_BUSINESS_INVOCATION",
                "legal_gold_and_criteria": "READY" if legal_ready else "BLOCKED",
                "canonical_legal_readiness": legal,
                "legal_accuracy_execution": "NOT_EXECUTED", "user_e2e_test_readiness": "BLOCKED",
                "model_configuration": {"providers": provider_count, "active_deployments": deployment_count,
                                        "health_check_is_not_workflow_evidence": True},
                "native_processing": native_safety(tool_evidence),
                "required_actions": ["CONFIGURE_AUTHORIZED_API_PROVIDER", "UPLOAD_VERIFY_PUBLISH_REAL_LAW",
                                     "PROVIDE_INDEPENDENT_APPROVED_GOLD", "SECURITY_CLEAR_NATIVE_PROCESSING"],
                "stage2_started": False}

    assert not app.dependency_overrides
    assert config["tenant_id"]
    return app


def install_native_pipeline(app, sessions_factory, account_path, storage, config, tool_evidence):
    """Wire the existing real ports only after the tool preflight is clear."""
    import tempfile
    from crossborder_compliance.application.document_upload import DocumentFilePolicy, FileTypePolicy
    from crossborder_compliance.infrastructure.knowledge_process_sandbox import ClamKnowledgeScanner, KnowledgeProcessSandbox
    from crossborder_compliance.infrastructure.knowledge_archive_extractor import IsolatedKnowledgeArchiveExtractor
    from crossborder_compliance.infrastructure.knowledge_native_parser import IsolatedNativeDocumentParser
    from crossborder_compliance.infrastructure.knowledge_management_worker import KnowledgeManagementWorker

    root = Path(config["working_root"])
    sandbox = KnowledgeProcessSandbox(config["image_id"], root / "scanner")
    scanner = ClamKnowledgeScanner(sandbox, Path(config["database"]), config["database_identity"])
    extractor = IsolatedKnowledgeArchiveExtractor(KnowledgeProcessSandbox(config["image_id"], root / "archive"))
    parser = IsolatedNativeDocumentParser(KnowledgeProcessSandbox(config["image_id"], root / "native"))
    worker_scopes = {"knowledge:upload:" + x for x in ("create", "read", "write", "complete", "work", "cancel")}
    worker_scopes |= {"knowledge:batch:work", "knowledge:document:ingest"}

    def require_current_tools():
        current = native_safety(tool_evidence)
        if current["status"] != "TECHNICALLY_CLEAR" or current["image_id"] != config["image_id"]:
            raise PermissionError("ACCEPTANCE_NATIVE_PROCESSING_HELD")

    def current_contexts():
        # Recheck every worker cycle; an expired/replaced report cannot keep
        # native processing enabled merely because startup previously passed.
        require_current_tools()
        account = profile(account_path)
        return [RepositoryContext.user(UUID(account["tenant_id"]), account["technical_worker_actor_id"], worker_scopes)]

    class ProjectScanner:
        def scan(self, *, content, filename):
            require_current_tools()
            # Only bounded non-sensitive TXT is enabled for the first business case.
            with tempfile.TemporaryDirectory(dir=sandbox.working_root) as directory:
                Path(directory).chmod(0o755)
                target = Path(directory) / "original"
                target.write_bytes(content)
                target.chmod(0o644)
                return scanner.scan(target, 120, max_expanded_bytes=8 * 1024**2, max_entries=100,
                                    memory_bytes=2 * 1024**3)["clean"]

    app.state.knowledge_management_worker = KnowledgeManagementWorker(
        sessions_factory, storage, scanner, sandbox, extractor, parser, current_contexts, root / "jobs")
    app.state.document_file_policy = DocumentFilePolicy(
        version="stage1-first-case-text-v1", max_size_bytes=1024**2,
        allowed_types=(FileTypePolicy(extension=".txt", media_type="text/plain", signature="text"),),
        scan_required=True)
    app.state.document_malware_scanner = ProjectScanner()
