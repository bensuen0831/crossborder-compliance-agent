"""Display locales are orthogonal to machine semantics and official legal authority."""

from uuid import uuid4

import pytest
from phase1i_fixtures import prepared
from pydantic import ValidationError

from crossborder_compliance.domain.localized_metadata import (
    LocalizedDisplayMetadata,
    resolve_display,
)
from crossborder_compliance.domain.regulation_applicability import (
    RegulationApplicabilityResult,
    RegulationApplicabilitySkill,
)
from crossborder_compliance.interfaces.api.metadata_presenter import (
    present_applicability,
    present_metadata,
)

LABELS = {"zh-CN": "适用", "zh-HK": "適用", "en-US": "Applicable"}


@pytest.mark.parametrize("locale", list(LABELS))
def test_independent_labels_same_stable_code(locale):
    metadata = LocalizedDisplayMetadata(localized_display_names=LABELS)
    result = resolve_display("APPLICABLE", "Canonical", metadata, locale)
    assert result.stable_code == "APPLICABLE" and result.display_name == LABELS[locale]
    assert result.resolved_locale == locale and not result.fallback_used


def test_governed_deterministic_fallback_missing_translation():
    metadata = LocalizedDisplayMetadata(
        localized_display_names={"en-US": "English", "zh-HK": "繁體"}, fallback_locale="zh-HK"
    )
    result = resolve_display("AI_SERVICE", "Canonical", metadata, "zh-CN")
    assert (
        result.display_name == "繁體" and result.resolved_locale == "zh-HK" and result.fallback_used
    )
    empty = LocalizedDisplayMetadata(
        localized_display_names={"en-US": "English"}, fallback_locale="zh-HK"
    )
    assert resolve_display("AI_SERVICE", "Canonical", empty, "zh-CN").display_name == "Canonical"
    assert resolve_display("AI_SERVICE", None, empty, "zh-CN").display_name == "AI_SERVICE"


@pytest.mark.parametrize(
    "bad",
    [
        {"localized_display_names": {"fr-FR": "Label"}},
        {"fallback_locale": "fr-FR"},
        {"localized_display_names": {"zh-CN": ""}},
    ],
)
def test_unknown_locale_or_empty_label_rejected(bad):
    with pytest.raises(ValidationError):
        LocalizedDisplayMetadata(**bad)


def test_locale_change_preserves_formal_result_and_official_evidence_basis():
    result = RegulationApplicabilitySkill().execute(prepared()).model_dump(mode="json")
    config = {"localized_code_labels": {"APPLICABLE": {"localized_display_names": LABELS}}}
    responses = [present_applicability(result, config, locale) for locale in LABELS]
    assert all(x["result"] == result for x in responses)
    assert all(
        x["result"]["evidence_ids"] == result["evidence_ids"]
        and x["result"]["legal_basis_ids"] == result["legal_basis_ids"]
        and x["result"]["provenance"]["official_sources"]
        == result["provenance"]["official_sources"]
        and x["result"]["provenance"]["citation_locators"]
        == result["provenance"]["citation_locators"]
        for x in responses
    )
    for label in LABELS.values():
        with pytest.raises(ValidationError):
            RegulationApplicabilityResult.model_validate({**result, "applicability_status": label})


def test_generic_registry_presenter_keeps_canonical_identity_and_payload():
    row = {
        "definition_id": str(uuid4()),
        "code": "AI_SERVICE",
        "display_name": "Canonical",
        "payload": {
            "localized_display": {
                "localized_display_names": {
                    "zh-CN": "人工智能服务",
                    "zh-HK": "人工智能服務",
                    "en-US": "AI service",
                }
            },
            "official_text": "source text",
            "evidence_language": "en",
        },
    }
    for locale in LABELS:
        projected = present_metadata(row, locale)
        assert (
            projected["code"] == row["code"]
            and projected["payload"] == row["payload"]
            and projected["display_name"] == row["display_name"]
        )
        assert projected["presentation"]["requested_locale"] == locale
    assert "presentation" not in row


def test_localized_labels_cannot_be_persisted_as_formal_configuration_codes():
    from crossborder_compliance.domain.compliance_profiles import (
        CapabilityConfig,
        ScenarioAdjustmentConfig,
    )

    for label in ("适用", "適用", "Applicable"):
        with pytest.raises(ValidationError):
            CapabilityConfig(kind="FILING", effective_from="2025-01-01", reason_codes=(label,))
        result = RegulationApplicabilitySkill().execute(prepared()).model_dump(mode="json")
        with pytest.raises(ValidationError):
            RegulationApplicabilityResult.model_validate({**result, "reason_codes": [label]})
    with pytest.raises(ValidationError):
        ScenarioAdjustmentConfig(
            scenario_definition_id=uuid4(),
            effective_from="2025-01-01",
            required_inputs=("跨境資料",),
        )
