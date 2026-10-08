"""Admin safe probes through the canonical HTTP adapters, never fake success."""

from datetime import UTC, datetime

from crossborder_compliance.application.metadata_services import AdminActionPolicy
from crossborder_compliance.domain.llm_gateway import GatewayDenied, ProviderFailure, ProviderInput
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.llm_gateway_http import (
    HTTPProviderAdapter,
    OpenAICompatibleProviderAdapter,
)


class _ProbeConnectionSource:
    def __init__(self, connection):
        self.value = connection

    def connection(self, model):
        return self.value


class ProviderInspection:
    def __init__(self, repository, secrets):
        self.repository, self.secrets = repository, secrets

    def _adapter(self, protocol, connection):
        cls = (
            OpenAICompatibleProviderAdapter
            if protocol == "OPENAI_COMPATIBLE"
            else HTTPProviderAdapter
        )
        return cls(_ProbeConnectionSource(connection), self.secrets)

    @staticmethod
    def _failure(error):
        code = error.code
        allowed = {
            "AUTHENTICATION_FAILED",
            "ENDPOINT_UNREACHABLE",
            "TLS_ERROR",
            "MODEL_ENDPOINT_INVALID",
            "CAPABILITY_UNSUPPORTED",
            "SECRET_UNAVAILABLE",
            "TIMEOUT",
        }
        code = {
            "MODEL_SECRET_UNAVAILABLE": "SECRET_UNAVAILABLE",
            "PROVIDER_CAPABILITY_UNSUPPORTED": "CAPABILITY_UNSUPPORTED",
            "MODEL_ENDPOINT_INVALID": "MODEL_ENDPOINT_INVALID",
        }.get(code, code)
        return {
            "status": code if code in allowed else "ENDPOINT_UNREACHABLE",
            "candidate_models": (),
        }

    def connection_test(self, provider_version_id):
        protocol, connection = self.repository.probe_connection(provider_version_id)
        try:
            result = self._adapter(protocol, connection).execute(
                None, ProviderInput(operation="health_check", texts=(), max_output_tokens=1)
            )
            return {
                "status": "HEALTHY" if result.healthy else "ENDPOINT_UNREACHABLE",
                "candidate_models": result.discovered_models,
            }
        except (GatewayDenied, ProviderFailure) as error:
            return self._failure(error)

    def model_test(self, deployment_id, operation):
        AdminActionPolicy().require(self.repository.context, "metadata:admin")
        config = PostgresLLMConfiguration(self.repository.sessions, self.repository.context)
        model, connection = config._model(deployment_id, datetime.now(UTC).date())
        adapter = self._adapter(model.provider_type, connection)
        if operation not in model.operations or operation not in adapter.supported_operations:
            return {"status": "CAPABILITY_UNSUPPORTED", "candidate_models": ()}
        schema = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }
        payload = ProviderInput(
            operation=operation,
            texts=('Return JSON {"ok":true}; safe model connectivity test.',),
            output_schema=schema if operation == "structured_output" else None,
            max_output_tokens=min(model.max_output_tokens, 64),
        )
        try:
            result = adapter.execute(model, payload)
            from crossborder_compliance.application.llm_gateway_services import LLMService

            # The same output validation applies to fixed non-project control-plane probes.
            LLMService._validate_result(payload, model, payload, result)
            status = "HEALTHY"
        except (GatewayDenied, ProviderFailure) as error:
            status = self._failure(error)["status"]
        self.repository.record_health(deployment_id, status)
        return {"status": status, "candidate_models": ()}
