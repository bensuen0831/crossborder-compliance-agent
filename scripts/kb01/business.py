"""Local Stage1 acceptance launcher. Never seeds legal configuration or results."""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.kb01 import rc1
from scripts.kb01.business_host import (
    create_app, native_safety, password_record, private_json, profile, verified_native_database,
)


BUSINESS = {
    "project:create", "project:read", "project:update", "project:confirm",
    "document:read", "document:upload", "document:parse", "document:unlink",
    "workflow:execute", "workflow:read", "context:read", "context:resolve",
    "classification:execute", "classification:read", "applicability:execute", "applicability:read",
    "decision:execute", "decision:read", "knowledge:read", "knowledge:retrieve", "llm:invoke",
}
AUTHOR = {"metadata:admin", "knowledge:admin"} | {
    "knowledge:document:" + x for x in ("read", "create", "write", "download", "delete", "validate", "submit-review", "archive", "bind", "ingest")
} | {"knowledge:upload:" + x for x in ("create", "read", "write", "complete", "cancel", "attach", "retry")} | {
    "knowledge:taxonomy:" + x for x in ("read", "write", "delete", "submit-review", "archive")
} | {"knowledge:batch:" + x for x in (
    "create", "read", "confirm", "cancel", "retry", "export",
    "manifest-import", "manifest-read", "manifest-export",
)} | {"knowledge:translation:read", "knowledge:translation:write",
     "knowledge:statistics:read", "knowledge:audit:read", "knowledge:acceptance:read", "knowledge:acceptance:write"}
ROLES = {
    "business": BUSINESS,
    "workflow-reviewer": (BUSINESS - {"project:create", "project:confirm"}) | {"workflow:review"},
    "knowledge-author": AUTHOR,
    "configuration-reviewer": {"metadata:admin", "metadata:review", "knowledge:admin",
                               "knowledge:document:read", "knowledge:document:approve",
                               "knowledge:taxonomy:read", "knowledge:taxonomy:approve", "knowledge:acceptance:read"},
    "configuration-publisher": {"metadata:admin", "metadata:publish", "knowledge:admin",
                                "knowledge:document:read", "knowledge:document:publish",
                                "knowledge:taxonomy:read", "knowledge:taxonomy:publish", "knowledge:acceptance:read"},
    # Provision only after actual appointment. The canonical F0 owner still
    # checks an independently approved exact expert authorization version.
    "acceptance-expert": {"metadata:admin", "metadata:review", "knowledge:acceptance:read",
                          "knowledge:acceptance:review"},
    "acceptance-publisher": {"metadata:admin", "metadata:publish", "knowledge:acceptance:read",
                             "knowledge:acceptance:publish"},
}


def save(path, data):
    temporary = path.with_suffix(".new")
    with open(temporary, "w", opener=lambda n, f: os.open(n, f, 0o600)) as file:
        json.dump(data, file, indent=2)
    os.replace(temporary, path)
    path.chmod(0o600)


def environment(root, services):
    if not (services / "private.json").is_file() or not (services / "services/service-evidence.json").is_file():
        raise ValueError("EXISTING_OWNED_SERVICES_REQUIRED")
    env = rc1.environment(services, rc1.settings(services))
    env.update(M0_LOCAL_UAT="0", KB01_LOCAL_UAT="0", VITE_M0_DEMO="false", VITE_KB01_UAT="false",
               VITE_STAGE1_ACCEPTANCE="true", VITE_SESSION_PATH="/api/v1/session",
               M0_API_TARGET="http://127.0.0.1:18011", M0_FRONTEND_URL="http://127.0.0.1:15174")
    env["BUSINESS_STATE_DIR"] = str(root)
    return env


def initialize(root, env, label):
    from cryptography.fernet import Fernet
    from crossborder_compliance.infrastructure.persistence.db import build_session_factory
    from crossborder_compliance.infrastructure.persistence.models import TenantEntity

    path = root / "accounts.json"
    if path.exists():
        raise ValueError("ACCEPTANCE_ALREADY_INITIALIZED_NO_RESET")
    engine, sf = build_session_factory(env["DATABASE_URL"])
    tenant = str(uuid4())
    with sf() as session, session.begin():
        # Offline local identity bootstrap only: no policies, laws, approvals or results.
        session.add(TenantEntity(tenant_id=tenant, name=label))
    engine.dispose()
    save(path, {"schema_version": "STAGE1_LOCAL_ACCEPTANCE_V1", "tenant_id": tenant,
                "tenant_label": label, "technical_worker_actor_id": str(uuid4()), "users": {}})
    with open(root / "secret-store.key", "xb", opener=lambda n, f: os.open(n, f, 0o600)) as key:
        key.write(Fernet.generate_key())
    print("Initialized isolated tenant; provision accounts interactively. No legal data or approvals seeded.")


