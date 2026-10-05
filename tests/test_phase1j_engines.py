from decimal import Decimal
from uuid import uuid4

import pytest
from phase1j_fixtures import decision_fixture
from test_phase1j_contracts import risk_policy

from crossborder_compliance.domain.decision_contracts import result_digest
from crossborder_compliance.domain.decision_engine import (
    candidates,
    final_path,
    obligations,
    recommendation,
    risks,
)
from crossborder_compliance.domain.decision_policies import ConditionPolicy, RiskPolicy
from crossborder_compliance.domain.decision_risk import evaluate_policy_values


def pipeline(f):
    o = obligations(f)
    c = candidates(f, o)
    r = risks(f, c)
    a = recommendation(f, c, r)
    return o, c, r, a, final_path(f, o, c, r, a)


def replace_policy(f, kind, **changes):
    policies = tuple(
        p.model_copy(
            update={"config": type(p.config).model_validate({**p.config.model_dump(), **changes})}
        )
        if p.pin.kind == kind
        else p
        for p in f.policies
    )
    return f.model_copy(update={"policies": policies})


def test_legal_risk_path_order_and_no_fulfillment_fabrication():
    f = decision_fixture(risk_value=95)
    o, c, r, a, final = pipeline(f)
    assert o.items[0].legal_effect == "REQUIRED"
    assert o.items[0].fulfillment_state == "UNKNOWN"
    assert c.items[0].legal_viability == "VIABLE"
    assert r.items[0].risk_level == "HIGH"
    assert a.items[0].status == "RECOMMENDED"
    assert final.items[0].status == "CONDITIONAL_PROPOSAL"
    assert not final.items[0].actions[0].performed
    assert final.items[0].residual_risk_ref.item_id == r.items[0].risk_assessment_id


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "LOW"),
        (Decimal("49.994"), "LOW"),
        (Decimal("49.995"), "HIGH"),
        (50, "HIGH"),
        (100, "HIGH"),
        (None, "UNKNOWN"),
        (-1, "UNKNOWN"),
        (True, "UNKNOWN"),
    ],
)
def test_decimal_bands_exact_boundaries_and_missing(value, expected):
    score, band, _ = evaluate_policy_values(
        risk_policy(), {} if value is None else {"count": value}
    )
    assert band == expected
    if value is None:
        assert score is None


def test_exact_tie_never_uses_uuid_or_input_order():
    f = decision_fixture(paths=2)
    first = pipeline(f)
    second = pipeline(
        f.model_copy(
            update={"facts": tuple(reversed(f.facts)), "policies": tuple(reversed(f.policies))}
        )
    )
    for records in (first, second):
        assert records[3].items[0].status == "TIED"
        assert records[3].items[0].selected_candidate_id is None
        assert records[4].items[0].selected_candidate_path_id is None
        assert records[4].review_required
    assert result_digest(first[-1]) == result_digest(second[-1])


def test_explicit_governed_priority_resolves_tie():
    f = decision_fixture(paths=2)
    p = f.policy("COMPLIANCE_PATH_POLICY").config
    templates = (p.templates[0].model_copy(update={"priority": 10}), p.templates[1])
    f = replace_policy(f, "COMPLIANCE_PATH_POLICY", templates=templates)
    f = replace_policy(
        f,
        "RECOMMENDATION_POLICY",
        criteria=[
            {"kind": "RISK_SCORE", "direction": "ASC"},
            {"kind": "TEMPLATE_PRIORITY", "direction": "DESC"},
        ],
    )
    o, c, r, rec, final = pipeline(f)
    assert rec.items[0].selected_candidate_id == c.items[0].candidate_path_id


def test_capability_gap_is_not_legal_prohibition():
    f = decision_fixture()
    p = f.policy("COMPLIANCE_PATH_POLICY").config
    f = replace_policy(
        f,
        "COMPLIANCE_PATH_POLICY",
        templates=[p.templates[0].model_copy(update={"capability_ids": (uuid4(),)})],
    )
    o, c, _, rec, final = pipeline(f)
    assert o.items[0].legal_effect == "REQUIRED"
    assert c.items[0].legal_viability == "VIABLE"
    assert c.items[0].operational_availability == "CAPABILITY_NOT_CONFIGURED"
    assert rec.items[0].selected_candidate_id is None
    assert final.items[0].status != "LEGALLY_PROHIBITED"


