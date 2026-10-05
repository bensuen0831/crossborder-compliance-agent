"""Track D wire-contract checks against existing APIs; no new governance backend.

Trusted context injection and in-memory artifact storage are TEST adapters only.
PostgreSQL, Redis, ingestion/outbox and publication workers are real.
"""

import threading
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_phase1f_postgres import FakeEmbedding, inputs
from test_phase1f_postgres import fixture as fixture
from test_phase1g_persistence_postgres import policies

from crossborder_compliance.application.knowledge_services import KnowledgeIngestionService
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_publication_worker import (
    KnowledgePublicationWorker,
)
from crossborder_compliance.infrastructure.knowledge_worker import (
    KnowledgeIngestionWorker,
    RedisKnowledgeTaskQueue,
)
from crossborder_compliance.interfaces.api.routes import (
    admin_metadata,
    knowledge,
    metadata,
    retrieval,
)

pytestmark = pytest.mark.runtime_smoke


def test_knowledge_admin_wire_flow_automatic_ready_and_runtime_query(fixture):
    f = fixture
    _, policy, _ = policies(f)
    identity = {"context": f["ctx"]}
    queue = RedisKnowledgeTaskQueue(get_settings().redis_url, f["tenant"], "track-d-test")
    worker = KnowledgeIngestionWorker(
        f["repo"], KnowledgeIngestionService(f["repo"], storage=f["storage"]), queue
    )
    stop = threading.Event()
    errors = []

    @asynccontextmanager
    async def lifespan(app):
        publication = KnowledgePublicationWorker(
            f["sf"], get_settings().redis_url, embedding=FakeEmbedding(), poll_interval=0.05
        )

        def ingest_loop():
            while not stop.is_set():
                try:
                    worker.run_once()
                except Exception as exc:
                    errors.append(str(exc))
                    stop.set()

        thread = threading.Thread(target=ingest_loop, daemon=True)
        thread.start()
        publication.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=3)
            publication.stop()

    app = FastAPI(lifespan=lifespan)
    app.state.knowledge_session_factory = f["sf"]
    app.state.knowledge_queue = queue
    for router in (knowledge.router, retrieval.router, metadata.router):
        app.include_router(router)

    @app.middleware("http")
    async def trusted_test_context(request, call_next):
        if identity["context"] is not None:
            request.state.repository_context = identity["context"]
        return await call_next(request)

    def checked(response, expected=200):
        assert response.status_code == expected, response.text
        return response.json()

    with TestClient(app) as c:
        source = checked(
            c.post(
                "/api/v1/admin/knowledge-sources",
                json={
                    "collection_id": f["col"],
                    "code": f"track-d-{uuid4()}",
                    "source_type": "APPROVED_INTERNAL",
                    "language": "en",
                    "provenance": {"test": "Track D API contract"},
                },
            ),
            201,
        )
        source = checked(
            c.patch(
                f"/api/v1/admin/knowledge-sources/{source['source_id']}",
                json={
                    "expected_record_version": source["record_version"],
                    "validation_status": "VALIDATED",
                },
            )
        )
        doc = checked(
            c.post(
                "/api/v1/admin/knowledge-documents",
                json={
                    "source_id": source["source_id"],
                    "display_name": "Admin wire demo",
                },
            ),
            201,
        )
        v = checked(
            c.post(
                f"/api/v1/admin/knowledge-documents/{doc['document_id']}/versions",
                json={
                    "collection_version_id": f["cv"],
                    "language": "en",
                    "provenance": {"test": True},
                },
            ),
            201,
        )
        path = f"/api/v1/admin/knowledge-versions/{v['knowledge_version_id']}"
        run = checked(c.post(path + "/ingest", json=inputs(f)), 202)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            v = checked(c.get(path))
            if v["lifecycle"] == "INGESTED":
                break
            time.sleep(0.05)
        assert not errors, errors
        assert v["lifecycle"] == "INGESTED"
        assert (
            checked(c.get(f"/api/v1/admin/knowledge-ingestion-runs/{run['ingestion_run_id']}"))[
                "status"
            ]
            == "COMPLETED"
        )
        assert checked(c.get(path + "/bindings"))[0]["dimensions"]["product"] == [f["a"]]

        for action in ("validate", "submit-review"):
            v = checked(
                c.post(path + "/" + action, json={"expected_record_version": v["record_version"]})
            )
        # Backend enforces an independent reviewer, not just UI visibility.
        assert (
            c.post(
                path + "/approve", json={"expected_record_version": v["record_version"]}
            ).status_code
            == 422
        )
        identity["context"] = f["reviewer"].context
        v = checked(
            c.post(path + "/approve", json={"expected_record_version": v["record_version"]})
        )
        identity["context"] = RepositoryContext.user(
            UUID(f["tenant"]), "project-user", {"project:read"}
        )
        assert (
            c.post(
                path + "/publish", json={"expected_record_version": v["record_version"]}
            ).status_code
            == 403
        )
        identity["context"] = f["ctx"]
        v = checked(
            c.post(path + "/publish", json={"expected_record_version": v["record_version"]})
        )
        assert v["lifecycle"] == "ACTIVE"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            ready = checked(c.get(path + "/runtime-readiness"))
            if ready["status"] == "READY":
                break
            time.sleep(0.05)
        assert ready["status"] == "READY", ready
        assert all(ready["checks"].values())
        result = checked(
            c.post(
                f"/api/v1/projects/{f['project']}/knowledge/retrieve",
                json={
                    "analysis_snapshot_id": f["snapshot"],
                    "policy_id": policy["policy_id"],
                    "query_text": "Generic",
                    "idempotency_key": str(uuid4()),
                },
            )
        )
        assert {
            item["knowledge_version_id"]
            for item in result["rag_context_pack"]["evidence_pack"]["items"]
        } == {v["knowledge_version_id"]}
        identity["context"] = None
        assert c.get(path).status_code == 401
        identity["context"] = RepositoryContext.user(uuid4(), "other-tenant", {"knowledge:admin"})
        assert c.get(path).status_code == 404


