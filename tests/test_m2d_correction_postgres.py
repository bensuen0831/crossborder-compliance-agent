"""Forward-only owning correction of genuine structured/document conflict."""

# ruff: noqa: F401,F811 -- shared real PostgreSQL fixtures
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_m2a_intake import create, setup
from test_m2a_structured_intake import binding, confirm, facts, real_document, start
from test_phase1j_postgres import fixture, foundation_i
from test_phase1l_b_postgres import foundation_j

from crossborder_compliance.application.review_services import (
    FactSelection,
    ReviewCorrectionRequest,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
    PostgresReviewRepository,
)
from crossborder_compliance.infrastructure.persistence.review_governance import ReviewConflict

pytestmark = pytest.mark.runtime_smoke


def conflict(f):
    binding(f)
    binding(f, code="GENERIC_FIELD", field="business_purpose", value_type="string")
    app, client, context, values = setup(f)
    record = create(client, {**values, "data_volume": "3"}).json()
    real_document(f, context, record["project_id"], "Other purpose")
    record = confirm(client, record)
    workflow = start(client, record)
    assert workflow["status"] == "REVIEW_REQUIRED"
    authorized = RepositoryContext.user(
        context.tenant_id,
        "author",
        set(context.permission.scopes)
        | {"workflow:review", f"project:{record['project_id']}:comply"},
    )
    repo = PostgresReviewRepository(f["sf"], authorized)
    task = repo.read(UUID(workflow["review_id"]))
    assert task.object_type == "CONTEXT_CONFLICT" and "SUBMIT_CORRECTION" in task.allowed_actions
    assert "APPROVE" not in task.allowed_actions and len(task.choices) == 2
    return app, client, authorized, repo, task, record


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_fact_choice_creates_successor_keeps_source_and_exact_parse_universe(foundation_j):
    from crossborder_compliance.infrastructure.persistence.document_models import (
        AnalysisSnapshotParseRunPinEntity,
    )

    f = foundation_j
    _app, client, context, repo, task, source = conflict(f)
    before_rows = facts(f, source["project_id"])
    before = [
        (
            r.fact_id,
            r.normalized_value_json,
            r.review_required,
            r.structured_provenance_json,
            r.source_document_ids_json,
        )
        for r in before_rows
    ]
    before_result = client.get(f"/api/v1/workflows/{task.workflow_run_id}/stage1-result").json()
    with f["sf"]() as s:
        old_pin = s.scalar(
            select(e.AnalysisSnapshotContextPinEntity).where(
                e.AnalysisSnapshotContextPinEntity.analysis_snapshot_id
                == source["analysis_snapshot_id"]
            )
        )
        old_conflict = s.get(e.ContextConflictEntity, str(task.object_id))
        source_pins = [
            (p.document_version_id, p.parse_run_id)
            for p in s.scalars(
                select(AnalysisSnapshotParseRunPinEntity).where(
                    AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id
                    == source["analysis_snapshot_id"]
                )
            )
        ]
        state = (
            old_conflict.resolution_status,
            old_conflict.record_version,
            old_pin.context_resolution_run_id,
        )
    choice = next(c for c in task.choices if c.source_document_ids)
    command = ReviewCorrectionRequest(
        expected_record_version=task.record_version,
        idempotency_key=str(uuid4()),
        correction=FactSelection(
            correction_type="SELECT_BUSINESS_FACT",
            target_object_type="CONTEXT_CONFLICT",
            target_object_id=task.object_id,
            selected_fact_id=choice.object_id,
        ),
    )
    lineage = repo.correct(task.review_id, command)
    assert lineage.source_snapshot_id == task.analysis_snapshot_id
    assert (
        lineage.successor_snapshot_id != task.analysis_snapshot_id
        and lineage.rerun_from_stage == "requirement"
    )
    assert repo.correct(task.review_id, command) == lineage
    old_after = [
        (
            r.fact_id,
            r.normalized_value_json,
            r.review_required,
            r.structured_provenance_json,
            r.source_document_ids_json,
        )
        for r in facts(f, source["project_id"])
        if r.version == old_pin.context_resolution_version
    ]
    assert sorted(old_after, key=lambda v: v[0]) == sorted(before, key=lambda v: v[0])
    with f["sf"]() as s:
        old_conflict = s.get(e.ContextConflictEntity, str(task.object_id))
        old_pin_after = s.scalar(
            select(e.AnalysisSnapshotContextPinEntity).where(
                e.AnalysisSnapshotContextPinEntity.analysis_snapshot_id
                == source["analysis_snapshot_id"]
            )
        )
        assert (
            old_conflict.resolution_status,
            old_conflict.record_version,
            old_pin_after.context_resolution_run_id,
        ) == state
        target_pins = [
            (p.document_version_id, p.parse_run_id)
            for p in s.scalars(
                select(AnalysisSnapshotParseRunPinEntity).where(
                    AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id
                    == str(lineage.successor_snapshot_id)
                )
            )
        ]
        assert sorted(target_pins) == sorted(source_pins)
        s1 = s.get(b.AnalysisSnapshotEntity, str(lineage.source_snapshot_id))
        s2 = s.get(b.AnalysisSnapshotEntity, str(lineage.successor_snapshot_id))
        assert s2.analysis_as_of_date == s1.analysis_as_of_date
        current = s.scalar(
            select(e.BusinessFactEntity).where(
                e.BusinessFactEntity.project_id == source["project_id"],
                e.BusinessFactEntity.fact_type == "GENERIC_FIELD",
                e.BusinessFactEntity.version > old_pin.context_resolution_version,
            )
        )
        assert current.normalized_value_json == "Other purpose" and not current.review_required
        assert (
            current.resolution_method == "HUMAN_CONFLICT_SELECTION"
            and current.source_document_ids_json
        )
    target = PostgresProjectRepository(f["sf"], context).read_intake(UUID(source["project_id"]))
    view = start(client, target.model_dump(mode="json"))
    assert view["workflow_run_id"] == str(lineage.successor_workflow_run_id)
    assert view["status"] == "COMPLETED", view
    assert (
        client.get(f"/api/v1/workflows/{task.workflow_run_id}/stage1-result").json()
        == before_result
    )
    assert repo.read(task.review_id).presentation_state == "SUPERSEDED"


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_outside_target_and_wrong_payload_do_not_create_successor(foundation_j):
    f = foundation_j
    _app, _client, _context, repo, task, _source = conflict(f)
    command = ReviewCorrectionRequest(
        expected_record_version=task.record_version,
        idempotency_key=str(uuid4()),
        correction=FactSelection(
            correction_type="SELECT_BUSINESS_FACT",
            target_object_type="CONTEXT_CONFLICT",
            target_object_id=task.object_id,
            selected_fact_id=uuid4(),
        ),
    )
    with pytest.raises(ReviewConflict, match="CORRECTION_OUTSIDE_REVIEW_TARGET"):
        repo.correct(task.review_id, command)
    assert repo.read(task.review_id).record_version == task.record_version


