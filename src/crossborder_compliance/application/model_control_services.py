"""Admin authorization and endpoint validation precede every secret write."""

from crossborder_compliance.application.metadata_services import AdminActionPolicy
from crossborder_compliance.domain.llm_gateway import GatewayDenied


class ModelControlService:
    def __init__(self, repository, context, secrets, endpoint_validator):
        self.repository, self.context = repository, context
        self.secrets, self.endpoint_validator = secrets, endpoint_validator
        self.policy = AdminActionPolicy()

    def providers(self):
        self.policy.require(self.context, "metadata:admin")
        return self.repository.list_providers()

    def save_provider(self, request):
        self.policy.require(self.context, "metadata:admin")
        # Authorization/concurrency of existing identity before writing a secret.
        if request.provider_id:
            self.repository.require_provider(request.provider_id, request.expected_record_version)
        self.endpoint_validator(request.base_url, request.deployment_class == "EXTERNAL")
        secret_ref = None
        if request.credential is not None:
            if self.secrets is None:
                raise GatewayDenied("SECRET_UNAVAILABLE")
            secret_ref = self.secrets.put(request.credential.get_secret_value())
        return self.repository.save_provider(request, secret_ref)

    def models(self, provider_id):
        self.policy.require(self.context, "metadata:admin")
        return self.repository.list_models(provider_id)

    def save_model(self, provider_id, request):
        self.policy.require(self.context, "metadata:admin")
        return self.repository.save_model(provider_id, request)

    def transition(self, kind, version_id, request):
        return self.repository.transition(kind, version_id, request)

    def enabled(self, kind, identity, request):
        self.policy.require(self.context, "metadata:admin")
        return self.repository.set_enabled(
            kind, identity, request.enabled, request.expected_record_version
        )
