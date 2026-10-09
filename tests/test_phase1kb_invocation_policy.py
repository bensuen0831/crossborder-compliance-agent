from uuid import uuid4

import pytest
from pydantic import ValidationError

from crossborder_compliance.application.llm_invocation_policy import LLMInvocationPolicyService
from crossborder_compliance.domain.llm_invocation import (
    AIModelPreference,
    InvocationFacts,
    InvocationPurpose,
    InvocationTrigger,
    LLMInvocationPolicy,
    LLMUsageMode,
)


def decision(trigger, purpose, mode="STANDARD", **facts):
    policy = LLMInvocationPolicy(
        policy_id=uuid4(),
        version_id=uuid4(),
        max_models=3,
        allowed_triggers={m: tuple(InvocationTrigger) for m in LLMUsageMode},
    )
    return LLMInvocationPolicyService().evaluate(
        policy,
        AIModelPreference(usage_mode=mode),
        InvocationFacts(trigger=trigger, purpose=purpose, **facts),
    )


@pytest.mark.parametrize("mode", list(LLMUsageMode))
def test_parser_insufficiency_all_modes_candidate_only(mode):
    assert decision(
        "DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED",
        "DOCUMENT_CANDIDATE_EXTRACTION",
        mode,
        parser_insufficient=True,
    ).allowed
    assert not decision(
        "DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED",
        "DOCUMENT_CANDIDATE_EXTRACTION",
        mode,
        parser_insufficient=True,
        structured_fields_complete=True,
    ).allowed
    assert not decision(
        "DOCUMENT_EXTRACTION_LOW_CONFIDENCE", "DOCUMENT_CANDIDATE_EXTRACTION", mode
    ).allowed


@pytest.mark.parametrize(
    "trigger", ["KNOWLEDGE_EVIDENCE_INSUFFICIENT", "RETRIEVAL_QUERY_EXPANSION_REQUIRED"]
)
def test_rag_first_never_expand_sufficient_evidence(trigger):
    assert not decision(trigger, "QUERY_EXPANSION", evidence_sufficient=True).allowed
    assert decision(trigger, "QUERY_EXPANSION").allowed
    assert not decision(trigger, "QUERY_EXPANSION", "MINIMAL").allowed


@pytest.mark.parametrize(
    "trigger",
    ["DOCUMENT_GENERATION_REQUESTED", "CONTRACT_GENERATION_REQUESTED", "CONTRACT_REVIEW_REQUESTED"],
)
def test_stage2_always_denied_even_if_policy_lists_it(trigger):
    assert decision(trigger, "DERIVED_EXPLANATION").reason_code == "STAGE2_NOT_STARTED"


def test_legal_purpose_not_in_contract_or_multi_vote():
    with pytest.raises(ValidationError):
        InvocationFacts(trigger="RESULT_EXPLANATION_REQUESTED", purpose="FINAL_PATH")
    assert set(InvocationPurpose) == {
        "DOCUMENT_CANDIDATE_EXTRACTION",
        "QUERY_EXPANSION",
        "DERIVED_EXPLANATION",
    }
    assert not decision(
        "DOCUMENT_FIELD_CONFLICT", "QUERY_EXPANSION", parser_insufficient=True
    ).allowed
    assert not decision("RESULT_EXPLANATION_REQUESTED", "DERIVED_EXPLANATION").allowed


def test_user_selection_shape_and_server_limit():
    with pytest.raises(ValidationError):
        AIModelPreference(selection_mode="SINGLE")
    with pytest.raises(ValidationError):
        AIModelPreference(selection_mode="MULTI_MODEL", selected_model_ids=(uuid4(), uuid4()))
    preference = AIModelPreference(
        usage_mode="ENHANCED",
        selection_mode="MULTI_MODEL",
        selected_model_ids=tuple(uuid4() for _ in range(4)),
    )
    policy = LLMInvocationPolicy(
        policy_id=uuid4(),
        version_id=uuid4(),
        max_models=3,
        allowed_triggers={"ENHANCED": ("DOCUMENT_EXTRACTION_LOW_CONFIDENCE",)},
    )
    result = LLMInvocationPolicyService().evaluate(
        policy,
        preference,
        InvocationFacts(
            trigger="DOCUMENT_EXTRACTION_LOW_CONFIDENCE",
            purpose="DOCUMENT_CANDIDATE_EXTRACTION",
            parser_insufficient=True,
        ),
    )
    assert result.reason_code == "MODEL_SELECTION_LIMIT_EXCEEDED"


def test_governed_policy_can_deny_otherwise_valid_trigger():
    policy = LLMInvocationPolicy(
        policy_id=uuid4(), version_id=uuid4(), max_models=3, allowed_triggers={}
    )
    result = LLMInvocationPolicyService().evaluate(
        policy,
        AIModelPreference(),
        InvocationFacts(trigger="KNOWLEDGE_EVIDENCE_INSUFFICIENT", purpose="QUERY_EXPANSION"),
    )
    assert not result.allowed
