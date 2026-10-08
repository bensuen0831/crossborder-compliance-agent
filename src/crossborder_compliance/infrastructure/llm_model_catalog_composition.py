"""Draft advisory reads reuse canonical Project intake and model registry adapters."""

from crossborder_compliance.application.llm_model_catalog import EligibleModelCatalogService
from crossborder_compliance.domain.llm_gateway import AuthorizedInput, InputReference
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
)


def model_catalog(sessions, context):
    configuration = PostgresLLMConfiguration(sessions, context, draft_catalog=True)

    def profile(project_id):
        intake = PostgresProjectRepository(sessions, context).read_intake(project_id)
        # Intake business categories are not authoritative security/grade labels.
        # Unknown protection labels retain the gateway's existing internal-only semantics.
        return (
            AuthorizedInput(
                ref=InputReference(
                    resource_type="PROJECT_INTAKE",
                    resource_id=project_id,
                    version_id=intake.project_version_id,
                ),
                tenant_id=context.tenant_id,
                project_id=project_id,
                required_scopes=("project:read",),
                texts=(intake.intake.scenario_description or "",),
            ),
        )

    return EligibleModelCatalogService(configuration, profile, context)
