"""Owning R1 contract: real PostgreSQL, published schemes/rules, exact pins."""

# ruff: noqa: F401,F811 -- shared real PostgreSQL fixture
from datetime import date
from uuid import UUID, uuid4

import pytest
from phase1h_fixtures import contract
from sqlalchemy import delete, select
from test_phase1h_postgres import execute, foundation, payload, pin, publish

from crossborder_compliance.application.classification_services import ClassificationService
from crossborder_compliance.infrastructure.persistence import (
    context_models as c,
)
from crossborder_compliance.infrastructure.persistence import (
    metadata_models as m,
)
from crossborder_compliance.infrastructure.persistence import (
    models as b,
)

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def multi(foundation):
    f = foundation
    destination = uuid4()
    f["insert"](
        b.JurisdictionEntity, jurisdiction_id=destination, code=str(destination), name="Destination"
    )
    f["insert"](
        c.JurisdictionContextEntity,
        jurisdiction_context_id=uuid4(),
        project_id=f["project"],
        jurisdiction_id=destination,
        context_type="DESTINATION",
        location_precision="EXACT_CANONICAL",
        source="USER_INPUT",
        confidence=1,
        validation_status="VALIDATED",
        version=1,
    )
    draft = f["schemes"].create_version(
        f["scheme"],
        payload={
            "applicability": {
                "phase1h": {
                    "jurisdiction_ids": [str(f["jurisdiction"]), str(destination)],
                    "categories": [{"code": "CATEGORY"}],
                    "levels": [],
                }
            }
        },
    )
    from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
        PostgresClassificationAdminRepository,
    )

    publish(f["schemes"], draft, PostgresClassificationAdminRepository(f["sf"], f["reviewer"]))
    f["scheme_version"] = UUID(draft["version_id"])
    a = contract(f["scheme_version"], f["jurisdiction"], f["category"])
    ra = f["rules"].create_version(f["rule"], payload(a))
    publish(f["rules"], ra, f["review_rules"])
    rb = f["rules"].create_draft(
        code=str(uuid4()),
        display_name="Destination rule",
        payload=payload(contract(f["scheme_version"], destination, f["category"])),
    )
    publish(f["rules"], rb, f["review_rules"])
    f.update(destination=destination, ra=ra, rb=rb, contract=a)
    return f


def initialize(f):
    return f["repo"].pin_configurations(f["project"], f["snapshot"])


def classify(f, jurisdiction):
    return ClassificationService(f["repo"]).execute(
        project_id=f["project"],
        snapshot_id=f["snapshot"],
        data_item_id=f["item"],
        jurisdiction_id=jurisdiction,
        scheme_version_id=f["scheme_version"],
    )


def pins(f):
    with f["sf"]() as s:
        return s.scalars(
            select(m.AnalysisSnapshotRegistryPinEntity).where(
                m.AnalysisSnapshotRegistryPinEntity.tenant_id == str(f["tenant"]),
                m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(f["snapshot"]),
            )
        ).all()


def test_two_jurisdictions_complete_rule_union_and_distinct_execution_identity(multi):
    f = multi
    bound = initialize(f)
    assert {x.jurisdiction_id for x in bound} == {f["jurisdiction"], f["destination"]}
    assert {x.scheme_version_id for x in bound} == {f["scheme_version"]}
    assert {p.version_id for p in pins(f) if p.pin_type == "RULE_V1"} == {
        f["ra"]["version_id"],
        f["rb"]["version_id"],
    }
    a, d = classify(f, f["jurisdiction"]), classify(f, f["destination"])
    assert (
        a.result.jurisdiction_id == f["jurisdiction"]
        and d.result.jurisdiction_id == f["destination"]
    )
    assert {h.rule_version_id for h in a.rule_hits} == {UUID(f["ra"]["version_id"])}
    assert {h.rule_version_id for h in d.rule_hits} == {UUID(f["rb"]["version_id"])}
    assert all(h.jurisdiction_id == f["destination"] for h in d.rule_hits)
    assert a.result.classification_result_id != d.result.classification_result_id
    assert classify(f, f["jurisdiction"]).result == a.result
    assert classify(f, f["destination"]).result == d.result
    assert initialize(f) == bound
    with f["sf"]() as s:
        active = s.scalars(
            select(m.ClassificationSchemeVersionEntity).where(
                m.ClassificationSchemeVersionEntity.tenant_id == str(f["tenant"]),
                m.ClassificationSchemeVersionEntity.lifecycle_status == "ACTIVE",
            )
        ).all()
        assert len(active) == 1


