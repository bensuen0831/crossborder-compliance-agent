from datetime import date
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from phase1g_fixtures import publish as publish_knowledge
from phase1kb_http_servers import local_provider
from test_phase1c_model_registry import _ctx
from test_phase1f_postgres import binding
from test_phase1f_postgres import fixture as fixture
from test_phase1f_postgres import metadata as authority_metadata
from test_phase1g_persistence_postgres import policies, query, service
from test_phase1k_a_configuration_postgres import publish as publish_metadata
from test_phase1kb_control_postgres import configured_model, provider_request, publish

from crossborder_compliance.application.model_control_services import ModelControlService
from crossborder_compliance.domain.contracts import ProjectIntakeContext
from crossborder_compliance.domain.llm_invocation import InvocationPurpose
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_gateway_http import check_endpoint
from crossborder_compliance.infrastructure.llm_provider_inspection import ProviderInspection
from crossborder_compliance.infrastructure.llm_query_expansion import query_expansion_planner
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.llm_snapshot_pins import freeze_llm_configuration
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.model_control import (
    PostgresModelControlRepository,
)

pytestmark = pytest.mark.runtime_smoke


def llm_frame(f, tmp_path, url):
    tenant = UUID(f["tenant"])
    admin_context = _ctx(tenant)
    repository = PostgresModelControlRepository(f["sf"], admin_context)
    secrets = EncryptedFileSecretStore(tmp_path / "secrets", Fernet.generate_key(), tenant)
    admin = ModelControlService(repository, admin_context, secrets, check_endpoint)
    provider = publish(
        f["sf"],
        tenant,
        "PROVIDER",
        admin.save_provider(
            provider_request(credential="ci-local-credential").model_copy(update={"base_url": url})
        ),
    )
    model = publish(
        f["sf"], tenant, "MODEL", configured_model(f["sf"], tenant, repository, provider, "A1")
    )
    assert (
        ProviderInspection(repository, secrets).model_test(UUID(model["deployment_id"]), "chat")[
            "status"
        ]
        == "HEALTHY"
    )
    metadata = PostgresAdminMetadataRepository(f["sf"], admin_context)
    for role in ("TENANT", "PROJECT"):
        definition = metadata.create_definition(
            kind="MODEL_USAGE_POLICY", code=uuid4().hex, display_name=role
        )
        publish_metadata(
            metadata,
            metadata.create_version(
                definition_id=UUID(definition["definition_id"]),
                payload={
                    "scope_type": role,
                    "project_id": f["project"] if role == "PROJECT" else None,
                    "default_mode": "INTERNAL_MODEL_ONLY",
                    "allowed_operations": ["structured_output"],
                    "allowed_model_ids": [model["model_id"]],
                    "allowed_provider_ids": [provider["provider_id"]],
                    "allowed_trust_levels": ["APPROVED"],
                    "allowed_data_boundaries": ["TENANT"],
                },
            ),
            True,
        )
    definition = metadata.create_definition(
        kind="LLM_INVOCATION_POLICY", code=uuid4().hex, display_name="Expansion"
    )
    publish_metadata(
        metadata,
        metadata.create_version(
            definition_id=UUID(definition["definition_id"]),
            payload={
                "allowed_triggers": {"STANDARD": ["KNOWLEDGE_EVIDENCE_INSUFFICIENT"]},
                "max_models": 3,
                "query_expansion_limit": 2,
            },
        ),
        True,
    )
    prompts = PostgresGovernedArtifactAdminRepository(f["sf"], admin_context, "prompts")
    prompt = publish_metadata(
        prompts,
        prompts.create_draft(
            code=uuid4().hex,
            display_name="Search text only",
            payload={
                "template_text": "Return search phrases only, never legal evidence. Preserve scope.",
                "capability_requirement": ["STRUCTURED_OUTPUT"],
            },
        ),
    )
    prompts.bind_llm_invocation(UUID(prompt["version_id"]), InvocationPurpose.QUERY_EXPANSION)
    intake = ProjectIntakeContext(
        project_id=UUID(f["project"]),
        analysis_as_of_date=date.today(),
        project_name="Query fixture",
        provenance={
            "source_type": "USER_INPUT",
            "source_ref": "test-fixture",
            "generated_by": "test-fixture",
        },
    )
    with f["sf"]() as s, s.begin():
        snapshot = s.get(b.AnalysisSnapshotEntity, f["snapshot"])
        version = s.get(b.ProjectVersionEntity, snapshot.project_version_id)
        version.intake_json = intake.model_dump(mode="json")
        version.status = "CONFIRMED"
        snapshot.provenance_json = {**snapshot.provenance_json, "workflow_run_id": str(uuid4())}
    context = RepositoryContext.user(
        tenant,
        "author",
        set(f["ctx"].permission.scopes)
        | {
            "llm:invoke",
            "knowledge:retrieve",
            f"project:{f['project']}:read",
            f"prompt:{prompt['definition_id']}:use",
        },
    )
    assert freeze_llm_configuration(f["sf"], context, intake, UUID(f["snapshot"])) == "CONFIGURED"
    f["ctx"] = context
    return secrets


