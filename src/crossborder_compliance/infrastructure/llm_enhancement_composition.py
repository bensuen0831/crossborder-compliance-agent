"""One gateway composition for governed enhancements, using canonical adapters."""

from crossborder_compliance.application.llm_gateway_services import LLMService
from crossborder_compliance.application.llm_invocation_services import GovernedLLMInvocationService
from crossborder_compliance.infrastructure.llm_gateway_http import (
    HTTPProviderAdapter,
    OpenAICompatibleProviderAdapter,
)
from crossborder_compliance.infrastructure.llm_invocation_governance import (
    PostgresLLMInvocationGovernance,
)
from crossborder_compliance.infrastructure.persistence.llm_gateway_audit import PostgresGatewayAudit


def enhancement_invocation(configuration, inputs, secrets, *, redaction=None):
    gateway = LLMService(
        context=configuration.context,
        configuration=configuration,
        inputs=inputs,
        providers={
            "OPENAI_COMPATIBLE": OpenAICompatibleProviderAdapter(configuration, secrets),
            "GENERIC_REST": HTTPProviderAdapter(configuration, secrets),
        },
        audit=PostgresGatewayAudit(configuration.sessions, configuration.context),
        redaction=redaction,
    )
    return GovernedLLMInvocationService(gateway, PostgresLLMInvocationGovernance(configuration))
