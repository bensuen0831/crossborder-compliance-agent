"""Engineering-only Gold templates and reconciliation cannot assert real legal acceptance."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from crossborder_compliance.application.regulatory_acceptance import reconcile_semantics
from crossborder_compliance.domain.regulatory_acceptance import (
    ExpectedRegulatorySemantics,
    RegulatoryAcceptanceCase,
    RegulatorySourcePin,
)
from crossborder_compliance.interfaces.api.regulatory_acceptance_schemas import (
    ImportAcceptanceDraft,
)


def semantics():
    pin = RegulatorySourcePin(
        knowledge_version_id=uuid4(), content_sha256="a" * 64, structure_node_ids=(uuid4(),)
    )
    return ExpectedRegulatorySemantics(
        jurisdiction_ids=(uuid4(),),
        required_document_levels={},
        classification_codes=("SYNTHETIC_CLASS",),
        applicability_codes=("SYNTHETIC_APPLICABILITY",),
        cross_border_status="REVIEW_REQUIRED",
        obligation_codes=(),
        candidate_path_codes=(),
        risk_codes=(),
        recommendation_codes=(),
        final_path_codes=(),
        required_document_codes=(),
        reason_codes=("SYNTHETIC_REVIEW",),
        legal_source_pins=(pin,),
    )


def test_reconciliation_includes_status_reasons_and_exact_legal_source_pins():
    expected = semantics()
    assert reconcile_semantics(expected, expected)["decision"] == "RECONCILIATION_MATCH"
    for field, changed in (
        ("cross_border_status", "DIRECT_TRANSFER_ALLOWED"),
        ("reason_codes", ("DIFFERENT_REASON",)),
        (
            "legal_source_pins",
            (expected.legal_source_pins[0].model_copy(update={"content_sha256": "b" * 64}),),
        ),
        ("obligation_codes", ("FABRICATED_OBLIGATION",)),
        ("jurisdiction_ids", (uuid4(),)),
        ("required_document_levels", {"SYNTHETIC_DOCUMENT": "REQUIRED"}),
    ):
        actual = ExpectedRegulatorySemantics.model_validate(
            {**expected.model_dump(), field: changed}
        )
        result = reconcile_semantics(expected, actual)
        assert result["decision"] == "RECONCILIATION_MISMATCH"
        assert result["fields"][field]["match"] is False
        assert result["real_regulatory_legal_acceptance"] == "NOT_ESTABLISHED_BY_COMPARISON"


def test_l1_label_cannot_be_promoted_to_real_regulatory_dataset():
    payload = dict(
        dataset_kind="L1_SYNTHETIC_GOVERNED",
        synthetic_label="SYNTHETIC_GOVERNED_TEST_DATA",
        description="Engineering readiness fixture",
        jurisdiction_ids=(uuid4(),),
        analysis_as_of_date="2026-10-15",
        input_manifest_sha256="c" * 64,
        source_pins=(),
        evaluation_criteria=("TRACEABILITY",),
    )
    RegulatoryAcceptanceCase.model_validate(payload)
    with pytest.raises(ValidationError, match="DATASET_LABEL_MISMATCH"):
        RegulatoryAcceptanceCase.model_validate({**payload, "dataset_kind": "L2_REAL_REGULATORY"})
    with pytest.raises(ValidationError):
        ImportAcceptanceDraft(
            kind="REGULATORY_ACCEPTANCE_CASE",
            code="CASE",
            display_name="Case",
            payload=payload,
            approved_by="caller-fabricated-expert",
        )
