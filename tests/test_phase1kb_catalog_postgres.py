from datetime import date
from uuid import UUID, uuid4

import pytest
from test_phase1k_a_configuration_postgres import publish as publish_metadata
from test_phase1kb_control_postgres import configured_model, provider_request, publish
from test_phase1kb_control_postgres import control as control

from crossborder_compliance.application.intake_services import CreateProjectFromIntake
from crossborder_compliance.application.llm_model_catalog import ModelCatalogQuery
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_model_catalog_composition import model_catalog
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
)

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def catalog(control, request):
    sf, tenant, repo, store, service = control
    owner = RepositoryContext.user(
        tenant, "owner", {"project:create", "project:read", "llm:invoke"}
    )
    intake = PostgresProjectRepository(sf, owner).create_intake(
        CreateProjectFromIntake(
            name="Governed draft",
            idempotency_key=uuid4().hex,
            facts={"analysis_as_of_date": date.today()},
        )
    )
    ctx = RepositoryContext.user(
        tenant, "owner", set(owner.permission.scopes) | {f"project:{intake.project_id}:read"}
    )
    settings = provider_request()
    if getattr(request, "param", None) == "EXTERNAL":
        settings = settings.model_copy(
            update={"deployment_class": "EXTERNAL", "base_url": "https://8.8.8.8/v1"}
        )
    provider = publish(sf, tenant, "PROVIDER", service.save_provider(settings))
    models = [
        publish(sf, tenant, "MODEL", configured_model(sf, tenant, repo, provider, name))
        for name in ("A1", "A2")
    ]
    for model in models:
        repo.record_health(UUID(model["deployment_id"]), "HEALTHY")
    metadata = PostgresAdminMetadataRepository(sf, repo.context)
    for role in ("TENANT", "PROJECT"):
        definition = metadata.create_definition(
            kind="MODEL_USAGE_POLICY", code=uuid4().hex, display_name=role
        )
        version = metadata.create_version(
            definition_id=UUID(definition["definition_id"]),
            payload={
                "scope_type": role,
                "project_id": str(intake.project_id) if role == "PROJECT" else None,
                "default_mode": "EXTERNAL_MODEL_ALLOWED",
                "allowed_operations": ["structured_output", "chat"],
                "allowed_model_ids": [model["model_id"] for model in models],
                "allowed_provider_ids": [provider["provider_id"]],
                "allowed_trust_levels": ["APPROVED"],
                "allowed_data_boundaries": ["TENANT"],
            },
        )
        publish_metadata(metadata, version, True)
    return dict(
        sf=sf,
        tenant=tenant,
        repo=repo,
        ctx=ctx,
        intake=intake,
        provider=provider,
        models=models,
        store=store,
    )


def test_advisory_eligibility_uses_real_policy_health_and_canonical_draft(catalog):
    f = catalog
    result = model_catalog(f["sf"], f["ctx"]).read(
        ModelCatalogQuery(project_id=f["intake"].project_id)
    )
    assert result.status == "AVAILABLE"
    assert {str(model.model_id) for model in result.eligible_models} == {
        model["model_id"] for model in f["models"]
    }
    assert "secret" not in result.model_dump_json()
    f["repo"].set_enabled(
        "MODEL", UUID(f["models"][0]["model_id"]), False, f["models"][0]["model_record_version"]
    )
    refreshed = model_catalog(f["sf"], f["ctx"]).read(
        ModelCatalogQuery(project_id=f["intake"].project_id)
    )
    assert len(refreshed.eligible_models) == 1


@pytest.mark.parametrize("catalog", ["EXTERNAL"], indirect=True)
def test_unresolved_protection_does_not_allow_external_provider(catalog):
    f = catalog
    result = model_catalog(f["sf"], f["ctx"]).read(
        ModelCatalogQuery(project_id=f["intake"].project_id)
    )
    assert result.eligible_models == ()
    assert result.status == "CAPABILITY_NOT_CONFIGURED"


@pytest.mark.parametrize("foreign", [False, True])
def test_catalog_revalidates_project_and_tenant_permission(catalog, foreign):
    f = catalog
    ctx = RepositoryContext.user(
        uuid4() if foreign else f["tenant"], "outsider", {"project:read", "llm:invoke"}
    )
    with pytest.raises(PermissionError):
        model_catalog(f["sf"], ctx).read(ModelCatalogQuery(project_id=f["intake"].project_id))
