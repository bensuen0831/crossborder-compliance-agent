from contextlib import ExitStack
from datetime import date
from uuid import UUID, uuid4

import pytest
from phase1k_a_fixtures import FakeInputSource
from phase1kb_http_servers import local_provider
from sqlalchemy import select
from test_phase1k_a_configuration_postgres import publish as publish_metadata
from test_phase1kb_control_postgres import configured_model, provider_request, publish
from test_phase1kb_control_postgres import control as control

from crossborder_compliance.application.intake_services import CreateProjectFromIntake
from crossborder_compliance.application.llm_gateway_services import LLMService
from crossborder_compliance.application.llm_invocation_services import GovernedLLMInvocationService
from crossborder_compliance.domain.llm_gateway import (
    AuthorizedInput,
    GatewayDenied,
    InputReference,
    LLMRequest,
)
from crossborder_compliance.domain.llm_invocation import InvocationFacts
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.llm_gateway_http import OpenAICompatibleProviderAdapter
from crossborder_compliance.infrastructure.llm_invocation_governance import (
    PostgresLLMInvocationGovernance,
)
from crossborder_compliance.infrastructure.llm_provider_inspection import ProviderInspection
from crossborder_compliance.infrastructure.persistence.llm_gateway_audit import PostgresGatewayAudit
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    AuditEventEntity,
    ProjectVersionEntity,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
)

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def selected(control, request):
    sf, tenant, repo, store, admin = control
    mode = getattr(request, "param", "AUTO")
    owner = RepositoryContext.user(
        tenant, "owner", {"project:create", "project:read", "llm:invoke"}
    )
    intake = PostgresProjectRepository(sf, owner).create_intake(
        CreateProjectFromIntake(
            name="HTTP selection",
            idempotency_key=uuid4().hex,
            facts={"analysis_as_of_date": date.today()},
        )
    )
    ctx = RepositoryContext.user(
        tenant,
        "owner",
        set(owner.permission.scopes) | {f"project:{intake.project_id}:read", "resource:read"},
    )
    models, providers, calls = [], [], []
    with ExitStack() as stack:
        for names in (("A1", "A2"), ("B1", "B2")):
            url, observed = stack.enter_context(local_provider(names))
            calls.append(observed)
            provider = publish(
                sf,
                tenant,
                "PROVIDER",
                admin.save_provider(
                    provider_request(credential="ci-local-credential").model_copy(
                        update={"base_url": url}
                    )
                ),
            )
            providers.append(provider)
            for name in names:
                model = publish(
                    sf, tenant, "MODEL", configured_model(sf, tenant, repo, provider, name)
                )
                assert (
                    ProviderInspection(repo, store).model_test(
                        UUID(model["deployment_id"]), "chat"
                    )["status"]
                    == "HEALTHY"
                )
                models.append(model)
        for observed in calls:
            observed.clear()
        chosen = (
            []
            if mode == "AUTO"
            else [models[0]["model_id"], models[2]["model_id"]]
            if mode == "MULTI_MODEL"
            else [models[2 if mode == "SINGLE_B" else 0]["model_id"]]
        )
        snapshot, run = uuid4(), uuid4()
        with sf() as s, s.begin():
            version = s.get(ProjectVersionEntity, str(intake.project_version_id))
            version.intake_json = dict(
                version.intake_json,
                ai_model_preference={
                    "usage_mode": "ENHANCED" if mode == "MULTI_MODEL" else "STANDARD",
                    "selection_mode": "SINGLE" if mode.startswith("SINGLE") else mode,
                    "selected_model_ids": chosen,
                },
            )
            version.status = "CONFIRMED"
            s.add(
                AnalysisSnapshotEntity(
                    tenant_id=str(tenant),
                    analysis_snapshot_id=str(snapshot),
                    project_version_id=str(intake.project_version_id),
                    snapshot_version="1",
                    analysis_as_of_date=date.today(),
                    provenance_json={"workflow_run_id": str(run)},
                )
            )
        config = PostgresLLMConfiguration(sf, ctx)
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
                    "default_mode": "INTERNAL_MODEL_ONLY",
                    "allowed_operations": ["structured_output", "chat"],
                    "allowed_model_ids": [model["model_id"] for model in models],
                    "allowed_provider_ids": [provider["provider_id"] for provider in providers],
                    "allowed_trust_levels": ["APPROVED"],
                    "allowed_data_boundaries": ["TENANT"],
                },
            )
            publish_metadata(metadata, version, True)
        definition = metadata.create_definition(
            kind="LLM_INVOCATION_POLICY", code=uuid4().hex, display_name="Invocation"
        )
        policy = publish_metadata(
            metadata,
            metadata.create_version(
                definition_id=UUID(definition["definition_id"]),
                payload={
                    "allowed_triggers": {
                        mode: ["DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED"]
                        for mode in ("STANDARD", "ENHANCED")
                    },
                    "max_models": 3,
                },
            ),
            True,
        )
        ref = InputReference(
            resource_type="SAFE_PROTOCOL_FIXTURE", resource_id=uuid4(), version_id=uuid4()
        )
        item = AuthorizedInput(
            ref=ref,
            tenant_id=tenant,
            project_id=intake.project_id,
            required_scopes=("resource:read",),
            texts=("Safe protocol integration input",),
        )
        query = LLMRequest(
            project_id=intake.project_id,
            analysis_snapshot_id=snapshot,
            operation="structured_output",
            input_refs=(ref,),
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
        )
        config._pin(
            query,
            "LLM_SELECTION",
            "CONFIGURED",
            intake.project_id,
            intake.project_version_id,
            intake.version,
        )
        config._pin(
            query,
            "LLM_INVOCATION_POLICY",
            "INVOCATION",
            policy["definition_id"],
            policy["version_id"],
            policy["version_no"],
        )
        gateway = LLMService(
            context=ctx,
            configuration=config,
            inputs=FakeInputSource({ref: item}),
            providers={"OPENAI_COMPATIBLE": OpenAICompatibleProviderAdapter(config, store)},
            audit=PostgresGatewayAudit(sf, ctx),
        )
        yield dict(
            sf=sf,
            tenant=tenant,
            repo=repo,
            config=config,
            query=query,
            calls=calls,
            models=models,
            service=GovernedLLMInvocationService(gateway, PostgresLLMInvocationGovernance(config)),
            chosen=chosen,
            facts=InvocationFacts(
                trigger="DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED",
                purpose="DOCUMENT_CANDIDATE_EXTRACTION",
                parser_insufficient=True,
            ),
        )


