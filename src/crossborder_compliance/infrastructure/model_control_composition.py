"""Canonical control-plane composition, with protected missing-dependency behavior."""

import os

from crossborder_compliance.application.model_control_services import ModelControlService
from crossborder_compliance.infrastructure.llm_gateway_http import check_endpoint
from crossborder_compliance.infrastructure.llm_provider_inspection import ProviderInspection
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence.model_control import (
    PostgresModelControlRepository,
)


def model_control(request, sessions, context):
    factory = getattr(request.app.state, "llm_secret_store_factory", None)
    secrets = factory(context) if factory else None
    if (
        secrets is None
        and os.environ.get("LLM_SECRET_STORE_ROOT")
        and os.environ.get("LLM_SECRET_STORE_KEY")
    ):
        secrets = EncryptedFileSecretStore(
            os.environ["LLM_SECRET_STORE_ROOT"],
            os.environ["LLM_SECRET_STORE_KEY"].encode(),
            context.tenant_id,
        )
    repository = PostgresModelControlRepository(sessions, context)
    service = ModelControlService(repository, context, secrets, check_endpoint)
    return service, ProviderInspection(repository, secrets)