@pytest.fixture
def product_foundation(fixture, monkeypatch):
    from types import SimpleNamespace

    import test_phase1i_postgres as i_tests
    from m2c_policy_fixtures import configure_authorities
    from test_phase1j_postgres import foundation_j as j_foundation

    original = i_tests.binding
    # Published jurisdiction-scoped legal knowledge remains authorized even when
    # product ownership is unresolved. No production retrieval fallback changes.
    monkeypatch.setattr(
        i_tests,
        "binding",
        lambda f, **kwargs: original(f, scope="GLOBAL", dimensions={"jurisdiction": [f["juri"]]}),
    )
    f = i_tests.foundation_i.__wrapped__(fixture, SimpleNamespace(param={"no_data": True}))
    return j_foundation.__wrapped__(
        f, SimpleNamespace(param={"before_j_initialization": configure_authorities})
    )


@pytest.mark.parametrize("choice_source", ["selected", "detected"])
def test_product_choice_uses_product_owner_and_preserves_detection(
    product_foundation, choice_source
):
    from functools import partial

    from test_phase1f_postgres import metadata

    from crossborder_compliance.application.intake_services import (
        ConfirmProjectIntake,
        ProjectIntakeService,
    )
    from crossborder_compliance.application.review_services import ProductSelection
    from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
    from crossborder_compliance.infrastructure.persistence.models import (
        SourceTraceRefEntity,
    )
    from crossborder_compliance.interfaces.api.dependencies import get_repository_context

    f = product_foundation
    binding(f)
    app, client, context, values = setup(f)
    detected = metadata(f["sf"], f["tenant"], "PRODUCT")
    record = create(client, {**values, "data_volume": "3"}).json()
    real_document(f, context, record["project_id"], "Generic")
    with f["sf"]() as s:
        traces = tuple(
            UUID(t)
            for t in s.scalars(
                select(SourceTraceRefEntity.source_trace_ref_id).where(
                    SourceTraceRefEntity.tenant_id == f["tenant"]
                )
            )
        )
    assert traces
    prepared = partial(
        prepare_snapshot, detected_product_scope=(UUID(detected),), product_source_trace_ids=traces
    )
    intake = ProjectIntakeService(PostgresProjectRepository(f["sf"], context), prepared).confirm(
        UUID(record["project_id"]), ConfirmProjectIntake(expected_version=1)
    )
    source = intake.model_dump(mode="json")
    view = start(client, source)
    context = RepositoryContext.user(
        context.tenant_id, "author", set(context.permission.scopes) | {"workflow:review"}
    )
    app.dependency_overrides[get_repository_context] = lambda: context
    repo = PostgresReviewRepository(f["sf"], context)
    task = repo.read(UUID(view["review_id"]))
    assert "PRODUCT_CONTEXT_CONFLICT" in task.reason_codes and "APPROVE" not in task.allowed_actions
    before_result = client.get(f"/api/v1/workflows/{task.workflow_run_id}/stage1-result").json()
    selected = record["intake"]["selected_products"][0] if choice_source == "selected" else detected
    chosen = next(c for c in task.choices if str(c.object_id) == selected)
    assert chosen.source_trace_ids == traces
    request = ReviewCorrectionRequest(
        expected_record_version=task.record_version,
        idempotency_key=str(uuid4()),
        correction=ProductSelection(
            correction_type="SELECT_PRODUCT_SCOPE",
            target_object_type="CONTEXT_CONFLICT",
            target_object_id=task.object_id,
            selected_product_ids=(UUID(selected),),
        ),
    )
    lineage = repo.correct(task.review_id, request)
    target = PostgresProjectRepository(f["sf"], context).read_intake(UUID(record["project_id"]))
    assert target.intake.selected_products == [selected]
    with f["sf"]() as s:
        s1 = s.scalar(
            select(e.AnalysisSnapshotContextPinEntity).where(
                e.AnalysisSnapshotContextPinEntity.analysis_snapshot_id
                == str(task.analysis_snapshot_id)
            )
        )
        s2 = s.scalar(
            select(e.AnalysisSnapshotContextPinEntity).where(
                e.AnalysisSnapshotContextPinEntity.analysis_snapshot_id
                == str(lineage.successor_snapshot_id)
            )
        )
        old = s.get(e.ContextConflictEntity, str(task.object_id))
        assert old.resolution_status == "OPEN" and old.review_required
        current = s.scalar(
            select(e.ProductScopeResolutionEntity).where(
                e.ProductScopeResolutionEntity.project_id == record["project_id"],
                e.ProductScopeResolutionEntity.version == s2.context_resolution_version,
            )
        )
        assert current.version > s1.context_resolution_version
        assert current.selected_product_scope_json == [values["selected_products"][0]]
        assert current.detected_product_context_json == [detected]
        assert current.effective_product_scope_json == [selected] and not current.review_required
    target_view = start(client, target.model_dump(mode="json"))
    assert target_view["workflow_run_id"] == str(lineage.successor_workflow_run_id)
    assert target_view["status"] in {"COMPLETED", "REVIEW_REQUIRED"}, target_view
    assert (
        client.get(f"/api/v1/workflows/{task.workflow_run_id}/stage1-result").json()
        == before_result
    )


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_successor_delivery_failure_after_commit_can_recover_without_old_resume(foundation_j):
    from crossborder_compliance.application.review_services import HumanReviewService

    f = foundation_j
    _app, client, context, repo, task, source = conflict(f)
    chosen = next(c for c in task.choices if c.structured_provenance)
    payload = ReviewCorrectionRequest(
        expected_record_version=task.record_version,
        idempotency_key=str(uuid4()),
        correction=FactSelection(
            correction_type="SELECT_BUSINESS_FACT",
            target_object_type="CONTEXT_CONFLICT",
            target_object_id=task.object_id,
            selected_fact_id=chosen.object_id,
        ),
    )
    original = client.get(f"/api/v1/workflows/{task.workflow_run_id}/stage1-result").json()

    def unavailable(*_):
        raise ConnectionError("delivery unavailable after canonical successor commit")

    with pytest.raises(ConnectionError):
        HumanReviewService(repo, successor_delivery=unavailable).correct(task.review_id, payload)
    value = repo.read(task.review_id)
    assert value.lineage and value.allowed_actions == ("CONTINUE_SUCCESSOR",)

    def deliver(_view, lineage):
        record = PostgresProjectRepository(f["sf"], context).read_intake(UUID(source["project_id"]))
        result = start(client, record.model_dump(mode="json"))
        assert (
            result["workflow_run_id"] == str(lineage.successor_workflow_run_id)
            and result["status"] == "COMPLETED"
        )

    service = HumanReviewService(repo, successor_delivery=deliver)
    continued = service.continue_successor(task.review_id)
    assert continued.lineage == value.lineage and continued.allowed_actions == ()
    assert service.continue_successor(task.review_id) == continued
    assert client.get(f"/api/v1/workflows/{task.workflow_run_id}/stage1-result").json() == original
