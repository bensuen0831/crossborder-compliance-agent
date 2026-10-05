"""Technical model/data policy intersection, never classification or legal inference."""

from crossborder_compliance.domain.llm_gateway import (
    GatewayDenied,
    ModelOperation,
    ModelPolicyMode,
    PolicyDecision,
)
from crossborder_compliance.domain.metadata import ModelCapabilityCode

OPERATION_CAPABILITY = {
    ModelOperation.CHAT: ModelCapabilityCode.TEXT,
    ModelOperation.CHAT_STREAM: ModelCapabilityCode.TEXT,
    ModelOperation.STRUCTURED_OUTPUT: ModelCapabilityCode.STRUCTURED_OUTPUT,
    ModelOperation.EMBEDDING: ModelCapabilityCode.EMBEDDING,
    ModelOperation.RERANK: ModelCapabilityCode.RERANK,
    ModelOperation.COUNT_TOKENS: ModelCapabilityCode.TEXT,
}
POLICY_ORDER = {
    ModelPolicyMode.EXTERNAL_MODEL_ALLOWED: 0,
    ModelPolicyMode.REDACTION_REQUIRED: 1,
    ModelPolicyMode.INTERNAL_MODEL_ONLY: 2,
}


def required_capabilities(request):
    required = set(request.required_capabilities)
    if request.operation in OPERATION_CAPABILITY:
        required.add(OPERATION_CAPABILITY[request.operation])
    return required


class ModelUsagePolicyService:
    def evaluate(self, request, context, inputs, policies, models):
        if len(policies) != 2 or {p.scope_type for p in policies} != {"TENANT", "PROJECT"}:
            raise GatewayDenied("MODEL_POLICY_REQUIRED")
        modes, reasons = [], ["TENANT_PROJECT_POLICY_INTERSECTION"]
        for policy in policies:
            if policy.tenant_id != context.tenant_id or (
                policy.scope_type == "PROJECT" and policy.project_id != request.project_id
            ):
                raise GatewayDenied("RESOURCE_NOT_FOUND")
            if request.operation not in policy.allowed_operations:
                raise GatewayDenied()
            modes.append(policy.default_mode)
            for item in inputs:
                for codes, rules in (
                    (item.security_codes, policy.security_rules),
                    (item.confidentiality_codes, policy.confidentiality_rules),
                    (item.document_types, policy.document_rules),
                ):
                    if not codes or any(code not in rules for code in codes):
                        modes.append(ModelPolicyMode.INTERNAL_MODEL_ONLY)
                        reasons.append("UNRESOLVED_DATA_POLICY_INTERNAL_ONLY")
                    modes.extend(rules.get(c, ModelPolicyMode.INTERNAL_MODEL_ONLY) for c in codes)
            for cap in required_capabilities(request):
                modes.append(policy.capability_rules.get(cap.value, policy.default_mode))
        mode = ModelPolicyMode(max(modes, key=POLICY_ORDER.__getitem__))
        allowed = []
        for model in models:
            if model.tenant_id != context.tenant_id:
                continue
            if all(
                model.model_id in p.allowed_model_ids
                and model.provider_id in p.allowed_provider_ids
                and model.trust_level in p.allowed_trust_levels
                and model.data_boundary in p.allowed_data_boundaries
                and (mode != ModelPolicyMode.INTERNAL_MODEL_ONLY or self.internal(model, policies))
                for p in policies
            ) and all(
                not item.permitted_model_boundaries
                or model.data_boundary in item.permitted_model_boundaries
                for item in inputs
            ):
                allowed.append(model)
        return PolicyDecision(
            selected_policy=mode,
            external_model_allowed=mode != ModelPolicyMode.INTERNAL_MODEL_ONLY,
            redaction_required=mode == ModelPolicyMode.REDACTION_REQUIRED,
            internal_only=mode == ModelPolicyMode.INTERNAL_MODEL_ONLY,
            policy_versions=tuple(p.version_id for p in policies),
            allowed_model_ids=tuple(m.model_id for m in allowed),
            allowed_provider_ids=tuple(sorted({m.provider_id for m in allowed}, key=str)),
            reason_codes=tuple(dict.fromkeys([*reasons, mode.value])),
        )

    @staticmethod
    def internal(model, policies):
        return all(model.deployment_class in p.internal_deployment_classes for p in policies)


class ModelRouter:
    def route(self, request, decision, models):
        capabilities = required_capabilities(request)
        candidates = tuple(
            m
            for m in models
            if m.model_id in decision.allowed_model_ids
            and m.provider_id in decision.allowed_provider_ids
            and capabilities <= set(m.capabilities)
            and request.operation in m.operations
            and (m.health_status == "HEALTHY" or request.operation == ModelOperation.HEALTH_CHECK)
            and (
                request.operation
                not in (
                    ModelOperation.CHAT,
                    ModelOperation.CHAT_STREAM,
                    ModelOperation.STRUCTURED_OUTPUT,
                )
                or request.max_output_tokens <= m.max_output_tokens
            )
        )
        if not candidates:
            raise GatewayDenied("NO_ALLOWED_HEALTHY_CAPABLE_MODEL")
        return tuple(sorted(candidates, key=lambda m: (m.priority, str(m.model_id))))
