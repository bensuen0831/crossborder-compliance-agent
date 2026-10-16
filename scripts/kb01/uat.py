"""Loopback-only technical KB acceptance host; never a production identity service.

Reuses the existing trusted UAT session and canonical routers/workers. Synthetic
personas and policy publication are explicit, and no formal legal result is seeded
for these management journeys. No dependency override grants browser authority.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]


def seed(path):
    from test_kb01_taxonomy_postgres import deletion_policy

    from crossborder_compliance.config import get_settings
    from crossborder_compliance.infrastructure.persistence.db import build_session_factory
    from scripts.m0_preview.seed import seed_persona

    people = {name: seed_persona(name) for name in ("A", "B")}
    sf = build_session_factory(get_settings().database_url)[1]
    author = {
        "knowledge:document:" + name
        for name in (
            "read",
            "create",
            "write",
            "download",
            "delete",
            "validate",
            "submit-review",
            "archive",
            "bind",
            "ingest",
        )
    } | {
        "knowledge:upload:" + name
        for name in ("create", "read", "write", "complete", "cancel", "retry")
    }
    author |= {
        "knowledge:batch:" + name
        for name in ("create", "read", "confirm", "cancel", "retry", "export")
    }
    author |= {
        "knowledge:taxonomy:" + name
        for name in ("read", "write", "delete", "submit-review", "archive")
    }
    author |= {"knowledge:upload:attach", "knowledge:statistics:read", "knowledge:audit:read"}
    author |= {"knowledge:translation:read", "knowledge:translation:write"}
    author |= {
        "knowledge:batch:manifest-import",
        "knowledge:batch:manifest-read",
        "knowledge:batch:manifest-export",
    }
    for name in ("A", "B"):
        deletion_policy(
            (sf, UUID(people[name]["tenant_id"]), None, None),
            scanner_memory_bytes=4 * 1024**3,
        )
        people[name]["permissions"] = sorted(set(people[name]["permissions"]) | author)
    for name, permissions in (
        (
            "REVIEWER",
            {
                "knowledge:document:read",
                "knowledge:document:approve",
                "knowledge:taxonomy:read",
                "knowledge:taxonomy:approve",
                "knowledge:translation:read",
                "knowledge:translation:approve",
                "knowledge:admin",
            },
        ),
        (
            "PUBLISHER",
            {
                "knowledge:document:read",
                "knowledge:document:publish",
                "knowledge:taxonomy:read",
                "knowledge:taxonomy:publish",
                "knowledge:admin",
            },
        ),
    ):
        people[name] = {
            **people["A"],
            "actor_id": "synthetic-kb-" + name.lower(),
            "display_name": "SYNTHETIC_GOVERNED_TEST_DATA " + name,
            "permissions": sorted(permissions),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(people, indent=2) + "\n")
    path.chmod(0o600)


def upload_browser_origin():
    """Only a concrete loopback origin may configure this synthetic UAT bucket."""
    origin = os.environ.get("M0_FRONTEND_URL", "http://127.0.0.1:15173")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.port is None
    ):
        raise ValueError("KB01_UAT_REQUIRES_EXACT_LOOPBACK_ORIGIN")
    return origin


def host(path):
    from crossborder_compliance.config import get_settings
    from crossborder_compliance.domain.security import RepositoryContext
    from crossborder_compliance.infrastructure.knowledge_archive_extractor import (
        IsolatedKnowledgeArchiveExtractor,
    )
    from crossborder_compliance.infrastructure.knowledge_binary_storage import (
        S3KnowledgeBinaryStore,
    )
    from crossborder_compliance.infrastructure.knowledge_management_worker import (
        KnowledgeManagementWorker,
    )
    from crossborder_compliance.infrastructure.knowledge_native_parser import (
        IsolatedNativeDocumentParser,
    )
    from crossborder_compliance.infrastructure.knowledge_process_sandbox import (
        ClamKnowledgeScanner,
        KnowledgeProcessSandbox,
    )
    from crossborder_compliance.infrastructure.persistence.db import build_session_factory
    from crossborder_compliance.interfaces.api import main
    from scripts.m0_preview.server import create_demo_app

    app = create_demo_app(path)
    previous = len(app.router.routes)
    for router in (
        main.knowledge_management_router,
        main.knowledge_manifests_router,
        main.knowledge_translation_alignment_router,
        main.regulatory_acceptance_router,
        main.knowledge_document_management_router,
        main.knowledge_upload_router,
        main.knowledge_batch_router,
        main.knowledge_binary_ingestion_router,
        main.knowledge_statistics_router,
    ):
        app.include_router(router)
    # Match production: specific management routes precede generic admin routes.
    app.router.routes = app.router.routes[previous:] + app.router.routes[:previous]
    sf = build_session_factory(get_settings().database_url)[1]
    storage = S3KnowledgeBinaryStore(
        **json.loads(Path(os.environ["KB01_TEST_S3_CONFIG"]).read_text())
    )
    # Exact allowed browser origins; never a wildcard CORS policy.
    storage.client.put_bucket_cors(
        Bucket=storage.bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": [upload_browser_origin()],
                    "AllowedMethods": ["PUT"],
                    "AllowedHeaders": ["content-type", "x-amz-checksum-sha256"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 300,
                }
            ]
        },
    )
    scanner_sandbox = KnowledgeProcessSandbox(
        os.environ["KB01_TEST_TOOL_IMAGE"], Path(os.environ["KB01_TEST_WORK_ROOT"])
    )
    extractor = IsolatedKnowledgeArchiveExtractor(
        KnowledgeProcessSandbox(
            os.environ["KB01_TEST_ARCHIVE_IMAGE"], Path(os.environ["KB01_TEST_ARCHIVE_WORK_ROOT"])
        )
    )
    parser = IsolatedNativeDocumentParser(
        KnowledgeProcessSandbox(
            os.environ["KB01_TEST_NATIVE_IMAGE"], Path(os.environ["KB01_TEST_NATIVE_WORK_ROOT"])
        )
    )
    scanner = ClamKnowledgeScanner(
        scanner_sandbox,
        Path(os.environ["KB01_TEST_SCAN_DATABASE"]),
        os.environ["KB01_TEST_SCAN_IDENTITY"],
    )
    scopes = {
        "knowledge:upload:" + name
        for name in ("create", "read", "write", "complete", "work", "cancel")
    }
    scopes |= {"knowledge:batch:work", "knowledge:document:ingest"}

    def current_contexts():
        people = json.loads(path.read_text())
        return [
            RepositoryContext.user(
                UUID(people[name]["tenant_id"]), "synthetic-kb-technical-worker", scopes
            )
            for name in ("A", "B")
        ]

    app.state.knowledge_session_factory = sf
    app.state.knowledge_binary_store = storage
    app.state.knowledge_management_worker = KnowledgeManagementWorker(
        sf,
        storage,
        scanner,
        scanner_sandbox,
        extractor,
        parser,
        current_contexts,
        Path(os.environ["KB01_TEST_WORK_ROOT"]),
        poll_interval=0.5,
    )
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--port", type=int, default=18010)
    args = parser.parse_args()
    if os.environ.get("M0_LOCAL_UAT") != "1" or os.environ.get("KB01_LOCAL_UAT") != "1":
        raise SystemExit("Explicit loopback-only KB01_LOCAL_UAT=1 and M0_LOCAL_UAT=1 required")
    if args.seed:
        if args.manifest.exists():
            raise SystemExit("Manifest exists; preserve it and choose a new isolated path")
        seed(args.manifest)
        return
    import uvicorn

    uvicorn.run(host(args.manifest), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
