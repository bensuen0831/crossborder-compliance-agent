"""Explicit loopback-only, real PostgreSQL/HTTP protocol UAT over the canonical host."""

# ruff: noqa: E402 -- direct runner supplies the existing test fixture import roots
import argparse
import json
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from phase1kb_http_servers import local_provider
from test_phase1c_model_registry import _ctx
from test_phase1k_a_configuration_postgres import publish as publish_metadata
from test_phase1kb_control_postgres import configured_model, provider_request, publish

from crossborder_compliance.application.model_control_services import ModelControlService
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.llm_invocation import InvocationPurpose
from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
from crossborder_compliance.infrastructure.llm_gateway_http import check_endpoint
from crossborder_compliance.infrastructure.llm_provider_inspection import ProviderInspection
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.model_control import (
    PostgresModelControlRepository,
)
from frontend.scripts.m2a.uat import create_host
from frontend.scripts.m2d.uat import main as review_main


def candidate_response(payload):
    if payload.get("response_format") and payload["messages"][-1]["content"].startswith("{"):
        data = json.loads(payload["messages"][-1]["content"])
        if "source_nodes" in data:
            targets, nodes = data["allowed_fact_types"], data["source_nodes"]
            return {
                "facts": [
                    {
                        "source_node_id": nodes[-1]["source_node_id"],
                        "fact_type": targets[0],
                        "value": "document requirement note",
                        "confidence": 1.0,
                    }
                ]
                if targets and nodes
                else [],
                "items": [],
                "nodes": [],
                "edges": [],
            }
        if "original_query" in data:
            return {"search_phrases": [data["original_query"]]}
    return {"ok": True}