def test_formal_prohibition_comes_only_from_legal_binding():
    f = decision_fixture(risk_value=0)
    p = f.policy("OBLIGATION_POLICY").config
    f = replace_policy(
        f,
        "OBLIGATION_POLICY",
        entries=[p.entries[0].model_copy(update={"legal_effect_code": "TRANSFER_PROHIBITED"})],
    )
    o, c, _, a, final = pipeline(f)
    assert c.items[0].legal_viability == "LEGALLY_PROHIBITED"
    assert a.items[0].selected_candidate_id is None
    assert final.items[0].selected_candidate_path_id is None


@pytest.mark.parametrize(
    "status",
    [
        "NOT_APPLICABLE",
        "CONDITIONALLY_APPLICABLE",
        "INSUFFICIENT_EVIDENCE",
        "CONFLICTED",
        "REVIEW_REQUIRED",
    ],
)
def test_applicability_semantics_preserved(status):
    f = decision_fixture()
    f = f.model_copy(
        update={
            "applicability": (
                f.applicability[0].model_copy(update={"applicability_status": status}),
            )
        }
    )
    o, c, _, rec, final = pipeline(f)
    if status == "NOT_APPLICABLE":
        assert o.items[0].legal_effect == "NOT_APPLICABLE"
        assert final.items[0].status == "NOT_APPLICABLE"
    else:
        assert rec.items[0].selected_candidate_id is None
        assert final.items[0].selected_candidate_path_id is None


def test_missing_condition_is_unknown_not_false():
    f = decision_fixture()
    condition = ConditionPolicy(
        entry_id=uuid4(),
        code="MISSING_INPUT",
        fields=[{"code": "missing", "field_type": {"kind": "integer"}}],
        predicate='{"op":"gte","field":"missing","value":1}',
        examples=[{"facts": [], "expected": "UNKNOWN"}],
    )
    p = f.policy("OBLIGATION_POLICY").config
    f = replace_policy(
        f,
        "OBLIGATION_POLICY",
        entries=[p.entries[0].model_copy(update={"applicability_conditions": (condition,)})],
    )
    o, _, _, _, final = pipeline(f)
    assert o.items[0].legal_effect == "UNDETERMINED"
    assert o.items[0].conditions[0].evaluation == "UNKNOWN"
    assert final.summary_status == "INSUFFICIENT_EVIDENCE"


def test_conflicting_rule_hits_cannot_overwrite():
    f = decision_fixture()
    f = f.model_copy(
        update={"rule_hits": (*f.rule_hits, f.rule_hits[0].model_copy(update={"matched": False}))}
    )
    assert pipeline(f)[0].conflict_state == "CONFLICTED"
    assert pipeline(f)[-1].items[0].selected_candidate_path_id is None


def test_missing_required_risk_does_not_substitute_zero():
    f = decision_fixture().model_copy(update={"facts": ()})
    o, c, r, a, final = pipeline(f)
    assert o.items[0].legal_effect == "REQUIRED"
    assert c.items[0].legal_viability == "VIABLE"
    assert r.items[0].score is None
    assert r.items[0].risk_level == "UNKNOWN"
    assert a.items[0].selected_candidate_id is None


def test_wrong_parent_scope_rejected():
    f = decision_fixture()
    other = decision_fixture()
    with pytest.raises(ValueError, match="scope"):
        candidates(f, obligations(other))


def test_band_only_table_and_unmatched_is_unknown():
    low = ConditionPolicy(
        entry_id=uuid4(),
        code="LOW_INPUT",
        fields=[{"code": "count", "field_type": {"kind": "integer"}}],
        predicate='{"op":"lt","field":"count","value":50}',
        examples=[{"facts": [{"code": "count", "value": 1}], "expected": "TRUE"}],
    )
    policy = RiskPolicy(
        effective_from="2025-01-01",
        jurisdiction_ids=[uuid4()],
        mode="BAND_ONLY",
        band_rows=[{"conditions": [low], "band": "LOW"}],
        examples=[
            {
                "facts": [{"code": "count", "value": 1}],
                "expected_score": None,
                "expected_band": "LOW",
            }
        ],
    )
    assert evaluate_policy_values(policy, {"count": 1})[:2] == (None, "LOW")
    assert evaluate_policy_values(policy, {"count": 75})[:2] == (None, "UNKNOWN")
    assert evaluate_policy_values(policy, {})[:2] == (None, "UNKNOWN")


