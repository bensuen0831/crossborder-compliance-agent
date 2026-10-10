"""Additive gateway ownership checks, preserving all280 recovery checks."""

import ast
import json
from pathlib import Path


def check(root):
    root = Path(root)

    def read(path):
        return (root / path).read_text()

    facade = read("src/crossborder_compliance/application/external_channel.py")
    identity = read("src/crossborder_compliance/infrastructure/persistence/integrations.py")
    routes = read("src/crossborder_compliance/interfaces/api/routes/external.py")
    worker = read("src/crossborder_compliance/infrastructure/integration_worker.py")
    composition = read("src/crossborder_compliance/infrastructure/external_composition.py")
    contract = read("src/crossborder_compliance/domain/integrations.py")
    callback = read("src/crossborder_compliance/infrastructure/webhook_http.py")
    ui = "\n".join(
        p.read_text()
        for p in (root / "frontend/src/features/integrations").glob("*.tsx")
        if ".test." not in p.name
    )
    sdk = "\n".join(
        read(path)
        for path in ["sdk/typescript/src/client.ts", "sdk/python/src/crossborder_agent/client.py"]
    )
    imports = [
        ast.unparse(node)
        for node in ast.walk(ast.parse(facade))
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    forbidden = ("decision_engine", "rule_engine", "langgraph", "llm_gateway", "ProviderAdapter")
    no_owners = not any(value in "\n".join(imports) for value in forbidden)
    from crossborder_compliance.interfaces.api.external_openapi import external_openapi
    from scripts.m2e_r1_architecture_check import check as recovery

    public = external_openapi()
    checks = {
        "external_api_is_channel_only": no_owners and "ExternalChannelService" in facade,
        "external_uses_canonical_application_services": all(
            x in facade
            for x in [
                "CreateProjectFromIntake",
                "UpdateIntakeDraft",
                "canonical.intake",
                "canonical.documents",
            ]
        ),
        "external_has_no_legal_owner": no_owners and "calculate_risk" not in facade,
        "external_cannot_call_rule_engine_directly": no_owners,
        "external_cannot_call_langgraph_directly": no_owners,
        "external_cannot_call_provider_directly": no_owners and "api.openai" not in routes,
        "external_result_uses_stage1_result_authority": "canonical_workflow.stage1_result"
        in composition,
        "external_auth_maps_to_repository_context": "RepositoryContext.user(" in identity
        and "system=True" not in identity,
        "integration_secret_not_provider_secret": "INTEGRATION_SECRET_STORE_KEY" in composition
        and "LLM_SECRET_STORE_KEY" not in composition,
        "tenant_authority_is_server_owned": public["components"]["schemas"][
            "ExternalProjectCreate"
        ]["additionalProperties"]
        is False
        and "tenant_id"
        not in public["components"]["schemas"]["ExternalProjectCreate"]["properties"],
        "formal_result_fields_are_server_owned": public["components"]["schemas"][
            "WorkflowStart"
        ].get("properties")
        == {},
        "project_binding_required": 'Binding.status == "ACTIVE"' in identity
        and "PROJECT_ACCESS_DENIED" in identity,
        "scope_required": "required not in active" in identity
        and "CANONICAL_SCOPE_MAP" in contract,
        "model_selection_revalidated": "canonical.eligible_models" in facade
        and "IntegrationScope.MODEL_SELECT" in facade,
        "async_worker_not_workflow_runtime": "canonical_workflow.start(" in worker
        and "StateGraph" not in worker,
        "sse_uses_canonical_events": "service.events" in routes
        and "RuntimeRepository(self.sessions).workflow_events" in composition,
        "websocket_uses_canonical_events": "ch.events" in routes
        and "ExternalWorkflowEvent" in composition,
        "webhook_uses_canonical_events": "composition.event(" in worker,
        "webhook_secret_write_only": "secret_ref=self.store.put(raw)"
        in read("src/crossborder_compliance/infrastructure/persistence/webhooks.py")
        .replace(" ", "")
        .replace("\n", "")
        and "writeOnly" in contract,
        "webhook_ssrf_governed": "not ip.is_global" in callback
        and "socket.create_connection((ips[0],port)" in callback,
        "idempotency_server_owned": "pg_advisory_xact_lock" in identity
        and "IDEMPOTENCY_CONFLICT" in identity,
        "quota_not_business_logic": "QUOTA_EXCEEDED" in identity and no_owners,
        "rate_limit_not_business_logic": "RATE_LIMITED" in identity and no_owners,
        "external_openapi_excludes_internal_routes": all(
            p.startswith("/api/v1/external/") for p in public["paths"]
        ),
        "sdk_contains_no_legal_logic": not any(
            x in sdk
            for x in [
                "RuleEngine",
                "calculate_risk",
                "DIRECT_TRANSFER_ALLOWED",
                "CONDITIONAL_TRANSFER_ALLOWED",
                "StateGraph",
                "classification.execute",
            ]
        ),
        "r1_jurisdiction_identity_preserved": recovery(root)["pass_"],
        "stage2_not_started": not any(
            x in ui + sdk + facade for x in ["generate_scc(", "generate_contract(", "Stage2Runtime"]
        ),
    }
    return {
        "total": len(checks),
        "passed": sum(checks.values()),
        "pass_": all(checks.values()),
        "checks": checks,
    }


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass_"] else 1)
