"""Owning E/F/H/I exact-version and immutable-write PostgreSQL regressions."""
# ruff: noqa: F401,F811 -- inherited empirical fixture graph
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from test_phase1j_postgres import fixture, foundation_i, foundation_j

from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.context_temporal import exact_item_detail

pytestmark = pytest.mark.runtime_smoke


def test_item_detail_exact_membership_never_uses_latest(foundation_j):
    f = foundation_j
    with f["sf"]() as session, session.begin():
        first = exact_item_detail(session, f["tenant"], f["item"], 1)
        session.add(e.DataItemResolutionDetailEntity(
            tenant_id=f["tenant"], data_item_id=f["item"], version=3,
            display_name="Future input", value_type="future-type", confidence=1,
            validation_status="VALIDATED", review_required=False,
        ))
    with f["sf"]() as session:
        assert exact_item_detail(session, f["tenant"], f["item"], 1).display_name == first.display_name
        assert exact_item_detail(session, f["tenant"], f["item"], 3).display_name == "Future input"
        with pytest.raises(LookupError): exact_item_detail(session, f["tenant"], f["item"], 2)
        with pytest.raises(LookupError): exact_item_detail(session, uuid4(), f["item"], 1)


@pytest.mark.parametrize("operation", ["update", "delete", "duplicate"])
def test_formal_inventory_detail_cannot_be_rewritten(foundation_j, operation):
    f = foundation_j
    with pytest.raises(DBAPIError):
        with f["sf"]() as session, session.begin():
            row = exact_item_detail(session, f["tenant"], f["item"], 1)
            if operation == "update": row.display_name = "Silent overwrite"
            elif operation == "delete": session.delete(row)
            else:
                session.add(e.DataItemResolutionDetailEntity(tenant_id=f["tenant"], data_item_id=f["item"],
                    version=1, display_name="Duplicate", confidence=1, validation_status="VALIDATED"))
            session.flush()


def test_i_preserves_old_pin_and_reads_exact_new_pin(foundation_j, monkeypatch):
    """Seed versioned typed context inputs, execute real owning G/H/I services.

    The real binary/candidate provenance path is tested separately by the four
    snapshot integration test; these inputs isolate the I adapter read contract.
    """
    from test_phase1g_persistence_postgres import query, service
    from crossborder_compliance.application.context_services import ContextResolutionService
    from crossborder_compliance.infrastructure.persistence.context_repositories import PostgresContextResolutionRepository
    from crossborder_compliance.infrastructure.persistence.country_compliance_repository import PostgresCountryComplianceRepository
    import crossborder_compliance.infrastructure.persistence.country_compliance_repository as owning_i
    from crossborder_compliance.application.classification_services import ClassificationService
    from crossborder_compliance.infrastructure.persistence.classification_repository import PostgresFormalClassificationRepository

    f = foundation_j
    old_request = f["request"]
    old_snapshot = str(old_request.analysis_snapshot_id)
    first_input = f["compliance_repo"].prepare(old_request)
    assert first_input.context_version == 1
    repo = PostgresContextResolutionRepository(f["sf"], f["ctx"])
    result = ContextResolutionService(repo).run(UUID(f["project"]),
        selected_product_scope=(UUID(f["a"]),), selected_scenarios=(UUID(f["scenario"]),),
        jurisdictions=({"jurisdiction_id": f["juri"], "input_value": "Confirmed fixture location",
            "context_type": "STORAGE", "location_precision": "EXACT_CANONICAL", "source": "USER_INPUT", "confidence": 1},))
    assert result["version"] == 2
    new_snapshot = uuid4()
    with f["sf"]() as session, session.begin():
        old = session.get(b.AnalysisSnapshotEntity, old_snapshot)
        session.add(b.AnalysisSnapshotEntity(analysis_snapshot_id=str(new_snapshot), tenant_id=f["tenant"],
            project_version_id=old.project_version_id, snapshot_version="2", analysis_as_of_date=old.analysis_as_of_date,
            provenance_json={"fixture": "explicit versioned input"}))
        session.add(e.DataItemResolutionDetailEntity(tenant_id=f["tenant"], data_item_id=f["item"], version=2,
            display_name="Changed confirmed input", value_type="changed-type", confidence=1,
            validation_status="VALIDATED", review_required=False))
        session.add(e.BusinessFactEntity(fact_id=str(uuid4()), tenant_id=f["tenant"], project_id=f["project"],
            fact_type="COUNT", normalized_key="count", normalized_value_json=3, resolution_method="DETERMINISTIC",
            confidence=1, validation_status="VALIDATED", version=2))
    repo.bind_data_item_product(data_item_id=UUID(f["item"]), product_domain_definition_id=None,
        product_definition_id=UUID(f["a"]), relationship_type="PRIMARY", confidence=1, source_trace_ids=(), version=2)
    repo.pin_snapshot_context(analysis_snapshot_id=new_snapshot, project_id=UUID(f["project"]),
        context_resolution_run_id=UUID(result["context_resolution_run_id"]))
    retrieval_repo, _, _ = __import__("test_phase1g_persistence_postgres", fromlist=["policies"]).policies(f)
    evidence = service(f, retrieval_repo).retrieve(query(f, f["policy"], analysis_snapshot_id=str(new_snapshot),
        subject_type="DATA_ITEM", subject_id=f["item"], idempotency_key=str(uuid4())))
    classifier = PostgresFormalClassificationRepository(f["sf"], f["ctx"])
    classifier.pin_configuration(UUID(f["project"]), new_snapshot, UUID(f["scheme_version"]))
    classified = ClassificationService(classifier).execute(project_id=UUID(f["project"]), snapshot_id=new_snapshot,
        data_item_id=UUID(f["item"]), scheme_version_id=UUID(f["scheme_version"]))
    country = PostgresCountryComplianceRepository(f["sf"], f["ctx"])
    country.initialize(UUID(f["project"]), new_snapshot, UUID(f["juri"]))
    new_request = old_request.model_copy(update={"analysis_snapshot_id": new_snapshot,
        "retrieval_run_id": UUID(evidence["retrieval_run_id"]),
        "classification_result_ids": (classified.result.classification_result_id,) if classified.result else (),
        "rule_hit_ids": tuple(hit.rule_hit_id for hit in classified.rule_hits)})
    observed = []
    def record_exact(session, tenant, item, version):
        detail = exact_item_detail(session, tenant, item, version)
        observed.append((version, detail.display_name))
        return detail
    monkeypatch.setattr(owning_i, "exact_item_detail", record_exact)
    assert country.prepare(new_request).context_version == 2
    assert f["compliance_repo"].prepare(old_request).context_version == 1
    assert observed == [(2, "Changed confirmed input"), (1, "Generic item")]
