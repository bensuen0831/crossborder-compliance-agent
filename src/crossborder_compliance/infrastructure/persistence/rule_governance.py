"""V1 validation hooks inside the existing Admin/Registry publish transaction."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, select

from crossborder_compliance.domain.rules import (
    ComplianceRule,
    RuleContract,
    RuleTestCase,
    run_rule_tests,
    validate_conflicts,
)
from crossborder_compliance.infrastructure.persistence import metadata_models as m


def contract_values(payload):
    if "runtime_contract" not in payload:
        return {}
    contract = RuleContract.model_validate(payload["runtime_contract"])
    return {
        "runtime_contract_json": contract.model_dump(mode="json"),
        "governance_json": {},
        "safe_dsl_json": contract.conditions,
        "scope_json": contract.scope.model_dump(mode="json"),
        "priority": contract.priority,
        "effective_from": contract.effective_from,
        "effective_to": contract.effective_to,
    }


def replace_tests(session, row, payload):
    if row.runtime_contract_json is None:
        return  # Frozen config-only V0; never accepted by formal runtime.
    cases = tuple(RuleTestCase.model_validate(t) for t in payload.get("tests", []))
    session.execute(
        delete(m.RuleTestCaseEntity).where(
            m.RuleTestCaseEntity.tenant_id == row.tenant_id,
            m.RuleTestCaseEntity.rule_version_id == row.rule_version_id,
        )
    )
    for case in cases:
        data = case.model_dump(mode="json")
        session.add(
            m.RuleTestCaseEntity(
                rule_test_case_id=str(uuid4()),
                tenant_id=row.tenant_id,
                rule_version_id=row.rule_version_id,
                fact_context_json=data.pop("facts"),
                expected_result_json=data,
            )
        )


def as_rule(row):
    governance = row.governance_json or {}
    return ComplianceRule(
        rule_id=UUID(row.rule_definition_id),
        rule_version_id=UUID(row.rule_version_id),
        tenant_id=UUID(row.tenant_id),
        version=row.version_no,
        contract=RuleContract.model_validate(row.runtime_contract_json),
        lifecycle=row.lifecycle_status,
        approved_by=governance.get("approved_by"),
        published_by=governance.get("published_by"),
    )


def validate_version(session, row):
    if row.runtime_contract_json is None:
        raise ValueError("legacy config-only rule has no executable V1 contract")
    c = RuleContract.model_validate(row.runtime_contract_json)
    from crossborder_compliance.domain.classification import ClassificationScheme
    from crossborder_compliance.infrastructure.persistence import models as b

    for jurisdiction in c.scope.jurisdiction_ids:
        if (
            session.scalar(
                select(b.JurisdictionEntity).where(
                    b.JurisdictionEntity.tenant_id == row.tenant_id,
                    b.JurisdictionEntity.jurisdiction_id == str(jurisdiction),
                )
            )
            is None
        ):
            raise LookupError("rule reference not found")
    for action in c.actions:
        scheme_row = session.scalar(
            select(m.ClassificationSchemeVersionEntity).where(
                m.ClassificationSchemeVersionEntity.tenant_id == row.tenant_id,
                m.ClassificationSchemeVersionEntity.scheme_version_id
                == str(action.scheme_version_id),
                m.ClassificationSchemeVersionEntity.lifecycle_status.in_(["APPROVED", "ACTIVE"]),
            )
        )
        if scheme_row is None or not scheme_row.applicability_json.get("phase1h"):
            raise LookupError("rule scheme reference not found")
        scheme = ClassificationScheme.model_validate(
            {
                **scheme_row.applicability_json["phase1h"],
                "scheme_id": scheme_row.scheme_id,
                "scheme_version_id": scheme_row.scheme_version_id,
                "tenant_id": scheme_row.tenant_id,
                "version": scheme_row.version_no,
                "lifecycle": scheme_row.lifecycle_status,
            }
        )
        if not set(c.scope.jurisdiction_ids) <= set(scheme.jurisdiction_ids):
            raise ValueError("rule jurisdiction outside scheme")
        if not set(action.category_ids) <= {v.category_id for v in scheme.categories} or (
            action.level_id and action.level_id not in {v.level_id for v in scheme.levels}
        ):
            raise ValueError("rule classification target outside versioned scheme")
    for basis in c.legal_basis_ids:
        if (
            session.scalar(
                select(b.LegalBasisItemEntity).where(
                    b.LegalBasisItemEntity.tenant_id == row.tenant_id,
                    b.LegalBasisItemEntity.legal_basis_id == str(basis),
                    b.LegalBasisItemEntity.jurisdiction_id.in_(
                        [str(v) for v in c.scope.jurisdiction_ids]
                    ),
                )
            )
            is None
        ):
            raise LookupError("rule legal basis reference not found")
    cases = session.scalars(
        select(m.RuleTestCaseEntity).where(
            m.RuleTestCaseEntity.tenant_id == row.tenant_id,
            m.RuleTestCaseEntity.rule_version_id == row.rule_version_id,
        )
    ).all()
    run_rule_tests(
        c,
        tuple(
            RuleTestCase.model_validate({"facts": t.fact_context_json, **t.expected_result_json})
            for t in cases
        ),
    )
    peers = session.scalars(
        select(m.RuleVersionEntity).where(
            m.RuleVersionEntity.tenant_id == row.tenant_id,
            m.RuleVersionEntity.lifecycle_status.in_(["APPROVED", "ACTIVE"]),
            m.RuleVersionEntity.rule_definition_id != row.rule_definition_id,
            m.RuleVersionEntity.runtime_contract_json.is_not(None),
        )
    ).all()
    validate_conflicts((as_rule(row), *(as_rule(p) for p in peers)))
    return {"status": "PASS", "tests": len(cases), "ast": "VALIDATED", "conflicts": "CLEAR"}


def transition_gate(session, row, target, actor):
    if row.runtime_contract_json is None:
        return  # Retained 1C configuration behavior, not V1 execution permission.
    state = dict(row.governance_json or {})
    if target in {"PENDING_REVIEW", "APPROVED", "ACTIVE"}:
        # Serialize publication/conflict checks for this tenant using its existing identity row.
        from crossborder_compliance.infrastructure.persistence.models import TenantEntity

        session.scalar(
            select(TenantEntity).where(TenantEntity.tenant_id == row.tenant_id).with_for_update()
        )
        state["validation"] = validate_version(session, row)
    if target == "PENDING_REVIEW":
        state["submitted_by"] = actor
    if target == "APPROVED":
        if not state.get("submitted_by") or state["submitted_by"] == actor:
            raise ValueError("independent rule reviewer is required")
        state["approved_by"] = actor
    if target == "ACTIVE":
        if not state.get("approved_by"):
            raise ValueError("rule requires durable review before publication")
        state["published_by"] = actor
    if target == "DRAFT":
        state = {}
    row.governance_json = state
