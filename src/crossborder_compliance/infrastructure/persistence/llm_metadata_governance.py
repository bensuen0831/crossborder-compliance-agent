"""Typed validation through the existing metadata lifecycle, never a new registry."""

from uuid import uuid4

from crossborder_compliance.domain.llm_gateway import ModelUsagePolicy
from crossborder_compliance.domain.llm_invocation import LLMInvocationPolicy


def validate_llm_metadata(session, definition, payload):
    if definition.kind == "LLM_INVOCATION_POLICY":
        LLMInvocationPolicy.model_validate(
            dict(payload, policy_id=definition.definition_id, version_id=uuid4())
        )
    elif definition.kind == "MODEL_USAGE_POLICY":
        policy = ModelUsagePolicy.model_validate(
            dict(
                payload,
                policy_id=definition.definition_id,
                version_id=uuid4(),
                version=1,
                tenant_id=definition.tenant_id,
            )
        )
        from crossborder_compliance.infrastructure.persistence import metadata_models as m
        from crossborder_compliance.infrastructure.persistence import models as b

        if policy.project_id:
            project = session.get(b.ProjectEntity, str(policy.project_id))
            if project is None or project.tenant_id != definition.tenant_id:
                raise ValueError("USAGE_POLICY_PROJECT_SCOPE_INVALID")
        for ids, cls in (
            (policy.allowed_model_ids, m.ModelDefinitionEntity),
            (policy.allowed_provider_ids, m.ModelProviderEntity),
        ):
            for identity in ids:
                row = session.get(cls, str(identity))
                if row is None or row.tenant_id != definition.tenant_id:
                    raise ValueError("USAGE_POLICY_MODEL_SCOPE_INVALID")
    elif not isinstance(payload.get("vendor_preset"), str) or not payload["vendor_preset"]:
        raise ValueError("PROVIDER_PRESET_CODE_REQUIRED")
    return {}
