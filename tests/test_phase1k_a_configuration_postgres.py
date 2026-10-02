from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from phase1k_a_fixtures import FakeAudit, FakeInputSource, FakeProvider
from sqlalchemy import func, select
from test_phase1c_model_registry import _ctx, _seed_tenant, _sf

from crossborder_compliance.application.llm_gateway_services import LLMService
from crossborder_compliance.domain.llm_gateway import (
    AuthorizedInput,
    GatewayDenied,
    InputReference,
    LLMRequest,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
    PostgresModelRegistryRepository,
)
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresModelAdminRepository,
)

pytestmark = pytest.mark.runtime_smoke


def publish(repo, version, generic=False):
    for status in ("PENDING_REVIEW", "APPROVED", "ACTIVE"):
        kwargs = dict(target_status=status, expected_record_version=version["record_version"])
        if generic:
            kwargs["actor_id"] = "independent-reviewer" if status == "APPROVED" else "publisher"
        version = repo.transition(UUID(str(version["version_id"])), **kwargs)
    return version


@pytest.fixture
def foundation():
    sf = _sf()
    tenant, project, pv, snapshot = [uuid4() for _ in range(4)]
    _seed_tenant(sf, tenant)
    with sf() as s, s.begin():
        s.add(
            b.ProjectEntity(
                tenant_id=str(tenant), project_id=str(project), name="Generic Track B Project"
            )
        )
        s.flush()
        s.add(
            b.ProjectVersionEntity(
                tenant_id=str(tenant),
                project_id=str(project),
                project_version_id=str(pv),
                version_no=1,
                intake_json={},
            )
        )
        s.flush()
        s.add(
            b.AnalysisSnapshotEntity(
                tenant_id=str(tenant),
                analysis_snapshot_id=str(snapshot),
                project_version_id=str(pv),
                snapshot_version="1",
                analysis_as_of_date=date.today(),
                provenance_json={},
            )
        )
    modelrepo = PostgresModelAdminRepository(sf, _ctx(tenant))
    draft = modelrepo.create_draft(
        code=uuid4().hex,
        display_name="Generic approved model",
        payload={
            "provider_type": "GENERIC_REST",
            "model_id": "generic-test-model",
            "deployment_ref": "generic-test-deploy",
            "endpoint_config": {
                "url": "https://generic-model.invalid/v1",
                "operations": ["chat", "chat_stream"],
                "paths": {"chat": "/invoke"},
            },
            "auth_type": "BEARER_SECRET_REF",
            "secret_ref": "secret://generic/tenant-model",
            "deployment_type": "PRIVATE_CLOUD",
            "trust_level": "APPROVED",
            "data_boundary": "TENANT",
            "capabilities": ["TEXT"],
            "max_output_tokens": 4096,
            "enabled": True,
        },
    )
    publish(modelrepo, draft)
    with sf() as s, s.begin():
        s.add(
            m.ModelHealthMetadataEntity(
                tenant_id=str(tenant),
                model_health_metadata_id=str(uuid4()),
                model_deployment_id=draft["version_id"],
                health_status="HEALTHY",
            )
        )
    policyrepo = PostgresAdminMetadataRepository(sf, _ctx(tenant))
    policies = []
    payload = dict(
        default_mode="INTERNAL_MODEL_ONLY",
        allowed_model_ids=[draft["definition_id"]],
        allowed_provider_ids=[draft["provider_id"]],
        allowed_trust_levels=["APPROVED"],
        allowed_data_boundaries=["TENANT"],
        allowed_operations=["chat", "chat_stream"],
    )
    for role in ("TENANT", "PROJECT"):
        definition = policyrepo.create_definition(
            kind="MODEL_USAGE_POLICY", code=uuid4().hex, display_name="Generic usage policy"
        )
        data = dict(
            payload, scope_type=role, project_id=str(project) if role == "PROJECT" else None
        )
        v = policyrepo.create_version(
            definition_id=UUID(str(definition["definition_id"])), payload=data
        )
        policies.append(publish(policyrepo, v, True))
    ctx = RepositoryContext.user(
        tenant, "gateway-user", {"llm:invoke", f"project:{project}:read", "resource:read"}
    )
    config = PostgresLLMConfiguration(sf, ctx)
    ref = InputReference(resource_type="GENERIC_DOCUMENT", resource_id=uuid4(), version_id=uuid4())
    item = AuthorizedInput(
        ref=ref,
        tenant_id=tenant,
        project_id=project,
        required_scopes=("resource:read",),
        texts=("generic sensitive body",),
    )
    request = LLMRequest(
        project_id=project, analysis_snapshot_id=snapshot, operation="chat", input_refs=(ref,)
    )
    provider = FakeProvider()
    service = LLMService(
        context=ctx,
        configuration=config,
        inputs=FakeInputSource({ref: item}),
        providers={"GENERIC_REST": provider},
        audit=FakeAudit(),
    )
    return dict(
        sf=sf,
        tenant=tenant,
        project=project,
        pv=pv,
        snapshot=snapshot,
        ctx=ctx,
        config=config,
        request=request,
        model=draft,
        policies=policies,
        policyrepo=policyrepo,
        service=service,
        provider=provider,
    )


def test_existing_registry_governance_and_pins_real_postgres(foundation):
    f = foundation
    result = f["service"].chat(f["request"])
    assert str(result.model_id) == f["model"]["definition_id"]
    pins = f["config"].pins.list_pins(f["snapshot"])
    assert [p["pin_type"] for p in pins].count("LLM_USAGE_POLICY") == 2
    assert [p["pin_type"] for p in pins].count("LLM_MODEL") == 1
    assert (
        "secret_ref" not in result.model_dump_json()
        and "generic/tenant-model" not in result.model_dump_json()
    )
    assert f["config"].model_registry.health()["source_of_truth"] is False