def test_metadata_draft_edit_history_review_publish_and_unauthorized_publish(fixture):
    f = fixture
    author = RepositoryContext.user(UUID(f["tenant"]), "track-d-author", {"metadata:admin"})
    reviewer = RepositoryContext.user(
        UUID(f["tenant"]), "track-d-reviewer", {"metadata:admin", "metadata:review"}
    )
    publisher = RepositoryContext.user(
        UUID(f["tenant"]), "track-d-publisher", {"metadata:admin", "metadata:publish"}
    )
    identity = {"context": author}
    app = FastAPI()
    app.include_router(admin_metadata.router)
    app.include_router(metadata.router)

    @app.middleware("http")
    async def trusted_test_context(request, call_next):
        request.state.repository_context = identity["context"]
        return await call_next(request)

    c = TestClient(app)
    response = c.post(
        "/api/v1/admin/scenarios",
        json={
            "code": f"track-d-{uuid4()}",
            "display_name": "New configurable scenario",
            "payload": {"visible": True},
        },
    )
    assert response.status_code == 200, response.text
    v = response.json()
    path = f"/api/v1/admin/scenarios/{v['version_id']}"
    response = c.patch(
        path + "/draft",
        json={
            "payload": {"visible": True, "label": "Edited"},
            "expected_record_version": v["record_version"],
        },
    )
    assert response.status_code == 200, response.text
    v = response.json()
    assert (
        c.patch(path + "/draft", json={"payload": {}, "expected_record_version": 1}).status_code
        == 409
    )
    v = c.post(
        path + "/submit-review", json={"expected_record_version": v["record_version"]}
    ).json()
    identity["context"] = reviewer
    response = c.post(path + "/approve", json={"expected_record_version": v["record_version"]})
    assert response.status_code == 200, response.text
    v = response.json()
    identity["context"] = author
    assert (
        c.post(path + "/publish", json={"expected_record_version": v["record_version"]}).status_code
        == 403
    )
    identity["context"] = publisher
    response = c.post(path + "/publish", json={"expected_record_version": v["record_version"]})
    assert response.status_code == 200, response.text
    history = c.get(f"/api/v1/admin/scenarios/{v['definition_id']}/versions").json()["items"]
    assert history[0]["lifecycle_status"] == "ACTIVE"
    assert history[0]["payload"]["label"] == "Edited"
    assert any(
        item["definition_id"] == v["definition_id"]
        for item in c.get("/api/v1/metadata/scenarios").json()["items"]
    )