def seed(args, urls, key):
    saved = sys.argv[:]
    sys.argv = ["uat.py", "--manifest", str(args.manifest), "--seed"]
    review_main()
    sys.argv = saved
    people = json.loads(args.manifest.read_text())
    user = people["INTAKE"]
    tenant = UUID(user["tenant_id"])
    sessions = build_session_factory(get_settings().database_url)[1]
    context = _ctx(tenant)
    repository = PostgresModelControlRepository(sessions, context)
    secrets = EncryptedFileSecretStore(args.secret_root, key, tenant)
    admin = ModelControlService(repository, context, secrets, check_endpoint)
    metadata = PostgresAdminMetadataRepository(sessions, context)
    models, providers = [], []
    for url, names in zip(urls, (("A1", "A2"), ("B1", "B2")), strict=True):
        provider = publish(
            sessions,
            tenant,
            "PROVIDER",
            admin.save_provider(
                provider_request(
                    credential="ci-local-credential", health_ttl_seconds=86400
                ).model_copy(update={"base_url": url})
            ),
        )
        providers.append(provider["provider_id"])
        for name in names:
            model = publish(
                sessions,
                tenant,
                "MODEL",
                configured_model(sessions, tenant, repository, provider, name),
            )
            assert (
                ProviderInspection(repository, secrets).model_test(
                    UUID(model["deployment_id"]), "chat"
                )["status"]
                == "HEALTHY"
            )
            models.append(model["model_id"])
    fact = metadata.create_definition(
        kind="BUSINESS_FACT_TYPE",
        code="DOCUMENT_REQUIREMENT_NOTE",
        display_name="Document note candidate",
    )
    publish_metadata(
        metadata,
        metadata.create_version(definition_id=UUID(fact["definition_id"]), payload={}),
        True,
    )
    usage_payload = {
        "scope_type": "TENANT",
        "project_id": None,
        "default_mode": "INTERNAL_MODEL_ONLY",
        "allowed_operations": ["structured_output"],
        "allowed_model_ids": models,
        "allowed_provider_ids": providers,
        "allowed_trust_levels": ["APPROVED"],
        "allowed_data_boundaries": ["TENANT"],
    }
    definition = metadata.create_definition(
        kind="MODEL_USAGE_POLICY", code=uuid4().hex, display_name="UAT tenant policy"
    )
    publish_metadata(
        metadata,
        metadata.create_version(
            definition_id=UUID(definition["definition_id"]), payload=usage_payload
        ),
        True,
    )
    definition = metadata.create_definition(
        kind="LLM_INVOCATION_POLICY", code=uuid4().hex, display_name="Governed UAT enhancements"
    )
    publish_metadata(
        metadata,
        metadata.create_version(
            definition_id=UUID(definition["definition_id"]),
            payload={
                "allowed_triggers": {
                    mode: [
                        "DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED",
                        "KNOWLEDGE_EVIDENCE_INSUFFICIENT",
                    ]
                    for mode in ("MINIMAL", "STANDARD", "ENHANCED")
                },
                "max_models": 3,
                "candidate_fact_type_ids": [fact["definition_id"]],
                "candidate_min_confidence": 0.95,
            },
        ),
        True,
    )
    prompt_ids = []
    prompts = PostgresGovernedArtifactAdminRepository(sessions, context, "prompts")
    for purpose in (
        InvocationPurpose.DOCUMENT_CANDIDATE_EXTRACTION,
        InvocationPurpose.QUERY_EXPANSION,
    ):
        prompt = publish_metadata(
            prompts,
            prompts.create_draft(
                code=uuid4().hex,
                display_name=purpose.value,
                payload={
                    "template_text": (
                        "Return source-addressed candidates or search text only, "
                        "never legal decisions."
                    ),
                    "capability_requirement": ["STRUCTURED_OUTPUT"],
                },
            ),
        )
        prompts.bind_llm_invocation(UUID(prompt["version_id"]), purpose)
        prompt_ids.append(prompt["definition_id"])
    people["LLM_USER"] = {
        **user,
        "display_name": "Governed AI user",
        "permissions": sorted(
            (set(user["permissions"]) - {"metadata:admin", "metadata:review", "metadata:publish", "knowledge:admin"})
            | {"llm:invoke", "knowledge:retrieve"}
            | {f"prompt:{identity}:use" for identity in prompt_ids}
        ),
        "models": models,
        "project_policy_payload": {**usage_payload, "scope_type": "PROJECT"},
    }
    for name, actor in (("LLM_ADMIN", "model-admin"), ("LLM_REVIEWER", "model-reviewer")):
        people[name] = {
            **user,
            "display_name": actor,
            "actor_id": actor,
            "permissions": sorted(
                set(user["permissions"]) | {"metadata:admin", "metadata:review", "metadata:publish"}
            ),
        }
    people["LLM_ADMIN"]["endpoint"] = urls[0]
    args.manifest.write_text(json.dumps(people, indent=2) + "\n")
    print("Phase1K-B governed PostgreSQL model fixtures seeded; no credentials in manifest")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--secret-root", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    if os.environ.get("PHASE1KB_LOCAL_UAT") != "1":
        raise SystemExit("Explicit loopback-only PHASE1KB_LOCAL_UAT=1 required")
    key = args.key_file.read_bytes()  # Explicit supplied test-store key; never output or archived.
    with ExitStack() as stack:
        urls = [
            stack.enter_context(
                local_provider(names, port=port, structured_response=candidate_response)
            )[0]
            for names, port in ((("A1", "A2"), 9101), (("B1", "B2"), 9102))
        ]
        if args.seed:
            seed(args, urls, key)
            return
        app = create_host(args.manifest)
        from crossborder_compliance.interfaces.api.routes.reviews import router

        app.include_router(router)
        people = json.loads(args.manifest.read_text())
        review_tenant = people["REVIEW"]["tenant_id"]
        app.state.llm_secret_store_factory = lambda context: EncryptedFileSecretStore(
            args.secret_root, key, context.tenant_id
        )

        def prepared(sessions, context, intake, snapshot_id, run_id):
            return prepare_snapshot(
                sessions,
                context,
                intake,
                snapshot_id,
                run_id,
                requirement_confirmation=str(context.tenant_id) == review_tenant,
                llm_dependencies={
                    "storage": app.state.document_object_storage,
                    "secrets": app.state.llm_secret_store_factory(context),
                },
            )

        app.state.intake_snapshot_preparer = prepared
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