@pytest.mark.parametrize(
    "problem", ["missing", "ambiguous", "expired", "scope", "multiple_schemes"]
)
def test_configuration_gap_or_conflict_is_atomic(multi, problem):
    f = multi
    with f["sf"]() as s, s.begin():
        row = s.scalar(
            select(m.ClassificationBindingEntity).where(
                m.ClassificationBindingEntity.tenant_id == str(f["tenant"]),
                m.ClassificationBindingEntity.scheme_version_id == str(f["scheme_version"]),
                m.ClassificationBindingEntity.jurisdiction_id == str(f["destination"]),
            )
        )
        if problem == "missing":
            row.status = "DISABLED"
        elif problem == "expired":
            row.effective_to = date(2020, 1, 1)
        elif problem == "scope":
            row.industry_ref = "unselected-governed-industry"
        elif problem == "ambiguous":
            s.add(
                m.ClassificationBindingEntity(
                    classification_binding_id=str(uuid4()),
                    tenant_id=str(f["tenant"]),
                    scheme_version_id=str(f["scheme_version"]),
                    jurisdiction_id=str(f["destination"]),
                    priority=row.priority,
                )
            )
        else:
            old = s.scalar(
                select(m.ClassificationSchemeVersionEntity).where(
                    m.ClassificationSchemeVersionEntity.tenant_id == str(f["tenant"]),
                    m.ClassificationSchemeVersionEntity.lifecycle_status == "SUPERSEDED",
                )
            )
            old.lifecycle_status = "ACTIVE"
    with pytest.raises(ValueError, match="CLASSIFICATION_CONFIGURATION_(GAP|CONFLICT)"):
        initialize(f)
    assert not pins(f), "failed batch must not leave a partial binding/rule closure"


def test_unpinned_or_implicit_execution_rejected(multi):
    f = multi
    initialize(f)
    with pytest.raises(ValueError, match="pinned jurisdiction"):
        execute(f)
    with pytest.raises(ValueError, match="pinned jurisdiction"):
        classify(f, uuid4())


def test_future_rule_binding_and_scheme_changes_do_not_change_s1(multi):
    f = multi
    binding = initialize(f)
    first = classify(f, f["jurisdiction"]).result
    original_pins = {(p.pin_type, p.logical_key, p.version_id) for p in pins(f)}
    future_payload = payload(
        contract(
            f["scheme_version"],
            f["jurisdiction"],
            f["category"],
            conditions={"op": "gte", "field": "count", "value": 4},
        )
    )
    future_payload["tests"][0]["facts"]["count"] = 4
    future = f["rules"].create_version(f["rule"], future_payload)
    publish(f["rules"], future, f["review_rules"])
    with f["sf"]() as s, s.begin():
        for row in s.scalars(
            select(m.ClassificationBindingEntity).where(
                m.ClassificationBindingEntity.tenant_id == str(f["tenant"])
            )
        ):
            row.status = "DISABLED"
            row.effective_to = date(2020, 1, 1)
    scheme = f["schemes"].create_version(
        f["scheme"],
        payload={
            "applicability": {
                "phase1h": {
                    "jurisdiction_ids": [str(f["jurisdiction"]), str(f["destination"])],
                    "categories": [{"code": "CATEGORY"}],
                    "levels": [],
                }
            }
        },
    )
    from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
        PostgresClassificationAdminRepository,
    )

    publish(f["schemes"], scheme, PostgresClassificationAdminRepository(f["sf"], f["reviewer"]))
    assert initialize(f) == binding  # Idempotent replay never consults live config.
    assert classify(f, f["jurisdiction"]).result == first
    assert {(p.pin_type, p.logical_key, p.version_id) for p in pins(f)} == original_pins


def test_legacy_single_jurisdiction_historical_execution(foundation):
    f = foundation
    pin(f)
    original = execute(f).result
    assert execute(f).result == original
    assert original.jurisdiction_id == f["jurisdiction"]


def test_database_rejects_competing_same_jurisdiction_result(multi):
    from sqlalchemy.exc import IntegrityError

    f = multi
    initialize(f)
    original = classify(f, f["jurisdiction"]).result
    with pytest.raises(IntegrityError, match="uq_formal_classification_snapshot"):
        with f["sf"]() as s, s.begin():
            row = s.get(b.ClassificationResultEntity, str(original.classification_result_id))
            values = {col.name: getattr(row, col.name) for col in row.__table__.columns}
            values["classification_result_id"] = str(uuid4())
            s.add(b.ClassificationResultEntity(**values))
    assert classify(f, f["jurisdiction"]).result == original