def host(root, services):
    from crossborder_compliance.infrastructure.persistence.db import build_session_factory
    from crossborder_compliance.infrastructure.knowledge_binary_storage import S3KnowledgeBinaryStore
    from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore

    env = environment(root, services)
    os.environ.update(env)
    engine, sf = build_session_factory(env["DATABASE_URL"])
    key_path = root / "secret-store.key"
    if key_path.is_symlink() or key_path.stat().st_mode & 0o077:
        raise ValueError("ACCEPTANCE_SECRET_KEY_PERMISSIONS")
    key = key_path.read_bytes()
    # This is the existing encrypted credential adapter, not a second model registry.
    factory = lambda context: EncryptedFileSecretStore(root / "model-secrets", key, context.tenant_id)
    storage = S3KnowledgeBinaryStore(**private_json(root / "object-store.json"))
    tool = json.loads((services / "tool-image.json").read_text())
    database = root / "processing/scanner/official-signatures"
    if native_safety(services / "tool-image.json")["status"] == "TECHNICALLY_CLEAR":
        database = verified_native_database(root, tool["image_id"])
    app = create_app(root / "accounts.json", sf, secret_factory=factory, binary_storage=storage,
                     document_root=root / "project-documents", tool_evidence=services / "tool-image.json",
                     native_configuration={"working_root": str(root / "processing"), "image_id": tool["image_id"],
                                           "database": str(database),
                                           "database_identity": env["KB01_TEST_SCAN_IDENTITY"]})
    import uvicorn
    try:
        uvicorn.run(app, host="127.0.0.1", port=18011, access_log=False)
    finally:
        engine.dispose()


