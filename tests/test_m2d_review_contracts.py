"""Review input authority and backend resolution precedence."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from crossborder_compliance.application.review_services import (
    ReviewCorrectionRequest,
    ReviewDecisionRequest,
)
from crossborder_compliance.domain.review_governance import resolution_actions


@pytest.mark.parametrize(
    "field", ["decided_by", "tenant_id", "langgraph_thread_id", "policy", "start_at", "final_path"]
)
def test_browser_cannot_inject_review_authority(field):
    with pytest.raises(ValidationError):
        ReviewDecisionRequest.model_validate(
            {
                "decision": "APPROVE",
                "expected_record_version": 1,
                "idempotency_key": "request",
                field: "injected",
            }
        )


@pytest.mark.parametrize(
    "reason",
    [
        "FACT_CONFLICT",
        "BUSINESS_FACT_CONFLICT",
        "PRODUCT_CONTEXT_CONFLICT",
        "JURISDICTION_UNRESOLVED",
        "INSUFFICIENT_EVIDENCE",
        "EVIDENCE_INSUFFICIENT",
        "CAPABILITY_NOT_CONFIGURED",
        "UNDETERMINED",
    ],
)
def test_approval_cannot_clear_formal_reason(reason):
    actions, mode, _ = resolution_actions(
        stage="requirement", reasons=(reason,), requirement_confirmation=True
    )
    assert "APPROVE" not in actions and mode == "SUCCESSOR_SNAPSHOT"


def test_only_explicit_immutable_requirement_confirmation_can_approve():
    assert resolution_actions(stage="requirement", reasons=(), requirement_confirmation=True)[
        :2
    ] == (("APPROVE", "REJECT", "REQUEST_CHANGES"), "SAME_SNAPSHOT")
    assert (
        "APPROVE"
        not in resolution_actions(stage="cross_border", reasons=(), requirement_confirmation=True)[
            0
        ]
    )
    assert (
        resolution_actions(
            stage="requirement", reasons=(), requirement_confirmation=True, modern=False
        )[0]
        == ()
    )


def test_correction_is_typed_not_free_text_or_arbitrary_json_path():
    with pytest.raises(ValidationError):
        ReviewCorrectionRequest.model_validate(
            {
                "expected_record_version": 1,
                "idempotency_key": "key",
                "correction": {
                    "correction_type": "PATCH_FINAL_PATH",
                    "target_object_id": str(uuid4()),
                    "value": "PROPOSED",
                },
            }
        )
