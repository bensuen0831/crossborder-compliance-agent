"""Candidate/derived orchestration over the sole gateway, never model voting."""

from uuid import uuid4

from crossborder_compliance.application.llm_invocation_policy import LLMInvocationPolicyService
from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.domain.llm_invocation import (
    ModelInvocationOutcome,
    ModelSelectionMode,
    MultiModelInvocationResult,
)


class GovernedLLMInvocationService:
    def __init__(self, gateway, governance):
        self.gateway, self.governance = gateway, governance

    def invoke(self, request, facts):
        # The server's snapshot reader owns preferences and immutable policy pins.
        policy, preference = self.governance.load(request)
        decision = LLMInvocationPolicyService().evaluate(policy, preference, facts)
        if not decision.allowed:
            raise GatewayDenied(decision.reason_code)
        group_id = request.invocation_group_id or uuid4()
        models = preference.selected_model_ids or (None,)
        if preference.selection_mode == ModelSelectionMode.MULTI_MODEL:
            self.gateway.prepare_selected_models(request, preference.selected_model_ids)
        outcomes = []
        for selected in models:
            child = request.model_copy(
                update={
                    "request_id": uuid4(),
                    "selected_model_id": selected,
                    "invocation_group_id": group_id,
                }
            )
            try:
                result = self.gateway.invoke(child)
            except GatewayDenied as error:
                if preference.selection_mode != ModelSelectionMode.MULTI_MODEL:
                    raise
                outcomes.append(
                    ModelInvocationOutcome(
                        request_id=child.request_id,
                        model_id=selected,
                        status="DENIED",
                        reason_code=error.code,
                    )
                )
            else:
                outcomes.append(
                    ModelInvocationOutcome(
                        request_id=child.request_id,
                        model_id=result.model_id,
                        status="COMPLETED",
                        result=result,
                    )
                )
        return MultiModelInvocationResult(
            invocation_group_id=group_id,
            analysis_snapshot_id=request.analysis_snapshot_id,
            purpose=facts.purpose,
            strategy=preference.selection_mode,
            model_results=tuple(outcomes),
            status="COMPLETED"
            if all(outcome.status == "COMPLETED" for outcome in outcomes)
            else "PARTIAL_FAILURE",
        )
