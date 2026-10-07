"""Real C0 owning services in the existing canonical graph, both input modes."""

# ruff: noqa: F401,F811 -- canonical PostgreSQL pytest fixture graph
from uuid import UUID

import pytest
from phase1l_b_worker import build
from test_m2c_authority_postgres import authority, fixture, foundation_i
from test_phase1l_b_postgres import manifest

from crossborder_compliance.application.formal_result_services import (
    CrossBorderAssessmentService,
    RegulatoryDocumentRequirementService,
)
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)
from crossborder_compliance.workflows.canonical import PIPELINE

pytestmark = pytest.mark.runtime_smoke


@pytest.mark.parametrize("foundation_i", [{}, {"no_data": True}], indirect=True)
def test_canonical_v2_executes_owners_and_preserves_refs_on_locale_replay(authority):
    f = authority
    m = manifest(f)
    runtime, factory = build(m)
    run = UUID(m["run"])
    runtime.start(run, factory.initial_state(run))
    state = runtime.inspect_checkpoint_state(run)["values"]
    assert state["route"] == "COMPLETED", state
    expected = [s.value for s in PIPELINE]
    if m["plan"]["mode"] == "SCENARIO_LEVEL":
        assert "classification" not in state["result_refs"]
    assert state["completed_steps"] == expected
    repo = PostgresCountryComplianceRepository(f["sf"], f["jctx"])
    cross = CrossBorderAssessmentService(repo).read(UUID(state["result_refs"]["cross_border"]))
    docs = RegulatoryDocumentRequirementService(repo).read(UUID(state["result_refs"]["documents"]))
    assert cross.items[0].status == "DIRECT_TRANSFER_ALLOWED"
    assert not docs.review_required and docs.items[0].requirement_level == "REQUIRED"
    assert cross.analysis_snapshot_id == docs.analysis_snapshot_id == UUID(f["snapshot"])
    for locale in ("en-US", "zh-HK"):
        replay = dict(m, locale=locale)
        restarted, _ = build(replay)
        restarted.start(run, factory.initial_state(run))
        assert restarted.get_status(run) == "COMPLETED"
        assert restarted.inspect_checkpoint_state(run)["values"] == state


@pytest.mark.parametrize("foundation_i", [{}, {"no_data": True}], indirect=True)
def test_authorized_stage1_projection_exact_snapshot_and_tenant(authority):
    from uuid import uuid4

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.domain.security import RepositoryContext
    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.routes import workflow

    f = authority
    m = manifest(f)
    runtime, factory = build(m)
    run = UUID(m["run"])
    runtime.start(run, factory.initial_state(run))
    context = RepositoryContext.user(UUID(f["tenant"]), "author", set(m["scopes"]))
    app = FastAPI()
    app.include_router(workflow.router)
    app.state.knowledge_session_factory = f["sf"]
    app.state.formal_workflow_host = lambda *args: (run, m["plan"])
    app.dependency_overrides[get_repository_context] = lambda: context
    client = TestClient(app)
    url = f"/api/v1/workflows/{run}/stage1-result"
    result = client.get(url)
    assert result.status_code == 200, result.text
    value = result.json()
    import json
    from pathlib import Path

    output = Path("artifacts/m2c")
    output.mkdir(parents=True, exist_ok=True)
    (output / ("stage1-" + m["plan"]["mode"] + ".json")).write_text(
        json.dumps(value, indent=2) + "\n"
    )
    assert value["cross_border"]["items"][0]["status"] == "DIRECT_TRANSFER_ALLOWED"
    assert value["document_requirements"]["items"][0]["requirement_level"] == "REQUIRED"
    assert value["legal_basis"][0]["legal_basis_id"] == f["basis"]
    assert (
        value["analysis_snapshot_id"] == f["snapshot"]
        and value["project"]["project_id"] == f["project"]
    )
    assert value["generation_available"] is False
    assert len(value["steps"]) == len(value["completed_steps"]) == 17
    for locale in ("zh-CN", "zh-HK", "en-US"):
        assert client.get(url, headers={"Accept-Language": locale}).json() == value
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        uuid4(), "author", set(m["scopes"])
    )
    assert client.get(url).status_code == 404
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        UUID(f["tenant"]), "author", {"workflow:read"}
    )
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("authority", [{"permission_field": "missing_formal_fact"}], indirect=True)
def test_crossborder_review_is_durable_and_does_not_produce_later_decisions(authority):
    from sqlalchemy import func, select

    from crossborder_compliance.infrastructure.persistence import decision_models as j
    from crossborder_compliance.infrastructure.persistence import models as b

    f = authority
    m = manifest(f)
    runtime, factory = build(m)
    run = UUID(m["run"])
    assert runtime.start(run, factory.initial_state(run)).status == "REVIEW_REQUIRED"
    before = runtime.inspect_checkpoint_state(run)
    assert before["values"]["current_step"] == "cross_border"
    assert "candidate_path" not in before["values"]["result_refs"]
    restarted, _ = build(dict(m, locale="en-US"))
    assert restarted.inspect_checkpoint_state(run)["values"] == before["values"]
    assert restarted.start(run, factory.initial_state(run)).status == "REVIEW_REQUIRED"
    with f["sf"]() as session:
        review = session.scalar(
            select(b.ReviewTaskEntity).where(b.ReviewTaskEntity.workflow_run_id == str(run))
        )
        assert review and review.status == "PENDING"
        for kind in ("CANDIDATE_PATH", "RISK", "RECOMMENDATION", "FINAL_PATH"):
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(j.MODELS[kind])
                    .where(j.MODELS[kind].analysis_snapshot_id == f["snapshot"])
                )
                == 0
            )