def test_published_new_policy_does_not_refresh_old_analysis(foundation):
    f = foundation
    first = f["service"].chat(f["request"])
    prior = f["policies"][1]
    new = f["policyrepo"].create_version(
        definition_id=UUID(prior["definition_id"]),
        payload=dict(prior["payload"], allowed_model_ids=[]),
    )
    publish(f["policyrepo"], new, True)
    resumed = f["service"].chat(f["request"])
    assert resumed.policy.policy_versions == first.policy.policy_versions
    new_snapshot = uuid4()
    with f["sf"]() as s, s.begin():
        s.add(
            b.AnalysisSnapshotEntity(
                tenant_id=str(f["tenant"]),
                analysis_snapshot_id=str(new_snapshot),
                project_version_id=str(f["pv"]),
                snapshot_version="2",
                analysis_as_of_date=date.today(),
                provenance_json={},
            )
        )
    before = len(f["provider"].calls)
    with pytest.raises(GatewayDenied):
        f["service"].chat(f["request"].model_copy(update={"analysis_snapshot_id": new_snapshot}))
    assert len(f["provider"].calls) == before


def test_disabled_pinned_model_cannot_refresh_or_escape(foundation):
    f = foundation
    f["service"].chat(f["request"])
    PostgresModelRegistryRepository(f["sf"], f["ctx"]).set_provider_enabled(
        UUID(f["model"]["provider_id"]), False
    )
    before = len(f["provider"].calls)
    with pytest.raises(GatewayDenied):
        f["service"].chat(f["request"])
    assert len(f["provider"].calls) == before


@pytest.mark.parametrize("kind", ("tenant", "project", "snapshot", "permission"))
def test_scope_denial_precedes_model_and_policy_resolution(foundation, kind):
    f = foundation
    request = f["request"]
    config = f["config"]
    if kind == "tenant":
        config = PostgresLLMConfiguration(
            f["sf"], RepositoryContext.user(uuid4(), "foreign", {"llm:invoke"})
        )
    if kind == "project":
        request = request.model_copy(update={"project_id": uuid4()})
    if kind == "snapshot":
        request = request.model_copy(update={"analysis_snapshot_id": uuid4()})
    if kind == "permission":
        config = PostgresLLMConfiguration(
            f["sf"], RepositoryContext.user(f["tenant"], "no-project-access", {"llm:invoke"})
        )
    with pytest.raises(GatewayDenied, match="RESOURCE_NOT_FOUND"):
        config.authorize(request)


def test_unknown_health_and_effective_date_excluded(foundation):
    f = foundation
    with f["sf"]() as s, s.begin():
        health = s.scalar(
            select(m.ModelHealthMetadataEntity).where(
                m.ModelHealthMetadataEntity.model_deployment_id == f["model"]["version_id"]
            )
        )
        health.observed_at -= timedelta(days=1)
    with pytest.raises(GatewayDenied):
        f["service"].chat(f["request"])
    assert not f["provider"].calls
    with f["sf"]() as s, s.begin():
        row = s.get(m.ModelDeploymentEntity, f["model"]["version_id"])
        row.effective_to = date.today() - timedelta(days=1)
    assert f["config"].models(f["request"]) == ()


def test_model_pin_is_immutable(foundation):
    f = foundation
    f["service"].chat(f["request"])
    model = f["config"].models(f["request"])[0]
    with pytest.raises(Exception, match="immutable"):
        f["config"].pin_models(f["request"], (model.model_copy(update={"deployment_id": uuid4()}),))


def test_policy_rollback_emits_no_publication(foundation):
    f = foundation
    with f["sf"]() as s:
        before = s.scalar(
            select(func.count())
            .select_from(m.RegistrySyncEventEntity)
            .where(m.RegistrySyncEventEntity.tenant_id == str(f["tenant"]))
        )
    with pytest.raises(RuntimeError):
        with f["sf"]() as s, s.begin():
            s.add(
                m.MetadataVersionEntity(
                    tenant_id=str(f["tenant"]),
                    version_id=str(uuid4()),
                    definition_id=f["policies"][0]["definition_id"],
                    version_no=99,
                    lifecycle_status="DRAFT",
                    payload_json={},
                    created_by="test-drafter",
                )
            )
            s.flush()
            raise RuntimeError("rollback")
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(m.RegistrySyncEventEntity)
                .where(m.RegistrySyncEventEntity.tenant_id == str(f["tenant"]))
            )
            == before
        )


def test_prompt_registry_reuse_and_pin(foundation):
    f = foundation
    admin = PostgresGovernedArtifactAdminRepository(f["sf"], _ctx(f["tenant"]), "prompts")
    draft = admin.create_draft(
        code=uuid4().hex,
        display_name="Generic governed prompt",
        payload={"template_text": "Generic trusted prompt", "capability_requirement": ["TEXT"]},
    )
    publish(admin, draft)
    prompt = UUID(draft["definition_id"])
    request = f["request"].model_copy(update={"prompt_id": prompt})
    with pytest.raises(GatewayDenied):
        f["config"].prompt(request)
    ctx = RepositoryContext.user(
        f["tenant"], "prompt-user", set(f["ctx"].permission.scopes) | {f"prompt:{prompt}:use"}
    )
    config = PostgresLLMConfiguration(f["sf"], ctx)
    assert config.prompt(request) == "Generic trusted prompt"
    assert any(p["pin_type"] == "LLM_PROMPT" for p in config.pins.list_pins(f["snapshot"]))
