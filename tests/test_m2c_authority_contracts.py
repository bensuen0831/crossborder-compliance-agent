"""Closed v2 authority, safe predicates and implementation-path counterexamples."""

from uuid import uuid4

import pytest
from phase1j_fixtures import decision_fixture
from pydantic import ValidationError
from test_m2c_authority_postgres import condition

from crossborder_compliance.application.formal_result_services import FormalAuthorityRequest
from crossborder_compliance.domain.decision_contracts import PinRef, result_digest
from crossborder_compliance.domain.decision_engine import (
    candidates,
    final_path,
    obligations,
    recommendation,
    risks,
)
from crossborder_compliance.domain.decision_policies import ConditionPolicy, ObligationPolicy
from crossborder_compliance.domain.formal_result_contracts import AuthorityIdentity
from crossborder_compliance.domain.formal_result_engine import (
    PinnedAuthorityPolicy,
    PreparedAuthorityInput,
    cross_border_assessment,
)
from crossborder_compliance.domain.formal_result_policies import (
    CrossBorderAssessmentPolicy,
    DocumentRequirementEntry,
)


def prepared():
    original = decision_fixture()
    original_policy = original.policy("OBLIGATION_POLICY")
    entry = original_policy.config.entries[0]
    updated = entry.model_copy(
        update={"fulfillment_conditions": (ConditionPolicy.model_validate(condition(30)),)}
    )
    policy = ObligationPolicy.model_validate(
        {
            **original_policy.config.model_dump(mode="json"),
            "entries": [updated.model_dump(mode="json")],
        }
    )
    original = original.model_copy(
        update={
            "policies": tuple(
                p.model_copy(update={"config": policy}) if p.pin.kind == "OBLIGATION_POLICY" else p
                for p in original.policies
            )
        }
    )
    obligation = obligations(original)
    candidate = candidates(original, obligation)
    risk = risks(original, candidate)
    rec = recommendation(original, candidate, risk)
    final = final_path(original, obligation, candidate, risk, rec)
    pin = PinRef(
        pin_id=uuid4(),
        kind="CROSS_BORDER_ASSESSMENT_POLICY",
        object_id=uuid4(),
        version_id=uuid4(),
        version_no=1,
    )
    cfg = CrossBorderAssessmentPolicy(
        effective_from=original.identity.analysis_as_of_date,
        jurisdiction_ids=original.identity.jurisdiction_ids,
        obligation_policy_id=original_policy.pin.object_id,
        transfer_legally_possible=condition(3),
        prerequisites=[dict(requirement_id=entry.entry_id, kind="APPROVAL")],
    )
    return PreparedAuthorityInput(
        identity=AuthorityIdentity(**original.identity.model_dump()),
        obligation=obligation,
        final_path=final,
        facts=original.facts,
        support=original.support,
        source_jurisdiction_ids=original.identity.jurisdiction_ids,
        destination_jurisdiction_ids=original.identity.jurisdiction_ids,
        policies=(PinnedAuthorityPolicy(pin=pin, config=cfg),),
        pins=(*original.pins, pin),
        evidence_sufficient=True,
        context_digest="a" * 64,
        prepared_at=original.prepared_at,
        actor_ref=original.actor_ref,
        request_id="c0",
        correlation_id="c0",
    )


@pytest.mark.parametrize("status", ["CONDITIONAL_PROPOSAL", "NO_VIABLE_PATH", "PROPOSED"])
def test_final_path_status_never_supplies_legal_transfer_authority(status):
    x = prepared()
    baseline = cross_border_assessment(x)
    alternative = x.final_path.items[0].model_copy(
        update={"status": status, "selected_candidate_path_id": None, "actions": ()}
    )
    changed = x.model_copy(
        update={
            "final_path": x.final_path.model_copy(update={"items": (alternative,), "confidence": 0})
        }
    )
    actual = cross_border_assessment(changed)
    assert result_digest(actual) == result_digest(baseline)
    assert actual.items[0].status == "CONDITIONAL_TRANSFER_ALLOWED"
    assert "LEGAL_PROHIBITION" not in actual.items[0].reason_codes


def test_no_viable_path_does_not_establish_prohibition_when_evidence_missing():
    x = prepared().model_copy(update={"evidence_sufficient": False})
    result = cross_border_assessment(x)
    assert result.review_required and result.items[0].status == "REVIEW_REQUIRED"
    assert result.reason_codes == ("EVIDENCE_INSUFFICIENT",)


def test_missing_non_transfer_predicate_input_cannot_assert_permission():
    x = prepared()
    p = x.policies[0]
    cfg = CrossBorderAssessmentPolicy.model_validate(
        {**p.config.model_dump(mode="json"), "non_transfer_condition": condition(field="missing")}
    )
    result = cross_border_assessment(
        x.model_copy(update={"policies": (p.model_copy(update={"config": cfg}),)})
    )
    assert result.review_required and result.reason_codes == ("EVIDENCE_INSUFFICIENT",)


def test_template_is_not_a_legal_trigger_and_locales_are_governed():
    with pytest.raises(ValidationError):
        DocumentRequirementEntry(
            entry_id=uuid4(),
            document_type_code="SCC",
            name="SCC",
            requirement_level="REQUIRED",
            template_binding_id=uuid4(),
        )
    with pytest.raises(ValidationError):
        DocumentRequirementEntry(
            entry_id=uuid4(),
            document_type_code="SCC",
            name="SCC",
            requirement_level="REQUIRED",
            cross_border_statuses=["DIRECT_TRANSFER_ALLOWED"],
            localized_display_names={"invalid": "label"},
        )


def test_client_cannot_inject_legal_result_policy_or_tenant():
    base = dict(
        project_id=uuid4(),
        analysis_snapshot_id=uuid4(),
        subject_type="DATA_ITEM",
        subject_id=uuid4(),
        stage_kind="CROSS_BORDER",
        idempotency_key="request",
    )
    for field in ("tenant_id", "policy_version_id", "status", "risk_score"):
        with pytest.raises(ValidationError):
            FormalAuthorityRequest(**base, **{field: str(uuid4())})
    with pytest.raises(ValidationError):
        FormalAuthorityRequest(**base, final_path_result_id=uuid4())