@pytest.mark.parametrize("selected", ["AUTO", "SINGLE_A", "SINGLE_B", "MULTI_MODEL"], indirect=True)
def test_selection_through_real_two_provider_http_and_durable_audit(selected):
    f = selected
    result = f["service"].invoke(f["query"], f["facts"])
    assert result.status == "COMPLETED" and result.authority == "DERIVED_CANDIDATE"
    assert all(child.result.result.structured == {"ok": True} for child in result.model_results)
    assert len({child.request_id for child in result.model_results}) == len(result.model_results)
    if f["chosen"]:
        assert [str(child.model_id) for child in result.model_results] == f["chosen"]
    with f["sf"]() as s:
        audits = s.scalars(
            select(AuditEventEntity).where(
                AuditEventEntity.analysis_snapshot_id == str(f["query"].analysis_snapshot_id),
                AuditEventEntity.event_type == "LLM_COMPLETED",
            )
        ).all()
        assert len(audits) == len(result.model_results)
        assert all(row.provenance_json["usage"]["total_tokens"] == 8 for row in audits)
        assert all(
            row.provenance_json["invocation_group_id"] == str(result.invocation_group_id)
            for row in audits
        )
        assert all("ci-local-credential" not in str(row.provenance_json) for row in audits)
    assert sum(len(calls) for calls in f["calls"]) == len(result.model_results)


@pytest.mark.parametrize("selected", ["SINGLE_A"], indirect=True)
def test_single_current_revocation_denied_without_other_provider_fallback(selected):
    f = selected
    model = f["models"][0]
    f["repo"].set_enabled("MODEL", UUID(model["model_id"]), False, model["model_record_version"])
    with pytest.raises(GatewayDenied, match="MODEL_SELECTION_NOT_ALLOWED"):
        f["service"].invoke(f["query"], f["facts"])
    assert not any(f["calls"])


def test_policy_trigger_blocks_sufficient_deterministic_extraction_before_http(selected):
    f = selected
    with pytest.raises(GatewayDenied, match="DETERMINISTIC_EXTRACTION_SUFFICIENT"):
        f["service"].invoke(
            f["query"], f["facts"].model_copy(update={"parser_insufficient": False})
        )
    assert not any(f["calls"])