@pytest.mark.parametrize("authoritative", [True, False])
def test_real_http_query_expansion_same_scope_and_no_model_memory_evidence(
    fixture, tmp_path, authoritative
):
    f = fixture
    if authoritative:
        authority = authority_metadata(f["sf"], f["tenant"], "AUTHORITY")
        f["source"] = f["repo"].create_source(
            {
                "collection_id": f["col"],
                "code": uuid4().hex,
                "source_type": "OFFICIAL_LEGISLATION",
                "authority_ref": authority,
                "canonical_url": "https://generic.example/official-authority.json",
                "jurisdiction_refs": [f["juri"]],
                "trust_level": "APPROVED",
                "language": "en",
                "validation_status": "VALIDATED",
                "provenance": {"fixture": True},
            }
        )["source_id"]
    dimensions = {"product": [f["a"]], **({"jurisdiction": [f["juri"]]} if authoritative else {})}
    good = publish_knowledge(f, [binding(f, dimensions=dimensions)])
    forbidden = publish_knowledge(f, [binding(f, dimensions={"product": [f["b"]]})])
    for version in (good, forbidden):
        f["repo"].build_index(version["knowledge_version_id"])
    with local_provider(
        structured_response={
            "search_phrases": ["Generic", "unrelated jurisdiction", "invented law"]
        }
    ) as (url, calls):
        secrets = llm_frame(f, tmp_path, url)
        r, policy, _ = policies(f)
        q = query(f, policy, query_text="initialtermdoesnotexist")
        planner = query_expansion_planner(f["sf"], f["ctx"], q, secrets=secrets)
        result = service(f, r, query_expansion=planner).retrieve(q)
        rag = result["rag_context_pack"]
        assert len(rag["evidence_pack"]["items"]) == 2
        assert {item["knowledge_version_id"] for item in rag["evidence_pack"]["items"]} == {
            good["knowledge_version_id"]
        }
        assert rag["knowledge_sufficiency"]["status"] == (
            "SUFFICIENT" if authoritative else "INSUFFICIENT"
        )
        assert rag["evidence_pack"]["manifest"]["query_expansion"] == {
            "authority": "DERIVED_CANDIDATE",
            "query_count": 2,
            "rounds": 1,
        }
        assert len([call for call in calls if call[1] == "structured_output"]) == 1
        repeat = service(f, r, query_expansion=planner).retrieve(q)
        assert repeat["retrieval_run_id"] == result["retrieval_run_id"]
        assert len([call for call in calls if call[1] == "structured_output"]) == 1
        # Once authoritative evidence is sufficient the helper itself fails closed.
        if authoritative:
            from crossborder_compliance.domain.retrieval import KnowledgeSufficiencyResult

            assert (
                planner.plan(
                    q.query_text,
                    KnowledgeSufficiencyResult.model_validate(rag["knowledge_sufficiency"]),
                )
                == ()
            )
