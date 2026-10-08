"""Real production intake/review HTTP paths; server-owned actor and run references."""

# ruff: noqa: F401,F811 -- shared real PostgreSQL fixtures
from functools import partial
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_m2a_intake import create, setup
from test_m2a_structured_intake import binding, start
from test_phase1j_postgres import fixture, foundation_i
from test_phase1l_b_postgres import foundation_j

from crossborder_compliance.application.intake_services import (
    ConfirmProjectIntake,
    ProjectIntakeService,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.reviews import router

pytestmark = pytest.mark.runtime_smoke


def production_review(f):
    binding(f)
    app, client, context, values = setup(f)
    context = RepositoryContext.user(
        context.tenant_id, "author", set(context.permission.scopes) | {"workflow:review"}
    )
    app.dependency_overrides[get_repository_context] = lambda: context
    app.include_router(router)
    record = create(client, {**values, "data_volume": "3"}).json()
    # Trusted host plan configuration is pinned before execution. Browser has no flag.
    confirmed = ProjectIntakeService(
        PostgresProjectRepository(f["sf"], context),
        partial(prepare_snapshot, requirement_confirmation=True),
    ).confirm(UUID(record["project_id"]), ConfirmProjectIntake(expected_version=1))
    view = start(client, confirmed.model_dump(mode="json"))
    assert view["status"] == "REVIEW_REQUIRED", view
    url = f"/api/v1/reviews/{view['review_id']}"
    review = client.get(url)
    assert review.status_code == 200, review.text
    return app, client, context, review.json(), url, confirmed


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_http_approve_and_recover_no_client_authority(foundation_j):
    app, client, context, task, url, confirmed = production_review(foundation_j)
    body = dict(
        decision="APPROVE",
        expected_record_version=task["record_version"],
        idempotency_key=str(uuid4()),
    )
    for field in ("decided_by", "tenant_id", "thread_id", "start_at", "final_path", "policy"):
        assert client.post(url + "/decisions", json={**body, field: "injected"}).status_code == 422
    response = client.post(url + "/decisions", json=body)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["status"] == "APPROVED" and value["continuation_status"] == "CONTINUED"
    assert value["history"][0]["decided_by"] == "author"
    assert client.post(url + "/decisions", json=body).json() == value
    assert client.post(url + "/resume").json() == value
    assert client.post(url + "/resume", json={"start_at": "final_path"}).status_code == 422
    workflow = client.get(f"/api/v1/workflows/{confirmed.workflow_run_id}").json()
    assert workflow["status"] == "COMPLETED" and workflow["analysis_snapshot_id"] == str(
        confirmed.analysis_snapshot_id
    )
    for ctx in (
        RepositoryContext.user(uuid4(), "author", set(context.permission.scopes)),
        RepositoryContext.user(context.tenant_id, "other", set(context.permission.scopes)),
        RepositoryContext.user(
            context.tenant_id, "author", set(context.permission.scopes) - {"workflow:review"}
        ),
    ):
        app.dependency_overrides[get_repository_context] = lambda ctx=ctx: ctx
        assert client.post(url + "/resume").status_code == 404


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_http_request_changes_then_typed_intake_successor(foundation_j):
    app, client, context, task, url, confirmed = production_review(foundation_j)
    response = client.post(
        url + "/decisions",
        json=dict(
            decision="REQUEST_CHANGES",
            expected_record_version=task["record_version"],
            idempotency_key=str(uuid4()),
            comment="Clarify purpose",
        ),
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    assert (
        changed["presentation_state"] == "CHANGES_REQUESTED"
        and "ADD_INFORMATION" in changed["allowed_actions"]
    )
    assert (
        client.get(f"/api/v1/workflows/{confirmed.workflow_run_id}").json()["status"]
        == "REVIEW_REQUIRED"
    )
    facts = confirmed.intake.model_dump(
        mode="json",
        exclude={
            "project_id",
            "project_name",
            "schema_version",
            "record_version",
            "created_at",
            "updated_at",
            "provenance",
        },
    )
    facts["scenario_description"] = "Clarified scenario description"
    payload = dict(
        expected_record_version=changed["record_version"],
        idempotency_key=str(uuid4()),
        correction=dict(
            correction_type="CLARIFY_INTAKE",
            target_object_type="PROJECT_INTAKE",
            target_object_id=changed["object_id"],
            facts=facts,
        ),
    )
    response = client.post(url + "/corrections", json=payload)
    assert response.status_code == 200, response.text
    lineage = response.json()
    assert lineage["source_snapshot_id"] == str(confirmed.analysis_snapshot_id)
    assert (
        lineage["successor_snapshot_id"] != lineage["source_snapshot_id"]
        and lineage["rerun_from_stage"] == "requirement"
    )
    assert client.post(url + "/corrections", json=payload).json() == lineage
    target = client.get(f"/api/v1/workflows/{lineage['successor_workflow_run_id']}")
    assert target.status_code == 200 and target.json()["status"] == "COMPLETED", target.text
    assert client.get(url).json()["presentation_state"] == "SUPERSEDED"
    assert client.post(url + "/successor/start", json={"start_at": "final_path"}).status_code == 422
    assert client.post(url + "/successor/start").status_code == 200
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        context.tenant_id, "author", set(context.permission.scopes) - {"workflow:review"}
    )
    assert client.post(url + "/successor/start").status_code == 404