def prepare_storage(root, env):
    from crossborder_compliance.infrastructure.knowledge_binary_storage import S3KnowledgeBinaryStore
    path = root / "object-store.json"
    if not path.exists():
        config = json.loads(Path(env["KB01_TEST_S3_CONFIG"]).read_text())
        config["bucket"] = "stage1-acceptance-" + profile(root / "accounts.json")["tenant_id"]
        save(path, config)
    storage = S3KnowledgeBinaryStore(**private_json(path))
    try:
        storage.client.head_bucket(Bucket=storage.bucket)
    except storage.client.exceptions.ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
            raise
        storage.client.create_bucket(Bucket=storage.bucket)
        storage.client.put_bucket_versioning(Bucket=storage.bucket, VersioningConfiguration={"Status": "Enabled"})
    storage.client.put_bucket_cors(Bucket=storage.bucket, CORSConfiguration={"CORSRules": [{
        "AllowedOrigins": ["http://127.0.0.1:15174"], "AllowedMethods": ["PUT"],
        "AllowedHeaders": ["content-type", "x-amz-checksum-sha256"], "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 300}]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "account", "grant-project", "start", "stop", "status", "serve"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--services-state", type=Path, required=True)
    parser.add_argument("--tenant-label", default="Isolated Stage1 acceptance")
    parser.add_argument("--username")
    parser.add_argument("--role", choices=tuple(ROLES))
    parser.add_argument("--project-id", type=__import__('uuid').UUID)
    args = parser.parse_args()
    root, services = args.state_dir.resolve(), args.services_state.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    env = environment(root, services)
    try:
        if args.action == "init":
            initialize(root, env, args.tenant_label)
        elif args.action == "account":
            if not args.username or not args.role:
                raise ValueError("USERNAME_AND_ROLE_REQUIRED")
            data = profile(root / "accounts.json")
            password = getpass.getpass("Local account password (minimum16characters): ")
            if password != getpass.getpass("Repeat password: "):
                raise ValueError("PASSWORD_MISMATCH")
            actor = data["users"].get(args.username, {}).get("actor_id", str(uuid4()))
            data["users"][args.username] = {"actor_id": actor, "display_name": args.username,
                                          "role": args.role, "scopes": sorted(ROLES[args.role]),
                                          **password_record(password)}
            save(root / "accounts.json", data)
            print("Account provisioned. This does not appoint a legal expert or security Reviewer.")
        elif args.action == "grant-project":
            data = profile(root / "accounts.json")
            if not args.project_id or args.username not in data["users"]:
                raise ValueError("EXACT_PROJECT_AND_ACCOUNT_REQUIRED")
            from crossborder_compliance.infrastructure.persistence.db import build_session_factory
            from crossborder_compliance.infrastructure.persistence.models import ProjectEntity
            engine, sf = build_session_factory(env["DATABASE_URL"])
            with sf() as session:
                row = session.get(ProjectEntity, str(args.project_id))
                if not row or row.tenant_id != data["tenant_id"]:
                    raise ValueError("PROJECT_NOT_IN_ACCEPTANCE_TENANT")
            engine.dispose()
            user = data["users"][args.username]
            user["scopes"] = sorted(set(user["scopes"]) | {f"project:{args.project_id}:{x}" for x in ("comply", "classify", "read")})
            save(root / "accounts.json", data)
            print("Exact project grant saved; previous account session invalidated.")
        elif args.action == "serve":
            host(root, services)
        elif args.action == "start":
            import urllib.request
            for port in (18011, 15174):
                import socket
                with socket.socket() as sock:
                    if sock.connect_ex(("127.0.0.1", port)) == 0:
                        raise ValueError("ACCEPTANCE_PORT_IN_USE_STOP_OWN_INSTANCE_FIRST")
            profile(root / "accounts.json")
            prepare_storage(root, env)
            tool = json.loads((services / "tool-image.json").read_text())
            if native_safety(services / "tool-image.json")["status"] == "TECHNICALLY_CLEAR":
                # Download/verify trusted signatures before the HTTP startup timer.
                # Originals remain offline; no broad sandbox mount is permitted.
                rc1.run(root, env, "official-signatures", [sys.executable,
                    "scripts/kb01/official_signatures.py", "--root",
                    str(root / "processing/scanner/official-signatures"),
                    "--image", tool["image_id"], "--evidence", str(root / "official-signatures.json")])
                (root / "official-signatures.json").chmod(0o600)
                verified_native_database(root, tool["image_id"])
            rc1.spawn(root, env, "business-backend", [sys.executable, "scripts/kb01/business.py", "serve",
                      "--state-dir", str(root), "--services-state", str(services)])
            rc1.spawn(root, env, "business-frontend", ["npm", "--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1", "--port", "15174"])
            import time
            for _ in range(60):
                try:
                    for port, path in ((18011, "/health/live"), (15174, "/")):
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
                            assert response.status == 200
                    print("Business entry: http://127.0.0.1:15174/intake (executing host only). Data is retained on stop.")
                    return
                except Exception:
                    time.sleep(1)
            raise ValueError("ACCEPTANCE_HTTP_NOT_READY_INSPECT_PRIVATE_LOGS")
        elif args.action == "stop":
            rc1.stop_process(root, "business-frontend")
            rc1.stop_process(root, "business-backend")
            print("Owned business processes stopped; tenant, files, accounts and secrets preserved.")
        elif args.action == "status":
            import urllib.request
            output = {"entry": "http://127.0.0.1:15174/intake", "scope": "EXECUTING_HOST_LOOPBACK_ONLY"}
            for name, url in (("backend", "http://127.0.0.1:18011/health/live"), ("frontend", "http://127.0.0.1:15174")):
                try:
                    with urllib.request.urlopen(url, timeout=2) as response:
                        output[name] = response.status
                except Exception:
                    output[name] = "UNAVAILABLE"
            from crossborder_compliance.infrastructure.persistence.db import build_session_factory
            from sqlalchemy import text
            from redis import Redis
            try:
                engine, sf = build_session_factory(env["DATABASE_URL"])
                with sf() as session:
                    session.execute(text("SET TRANSACTION READ ONLY"))
                    assert session.execute(text("SELECT 1")).scalar_one() == 1
                engine.dispose()
                output["postgres_readonly"] = "PASS"
            except Exception:
                output["postgres_readonly"] = "UNAVAILABLE"
            try:
                client = Redis.from_url(env["REDIS_URL"])
                output["redis"] = "PASS" if client.ping() else "UNAVAILABLE"
                client.close()
            except Exception:
                output["redis"] = "UNAVAILABLE"
            print(json.dumps(output, indent=2))
    except Exception as exc:
        # Do not serialize DB URLs, credentials, provider payloads or private config.
        code = str(exc) if isinstance(exc, ValueError) and str(exc).isupper() else type(exc).__name__
        raise SystemExit("ACCEPTANCE_OPERATION_FAILED:" + code) from None


if __name__ == "__main__":
    main()
