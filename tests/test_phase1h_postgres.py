"""Real PostgreSQL governance, scope, canonical persistence and snapshot history."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from phase1h_fixtures import cases, contract
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from crossborder_compliance.application.classification_services import ClassificationService
from crossborder_compliance.application.metadata_services import AdminAuthorizationError
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.classification_repository import (
    PostgresFormalClassificationRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.rule_admin_repository import (
    PostgresRuleAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresClassificationAdminRepository,
)

pytestmark = pytest.mark.runtime_smoke


def admin_context(tenant, actor):
    return RepositoryContext.user(
        tenant, actor, {"metadata:admin", "metadata:review", "metadata:publish"}
    )


def publish(repository, version, reviewer):
    ident = UUID(version["version_id"])
    value = repository.transition(ident, target_status="PENDING_REVIEW", expected_record_version=1)
    value = reviewer.transition(
        ident, target_status="APPROVED", expected_record_version=value["record_version"]
    )
    return repository.transition(
        ident, target_status="ACTIVE", expected_record_version=value["record_version"]
    )


def payload(con):
    return {
        "runtime_contract": con.model_dump(mode="json"),
        "tests": [case.model_dump(mode="json") for case in cases(con)],
    }


@pytest.fixture
def foundation():
    url = get_settings().database_url
    assert url.startswith("postgresql"), "Phase 1H integration requires real PostgreSQL"
    sf = build_session_factory(url)[1]
    ids = {
        key: uuid4()
        for key in (
            "tenant",
            "project",
            "project_version",
            "snapshot",
            "item",
            "jurisdiction",
            "document",
            "document_version",
            "trace",
            "fact",
            "evidence",
            "run",
        )
    }
    tenant = str(ids["tenant"])

    def insert(model, **kwargs):
        with sf() as s, s.begin():
            s.add(
                model(
                    tenant_id=tenant,
                    **{k: str(v) if isinstance(v, UUID) else v for k, v in kwargs.items()},
                )
            )

    insert(b.TenantEntity, name="Phase 1H fixture")
    insert(b.ProjectEntity, project_id=ids["project"], name="Track A")
    insert(
        b.ProjectVersionEntity,
        project_version_id=ids["project_version"],
        project_id=ids["project"],
        version_no=1,
        intake_json={},
    )
    insert(
        b.JurisdictionEntity,
        jurisdiction_id=ids["jurisdiction"],
        code=str(ids["jurisdiction"]),
        name="Scheme jurisdiction",
    )
    insert(
        b.DocumentEntity,
        document_id=ids["document"],
        project_id=ids["project"],
        name="Authorized source",
        document_type="UPLOADED",
    )
    insert(
        b.DocumentVersionEntity,
        document_version_id=ids["document_version"],
        document_id=ids["document"],
        version_no=1,
        storage_ref="fixture://source",
        content_hash="a" * 64,
    )
    insert(
        b.SourceTraceRefEntity,
        source_trace_ref_id=ids["trace"],
        document_version_id=ids["document_version"],
    )
    insert(
        b.DataItemEntity,
        data_item_id=ids["item"],
        project_id=ids["project"],
        name="Formal item",
        canonical_type_ref="TYPE",
        source_trace_ref_id=ids["trace"],
    )
    insert(
        c.DataItemResolutionDetailEntity,
        data_item_id=ids["item"],
        display_name="Formal item",
        confidence=0.95,
        validation_status="VALIDATED",
        version=1,
    )
    insert(
        c.DataItemSourceTraceLinkEntity,
        data_item_source_trace_link_id=uuid4(),
        data_item_id=ids["item"],
        source_trace_ref_id=ids["trace"],
    )
    insert(
        c.BusinessFactEntity,
        fact_id=ids["fact"],
        project_id=ids["project"],
        fact_type="COUNT",
        normalized_key="3",
        normalized_value_json=3,
        resolution_method="DETERMINISTIC",
        confidence=0.95,
        validation_status="VALIDATED",
        version=1,
    )
    insert(
        b.EvidenceReferenceEntity,
        evidence_id=ids["evidence"],
        evidence_type="DOCUMENT",
        source_ref="fixture://source",
        source_trace_ref_id=ids["trace"],
        validation_status="VALID",
    )
    insert(
        c.ContextResolutionRunEntity,
        context_resolution_run_id=ids["run"],
        project_id=ids["project"],
        version=1,
        product_context_version=1,
        data_inventory_version=1,
        data_flow_version=1,
        confidence=0.95,
    )
    insert(
        c.JurisdictionContextEntity,
        jurisdiction_context_id=uuid4(),
        project_id=ids["project"],
        jurisdiction_id=ids["jurisdiction"],
        context_type="PROCESSING",
        location_precision="COUNTRY",
        source="FORMAL",
        confidence=1,
        validation_status="VALIDATED",
        version=1,
    )
    insert(
        b.AnalysisSnapshotEntity,
        analysis_snapshot_id=ids["snapshot"],
        project_version_id=ids["project_version"],
        snapshot_version="1",
        analysis_as_of_date=date(2026, 1, 1),
        provenance_json={},
    )
    insert(
        c.AnalysisSnapshotContextPinEntity,
        analysis_snapshot_context_pin_id=uuid4(),
        analysis_snapshot_id=ids["snapshot"],
        project_id=ids["project"],
        context_resolution_run_id=ids["run"],
        context_resolution_version=1,
        product_context_version=1,
        data_inventory_version=1,
        data_flow_version=1,
    )
    writer = admin_context(ids["tenant"], "writer")
    reviewer = admin_context(ids["tenant"], "reviewer")
    schemes = PostgresClassificationAdminRepository(sf, writer)
    scheme_draft = schemes.create_draft(
        code=str(uuid4()),
        display_name="Versioned scheme",
        payload={
            "applicability": {
                "phase1h": {
                    "jurisdiction_ids": [str(ids["jurisdiction"])],
                    "categories": [{"code": "CATEGORY"}],
                    "levels": [],
                }
            }
        },
    )
    publish(schemes, scheme_draft, PostgresClassificationAdminRepository(sf, reviewer))
    detail = schemes.get_detail(UUID(scheme_draft["version_id"]))
    ids["scheme"] = UUID(scheme_draft["definition_id"])
    ids["scheme_version"] = UUID(scheme_draft["version_id"])
    ids["category"] = UUID(detail["applicability"]["phase1h"]["categories"][0]["category_id"])
    rules = PostgresRuleAdminRepository(sf, writer)
    rule_contract = contract(ids["scheme_version"], ids["jurisdiction"], ids["category"])
    rule_draft = rules.create_draft(
        code=str(uuid4()), display_name="Formal rule", payload=payload(rule_contract)
    )
    review_rules = PostgresRuleAdminRepository(sf, reviewer)
    publish(rules, rule_draft, review_rules)
    ids["rule"], ids["rule_version"] = (
        UUID(rule_draft["definition_id"]),
        UUID(rule_draft["version_id"]),
    )
    runtime = RepositoryContext.user(
        ids["tenant"],
        "reader",
        {"classification:execute", "classification:read", f"project:{ids['project']}:classify"},
    )
    repo = PostgresFormalClassificationRepository(sf, runtime)
    return dict(
        ids,
        sf=sf,
        insert=insert,
        writer=writer,
        reviewer=reviewer,
        rules=rules,
        review_rules=review_rules,
        schemes=schemes,
        contract=rule_contract,
        repo=repo,
        runtime=runtime,
    )


def execute(f):
    return ClassificationService(f["repo"]).execute(
        project_id=f["project"],
        snapshot_id=f["snapshot"],
        data_item_id=f["item"],
        scheme_version_id=f["scheme_version"],
    )


def pin(f):
    return f["repo"].pin_configuration(f["project"], f["snapshot"], f["scheme_version"])


def test_authorized_formal_classification_persists_one_canonical_result(foundation):
    f = foundation
    with pytest.raises(ValueError, match="pinned"):
        execute(f)
    assert pin(f)["rule_version_ids"] == [str(f["rule_version"])]
    out = execute(f)
    assert out.status == "CLASSIFIED"
    assert f["repo"].get_result(out.result.classification_result_id)["evidence_ids"] == [
        str(f["evidence"])
    ]
    with f["sf"]() as s:
        result = s.get(b.ClassificationResultEntity, str(out.result.classification_result_id))
        assert result.scheme_version_id == str(f["scheme_version"])
        hit = s.get(b.RuleHitEntity, str(out.result.rule_hit_ids[0]))
        assert hit.formal_provenance_json["matched_fact_refs"] == [str(f["fact"])]
        assert hit.formal_provenance_json["analysis_snapshot_id"] == str(f["snapshot"])
    assert execute(f).result.classification_result_id == out.result.classification_result_id


def test_publish_atomic_gate_tests_review_outbox_and_immutability(foundation):
    f = foundation
    wrong = payload(f["contract"])
    wrong["tests"][0]["expected_match"] = False
    draft = f["rules"].create_version(f["rule"], wrong)
    ident = UUID(draft["version_id"])
    with pytest.raises(ValueError, match="test failed"):
        f["rules"].transition(ident, target_status="PENDING_REVIEW", expected_record_version=1)
    with f["sf"]() as s:
        assert s.get(m.RuleVersionEntity, str(ident)).lifecycle_status == "DRAFT"
        assert not s.scalar(
            select(m.AdminPublishRecordEntity).where(
                m.AdminPublishRecordEntity.version_id == str(ident)
            )
        )
        assert not s.scalar(
            select(m.RegistrySyncEventEntity).where(
                m.RegistrySyncEventEntity.version_id == str(ident)
            )
        )
    f["rules"].update_draft(ident, payload=payload(f["contract"]), expected_record_version=1)
    f["rules"].transition(ident, target_status="PENDING_REVIEW", expected_record_version=2)
    with pytest.raises(ValueError, match="independent"):
        f["rules"].transition(ident, target_status="APPROVED", expected_record_version=3)
    f["review_rules"].transition(ident, target_status="APPROVED", expected_record_version=3)
    f["rules"].transition(ident, target_status="ACTIVE", expected_record_version=4)
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(m.AdminPublishRecordEntity)
                .where(m.AdminPublishRecordEntity.version_id == str(ident))
            )
            == 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(m.RegistrySyncEventEntity)
                .where(m.RegistrySyncEventEntity.version_id == str(ident))
            )
            == 1
        )
    with pytest.raises(DBAPIError, match="immutable"):
        with f["sf"]() as s, s.begin():
            row = s.get(m.RuleVersionEntity, str(ident))
            row.runtime_contract_json = {**row.runtime_contract_json, "severity": "LOW"}


def test_historical_rule_pin_survives_new_rule_publication(foundation):
    f = foundation
    pin(f)
    first = execute(f)
    new_contract = f["contract"].model_copy(
        update={"conditions": {"op": "gt", "field": "count", "value": 3}}
    )
    value = payload(new_contract)
    value["tests"] = [
        {
            "facts": {"count": 3},
            "expected_match": False,
            "expected_actions": [],
            "expected_severity": None,
            "expected_evidence_requirement": [],
        }
    ]
    draft = f["rules"].create_version(f["rule"], value)
    publish(f["rules"], draft, f["review_rules"])
    assert execute(f).result.scheme_version_id == first.result.scheme_version_id
    _, _, rules = f["repo"].prepare(f["project"], f["snapshot"], f["item"], f["scheme_version"])
    assert rules[0].rule_version_id == f["rule_version"] and rules[0].lifecycle == "SUPERSEDED"
    assert pin(f)["rule_version_ids"] == [str(f["rule_version"])]


@pytest.mark.parametrize(
    "mode", ["tenant", "project_permission", "operation_permission", "snapshot", "item"]
)
def test_runtime_isolation(foundation, mode):
    f = foundation
    pin(f)
    context = f["runtime"]
    if mode == "tenant":
        context = RepositoryContext.user(uuid4(), "foreign", set(context.permission.scopes))
    elif mode == "project_permission":
        context = RepositoryContext.user(f["tenant"], "foreign", {"classification:execute"})
    elif mode == "operation_permission":
        context = RepositoryContext.user(
            f["tenant"], "foreign", {f"project:{f['project']}:classify"}
        )
    repo = PostgresFormalClassificationRepository(f["sf"], context)
    with pytest.raises(LookupError):
        repo.prepare(
            f["project"],
            uuid4() if mode == "snapshot" else f["snapshot"],
            uuid4() if mode == "item" else f["item"],
            f["scheme_version"],
        )


def test_evidence_validation_fail_closed_and_missing_data_policy(foundation):
    f = foundation
    pin(f)
    with f["sf"]() as s, s.begin():
        s.get(b.EvidenceReferenceEntity, str(f["evidence"])).validation_status = "INVALID"
    out = execute(f)
    assert out.status == "INSUFFICIENT_INPUT" and out.result is None
    out = ClassificationService(f["repo"]).execute(
        project_id=f["project"],
        snapshot_id=f["snapshot"],
        data_item_id=None,
        scheme_version_id=f["scheme_version"],
    )
    assert out.status == "NOT_APPLICABLE" and out.result is None


def test_admin_privilege_and_conflict_gate(foundation):
    f = foundation
    ordinary = PostgresRuleAdminRepository(f["sf"], RepositoryContext.user(f["tenant"], "ordinary"))
    with pytest.raises(AdminAuthorizationError):
        ordinary.create_version(f["rule"], payload(f["contract"]))
    action = f["contract"].actions[0].model_copy(update={"reason_code": "CONFLICTING_REASON"})
    con = f["contract"].model_copy(update={"actions": (action,)})
    draft = f["rules"].create_draft(
        code=str(uuid4()), display_name="Conflict", payload=payload(con)
    )
    with pytest.raises(ValueError, match="ambiguous"):
        f["rules"].transition(
            UUID(draft["version_id"]), target_status="PENDING_REVIEW", expected_record_version=1
        )


def test_published_tests_scheme_and_formal_result_are_immutable(foundation):
    f = foundation
    pin(f)
    out = execute(f)
    with pytest.raises(DBAPIError, match="immutable"):
        with f["sf"]() as s, s.begin():
            test = s.scalar(
                select(m.RuleTestCaseEntity).where(
                    m.RuleTestCaseEntity.rule_version_id == str(f["rule_version"])
                )
            )
            test.fact_context_json = {"count": 99}
    with pytest.raises(DBAPIError, match="immutable"):
        with f["sf"]() as s, s.begin():
            scheme = s.get(m.ClassificationSchemeVersionEntity, str(f["scheme_version"]))
            scheme.applicability_json = {"phase1h": {}}
    with pytest.raises(DBAPIError, match="immutable"):
        with f["sf"]() as s, s.begin():
            s.get(
                b.ClassificationResultEntity, str(out.result.classification_result_id)
            ).confidence = 0.1


def test_evidence_revocation_cannot_leak_a_saved_result(foundation):
    f = foundation
    pin(f)
    out = execute(f)
    with f["sf"]() as s, s.begin():
        s.get(b.EvidenceReferenceEntity, str(f["evidence"])).validation_status = "INVALID"
    with pytest.raises(LookupError):
        f["repo"].get_result(out.result.classification_result_id)


def test_schema_revision_guard_and_no_data_do_not_write_classification(foundation):
    f = foundation
    pin(f)
    out = ClassificationService(f["repo"]).execute(
        project_id=f["project"],
        snapshot_id=f["snapshot"],
        data_item_id=None,
        scheme_version_id=f["scheme_version"],
    )
    assert out.result is None
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.ClassificationResultEntity)
                .where(b.ClassificationResultEntity.tenant_id == str(f["tenant"]))
            )
            == 0
        )
