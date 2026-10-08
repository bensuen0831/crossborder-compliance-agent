"""Deterministic trigger gate independent of model routing and legal owners."""

from crossborder_compliance.domain.llm_invocation import (
    InvocationDecision,
    InvocationPurpose,
    InvocationTrigger,
    LLMUsageMode,
)

DOCUMENT_TRIGGERS = frozenset(
    (
        InvocationTrigger.DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED,
        InvocationTrigger.DOCUMENT_EXTRACTION_LOW_CONFIDENCE,
        InvocationTrigger.DOCUMENT_FIELD_CONFLICT,
    )
)
QUERY_TRIGGERS = frozenset(
    (
        InvocationTrigger.RETRIEVAL_QUERY_EXPANSION_REQUIRED,
        InvocationTrigger.KNOWLEDGE_EVIDENCE_INSUFFICIENT,
    )
)


class LLMInvocationPolicyService:
    def evaluate(self, policy, preference, facts):
        code = "INVOCATION_TRIGGER_ALLOWED"
        if facts.trigger not in policy.allowed_triggers.get(preference.usage_mode, ()):
            code = "INVOCATION_TRIGGER_NOT_ALLOWED"
        elif facts.trigger in DOCUMENT_TRIGGERS:
            if facts.purpose != InvocationPurpose.DOCUMENT_CANDIDATE_EXTRACTION:
                code = "INVOCATION_PURPOSE_MISMATCH"
            elif facts.structured_fields_complete:
                code = "STRUCTURED_INPUT_ALREADY_COMPLETE"
            elif not facts.parser_insufficient:
                code = "DETERMINISTIC_EXTRACTION_SUFFICIENT"
        elif facts.trigger in QUERY_TRIGGERS:
            if facts.purpose != InvocationPurpose.QUERY_EXPANSION:
                code = "INVOCATION_PURPOSE_MISMATCH"
            elif facts.evidence_sufficient:
                code = "GOVERNED_EVIDENCE_ALREADY_SUFFICIENT"
            elif preference.usage_mode == LLMUsageMode.MINIMAL:
                code = "MINIMAL_QUERY_EXPANSION_DISABLED"
        elif facts.trigger == InvocationTrigger.RESULT_EXPLANATION_REQUESTED:
            if facts.purpose != InvocationPurpose.DERIVED_EXPLANATION:
                code = "INVOCATION_PURPOSE_MISMATCH"
            elif not facts.evidence_sufficient:
                code = "EXPLANATION_REQUIRES_GOVERNED_EVIDENCE"
            elif preference.usage_mode == LLMUsageMode.MINIMAL:
                code = "MINIMAL_EXPLANATION_DISABLED"
        else:
            code = "STAGE2_NOT_STARTED"
        if len(preference.selected_model_ids) > policy.max_models:
            code = "MODEL_SELECTION_LIMIT_EXCEEDED"
        return InvocationDecision(
            allowed=code == "INVOCATION_TRIGGER_ALLOWED",
            reason_code=code,
            policy_version_id=policy.version_id,
            purpose=facts.purpose,
        )
