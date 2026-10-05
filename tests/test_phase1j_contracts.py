from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from crossborder_compliance.domain.contracts import ComplianceObligationDTO
from crossborder_compliance.domain.decision_contracts import StageRef, canonical_json, digest
from crossborder_compliance.domain.decision_policies import ConditionPolicy, RiskPolicy


def risk_policy(**changes):
    return RiskPolicy.model_validate(
        {
            "effective_from": "2025-01-01",
            "jurisdiction_ids": [str(uuid4())],
            "mode": "WEIGHTED",
            "dimensions": [
                {
                    "code": "EXPOSURE",
                    "weight": "1",
                    "factors": [{"code": "VOLUME", "observation_code": "count", "weight": "1"}],
                }
            ],
            "bands": [
                {"lower": "0", "upper": "50", "band": "LOW"},
                {"lower": "50", "upper": "100", "band": "HIGH"},
            ],
            "examples": [
                {
                    "facts": [{"code": "count", "value": 25}],
                    "expected_score": "25",
                    "expected_band": "LOW",
                }
            ],
            **changes,
        }
    )


def test_v1_schema_stays_frozen():
    assert set(ComplianceObligationDTO.model_fields) == {
        "schema_version",
        "record_version",
        "created_at",
        "updated_at",
        "provenance",
        "obligation_id",
        "requirement_id",
        "subject_refs",
        "responsible_party_ids",
        "status",
        "legal_basis_ids",
        "evidence_ids",
    }
    assert ComplianceObligationDTO.model_fields["schema_version"].default == "1.0"


@pytest.mark.parametrize("code", ["适用", "適用", "Applicable", "APPLICABLE zh-HK"])
def test_localized_authority_rejected(code):
    with pytest.raises(ValidationError):
        StageRef(kind=code, result_id=uuid4(), content_digest="a" * 64)


def test_canonical_decimal_and_extra_fields():
    assert canonical_json({"score": Decimal("1.000")}) == canonical_json({"score": Decimal("1")})
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})
    with pytest.raises(ValidationError):
        StageRef(kind="RISK", result_id=uuid4(), content_digest="a" * 64, locale="zh-HK")


def test_policy_reuses_ast_and_unknown_example():
    p = ConditionPolicy(
        entry_id=uuid4(),
        code="COUNT_TEST",
        fields=({"code": "count", "field_type": {"kind": "integer"}},),
        predicate='{"op":"gte","field":"count","value":3}',
        examples=({"facts": (), "expected": "UNKNOWN"},),
    )
    with pytest.raises(ValidationError):
        ConditionPolicy.model_validate(
            {**p.model_dump(), "examples": [{"facts": [], "expected": "FALSE"}]}
        )


@pytest.mark.parametrize(
    "override",
    [
        {
            "bands": [
                {"lower": 0, "upper": 40, "band": "LOW"},
                {"lower": 50, "upper": 100, "band": "HIGH"},
            ]
        },
        {
            "dimensions": [
                {
                    "code": "D",
                    "weight": "0.9",
                    "factors": [{"code": "F", "observation_code": "count", "weight": "1"}],
                }
            ]
        },
        {
            "examples": [
                {
                    "facts": [{"code": "count", "value": 25}],
                    "expected_score": "50",
                    "expected_band": "HIGH",
                }
            ]
        },
    ],
)
def test_invalid_risk_policy_rejected(override):
    with pytest.raises(ValidationError):
        risk_policy(**override)


def test_generic_policy_localization_reuse():
    from crossborder_compliance.domain.localized_metadata import resolve_display

    p = risk_policy(
        localized_display={
            "localized_display_names": {"zh-CN": "简体标签", "zh-HK": "繁體標籤", "en-US": "Label"},
            "fallback_locale": "en-US",
        }
    )
    assert p.mode == "WEIGHTED"
    assert (
        len(
            {
                resolve_display("RISK", "Canonical", p.localized_display, locale).display_name
                for locale in ("zh-CN", "zh-HK", "en-US")
            }
        )
        == 3
    )


def test_governed_fallback_and_locale_neutral_digest():
    from phase1j_fixtures import decision_fixture

    from crossborder_compliance.domain.decision_engine import input_digest
    from crossborder_compliance.domain.localized_metadata import resolve_display

    p = risk_policy(
        localized_display={"localized_display_names": {"en-US": "Risk"}, "fallback_locale": "en-US"}
    )
    assert resolve_display("RISK", "Canonical", p.localized_display, "zh-HK").display_name == "Risk"
    assert resolve_display("RISK", None, None, "zh-CN").display_name == "RISK"
    f = decision_fixture()
    policy = f.policy("RISK_POLICY")
    translated = policy.model_copy(
        update={
            "config": policy.config.model_copy(update={"localized_display": p.localized_display})
        }
    )
    assert input_digest(f) == input_digest(
        f.model_copy(
            update={"policies": tuple(translated if v == policy else v for v in f.policies)}
        )
    )