def test_risk_review_escalation_never_relabels_legality():
    f = replace_policy(
        decision_fixture(risk_value=95), "RECOMMENDATION_POLICY", review_bands=["HIGH"]
    )
    o, c, _, a, final = pipeline(f)
    assert c.items[0].legal_viability == "VIABLE"
    assert o.items[0].legal_effect == "REQUIRED"
    assert a.review_required and final.items[0].selected_candidate_path_id is None


def test_missing_policy_and_incomplete_jurisdiction_fail_conservatively():
    f = decision_fixture().model_copy(update={"policies": ()})
    assert pipeline(f)[-1].summary_status == "INSUFFICIENT_EVIDENCE"
    f = decision_fixture()
    i = f.identity.model_copy(update={"jurisdiction_ids": (*f.identity.jurisdiction_ids, uuid4())})
    assert (
        pipeline(f.model_copy(update={"identity": i}))[-1].items[0].selected_candidate_path_id
        is None
    )


def test_governed_nontransfer_alternative_preserves_prohibition_obligation():
    f = decision_fixture(paths=2, risk_value=95)
    ob = f.policy("OBLIGATION_POLICY").config
    f = replace_policy(
        f,
        "OBLIGATION_POLICY",
        entries=[ob.entries[0].model_copy(update={"legal_effect_code": "TRANSFER_PROHIBITED"})],
    )
    p = f.policy("COMPLIANCE_PATH_POLICY").config
    f = replace_policy(
        f,
        "COMPLIANCE_PATH_POLICY",
        templates=(
            p.templates[0],
            p.templates[1].model_copy(update={"prohibiting_obligation_entry_ids": ()}),
        ),
    )
    o, c, _, rec, final = pipeline(f)
    assert o.items[0].legal_effect_code == "TRANSFER_PROHIBITED"
    assert {p.legal_viability for p in c.items} == {"VIABLE", "LEGALLY_PROHIBITED"}
    assert rec.items[0].selected_candidate_id == next(
        p.candidate_path_id for p in c.items if p.legal_viability == "VIABLE"
    )
    assert final.items[0].unmet_requirement_ids and final.items[0].status == "CONDITIONAL_PROPOSAL"


def test_unknown_action_condition_blocks_selection():
    f = decision_fixture()
    p = f.policy("COMPLIANCE_PATH_POLICY").config
    condition = ConditionPolicy(
        entry_id=uuid4(),
        code="MISSING_ACTION_FACT",
        fields=[{"code": "missing", "field_type": {"kind": "integer"}}],
        predicate='{"op":"gte","field":"missing","value":1}',
        examples=[{"facts": [], "expected": "UNKNOWN"}],
    )
    action = p.templates[0].actions[0].model_copy(update={"conditions": (condition,)})
    f = replace_policy(
        f,
        "COMPLIANCE_PATH_POLICY",
        templates=(p.templates[0].model_copy(update={"actions": (action,)}),),
    )
    _, c, _, rec, final = pipeline(f)
    assert c.items[0].legal_viability == "UNDETERMINED"
    assert (
        final.summary_status == "INSUFFICIENT_EVIDENCE"
        and rec.items[0].selected_candidate_id is None
    )


def test_band_only_formal_trace_requires_authorized_evidence():
    f = decision_fixture()
    condition = ConditionPolicy(
        entry_id=uuid4(),
        code="BAND_FACT",
        fields=[{"code": "count", "field_type": {"kind": "integer"}}],
        predicate='{"op":"lt","field":"count","value":50}',
        required_evidence=True,
        examples=[{"facts": [{"code": "count", "value": 25}], "expected": "TRUE"}],
    )
    f = replace_policy(
        f,
        "RISK_POLICY",
        mode="BAND_ONLY",
        dimensions=(),
        bands=(),
        band_rows=[{"conditions": [condition], "band": "LOW"}],
        examples=[
            {
                "facts": [{"code": "count", "value": 25}],
                "expected_score": None,
                "expected_band": "LOW",
            }
        ],
    )
    o = obligations(f)
    c = candidates(f, o)
    r = risks(f, c)
    assert (
        r.items[0].band_conditions[0].evaluation == "TRUE"
        and r.items[0].band_conditions[0].fact_refs
    )
    empty = f.model_copy(
        update={"facts": tuple(v.model_copy(update={"evidence_ids": ()}) for v in f.facts)}
    )
    o = obligations(empty)
    c = candidates(empty, o)
    r = risks(empty, c)
    assert r.items[0].risk_level == "UNKNOWN" and r.items[0].score is None