def test_historical_v1_actual_postgres_read_has_explicit_authority_gap(foundation_i):
    from types import SimpleNamespace

    from sqlalchemy import update
    from test_phase1j_postgres import foundation_j as original

    from crossborder_compliance.infrastructure.persistence.models import WorkflowRunEntity
    from crossborder_compliance.workflows.canonical import (
        LEGACY_GRAPH_VERSION,
        LEGACY_STATE_VERSION,
    )

    f = original.__wrapped__(foundation_i, SimpleNamespace(param={}))
    m = manifest(f)
    run = UUID(m["run"])
    with f["sf"]() as session, session.begin():
        session.execute(
            update(WorkflowRunEntity)
            .where(WorkflowRunEntity.workflow_run_id == str(run))
            .values(
                graph_definition_version=LEGACY_GRAPH_VERSION,
                state_schema_version=LEGACY_STATE_VERSION,
            )
        )
    runtime, factory = build(m)
    assert runtime.start(run, factory.initial_state(run)).status == "COMPLETED"
    state = runtime.inspect_checkpoint_state(run)["values"]
    assert len(state["completed_steps"]) == 16 and "cross_border" not in state["result_refs"]
    # No policy retrofit is attempted when reading or replaying a historic run.
    assert build(m)[0].start(run, factory.initial_state(run)).status == "COMPLETED"

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.domain.security import RepositoryContext
    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.routes import workflow

    app = FastAPI()
    app.include_router(workflow.router)
    app.state.knowledge_session_factory = f["sf"]
    app.state.formal_workflow_host = lambda *args: (run, m["plan"])
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        UUID(f["tenant"]), "author", set(m["scopes"])
    )
    response = TestClient(app).get(f"/api/v1/workflows/{run}/stage1-result")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["cross_border"] is None and result["document_requirements"] is None
    assert result["capability_gaps"] == ["HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED"]


def test_stage1_projection_ignores_future_inventory_and_documents(authority):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from test_phase1d_postgres import MemoryStorage, Queue
    from test_phase1g_publication_postgres import snapshot

    from crossborder_compliance.application.document_services import (
        DocumentIngestionService,
        DocumentParseService,
    )
    from crossborder_compliance.domain.security import RepositoryContext
    from crossborder_compliance.infrastructure.document_parsers import default_native_parsers
    from crossborder_compliance.infrastructure.persistence import context_models as c
    from crossborder_compliance.infrastructure.persistence.document_repositories import (
        PostgresDocumentIntelligenceRepository,
    )
    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.routes import workflow

    f = authority
    m = manifest(f)
    run = UUID(m["run"])
    runtime, factory = build(m)
    runtime.start(run, factory.initial_state(run))
    ctx = RepositoryContext.user(
        UUID(f["tenant"]),
        "author",
        set(m["scopes"]) | {"document:read", "document:write", "document:parse", "document:upload"},
    )
    app = FastAPI()
    app.include_router(workflow.router)
    app.state.knowledge_session_factory = f["sf"]
    app.state.formal_workflow_host = lambda *args: (run, m["plan"])
    app.dependency_overrides[get_repository_context] = lambda: ctx
    client = TestClient(app)
    url = f"/api/v1/workflows/{run}/stage1-result"
    before = client.get(url)
    assert before.status_code == 200, before.text
    with f["sf"]() as session, session.begin():
        previous = session.scalar(
            select(c.DataItemResolutionDetailEntity).where(
                c.DataItemResolutionDetailEntity.data_item_id == f["item"],
                c.DataItemResolutionDetailEntity.version == 1,
            )
        )
        session.add(
            c.DataItemResolutionDetailEntity(
                tenant_id=f["tenant"],
                data_item_id=f["item"],
                version=2,
                display_name="Future inventory display",
                value_type=previous.value_type,
                confidence=1,
                validation_status="VALIDATED",
                review_required=False,
            )
        )
    repo = PostgresDocumentIntelligenceRepository(f["sf"], ctx)
    storage = MemoryStorage()
    version = DocumentIngestionService(repo, storage, None, scan_required=False).ingest(
        tenant_id=UUID(f["tenant"]),
        project_id=UUID(f["project"]),
        filename="later-universe.txt",
        content=b"Future input universe",
        mime_type="text/plain",
    )
    parser = DocumentParseService(repo, storage, default_native_parsers(), Queue())
    task = parser.request_parse(
        document_version_id=UUID(version["document_version_id"]),
        idempotency_key="later-stage1-universe",
    )
    parsed = parser.process_task(UUID(task["task_id"]))
    assert parsed["status"] == "COMPLETED"
    second = UUID(snapshot(f))
    repo.pin_parse_run(
        analysis_snapshot_id=second,
        document_version_id=UUID(version["document_version_id"]),
        parse_run_id=UUID(parsed["parse_run_id"]),
    )
    after = client.get(url)
    assert after.status_code == 200, after.text
    assert after.json() == before.json()
    assert version["document_version_id"] not in {
        d["document_version_id"] for d in after.json()["documents"]
    }
