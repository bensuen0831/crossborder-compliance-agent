"""Track B boundaries with an explicit approved Phase 1H integration baseline.

The original source-track manifest remains immutable historical evidence.
Integration may use only the verified Phase 1H baseline, not hashes of live files.
"""

import ast
import hashlib
import json
import subprocess
from pathlib import Path


def check(root):
    root = Path(root)
    manifest = json.loads((root / "evidence/phase1k-a/frozen_baseline_manifest.json").read_text())[
        "files"
    ]
    integration = root / "evidence/stage1-alpha/approved_phase1h_baseline.json"
    baseline_authorized = True
    if integration.exists():
        approved = json.loads(integration.read_text())
        baseline_authorized = (
            approved["base_sha"] == "700951ebb9ebdf33e399158fd3fb53bb4a6c87e7"
            and approved["original_track_b_base"] == "f563e5067308e7eab6d3f89321b8b30da7c39044"
            and set(approved["files"]) == set(manifest)
            | {"alembic/versions/0008_phase1h_rule_classification.py"}
        )
        manifest = approved["files"]
    round2 = root / "evidence/round2-integration/approved_phase1i_baseline.json"
    if round2.exists():
        approved_i = json.loads(round2.read_text())
        baseline_authorized = baseline_authorized and (
            approved_i["base_sha"] == "14cba25353d9ab7dda84e9620ff3197d9e2a3d1d"
            and approved_i["original_track_b_base"] == "f563e5067308e7eab6d3f89321b8b30da7c39044"
            and set(approved_i["files"]) == set(manifest)
            | {"alembic/versions/0009_phase1i_applicability.py"}
        )
        # Verify the approved hashes against exact reviewed Git blobs, never
        # derive approval from the files currently being checked.
        baseline_authorized = baseline_authorized and all(
            hashlib.sha256(subprocess.check_output(
                ["git", "show", approved_i["base_sha"] + ":" + path], cwd=root
            )).hexdigest() == digest
            for path, digest in approved_i["files"].items()
        )
        manifest = approved_i["files"]
    files = list((root / "src").rglob("llm_gateway*.py"))
    source = {p.name: p.read_text() for p in files}
    appfiles = [p for p in files if "/application/" in str(p) or "/domain/" in str(p)]
    imports = []
    for p in appfiles:
        for n in ast.walk(ast.parse(p.read_text())):
            if isinstance(n, ast.Import):
                imports.extend(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                imports.append(n.module or "")
    denied = ("sqlalchemy", "langgraph", "httpx", "requests", "openai", "ollama", "qwen", "vllm")
    domain = source["llm_gateway.py"]
    ports = source["llm_gateway_ports.py"]
    policy = source["llm_gateway_policy.py"]
    services = source["llm_gateway_services.py"]
    redact = source["llm_gateway_redaction.py"]
    config = source["llm_gateway_configuration.py"]
    http = source["llm_gateway_http.py"]
    trees = [ast.parse(p.read_text()) for p in files]
    checks = {
        "approved_frozen_implementation_unchanged": baseline_authorized and all(
            (root / p).is_file() and hashlib.sha256((root / p).read_bytes()).hexdigest() == h
            for p, h in manifest.items()
        ),
        "approved_migrations_unchanged_no_integration_migration": set(
            str(p.relative_to(root)) for p in (root / "alembic/versions").glob("*.py")
        )
        == {p for p in manifest if p.startswith("alembic/versions/") and p.endswith(".py")},
        "domain_application_provider_sdk_orm_free": not any(
            i.split(".")[0] in denied or ".infrastructure" in i for i in imports
        ),
        "no_parallel_registry": not any(
            isinstance(n, ast.ClassDef) and "Registry" in n.name for t in trees for n in ast.walk(t)
        ),
        "existing_model_registry_reused": "ModelRegistry(PostgresModelRegistryRepository" in config,
        "existing_governed_policy_source_reused": "PostgresRegistrySourceRepository" in config
        and "MODEL_USAGE_POLICY" in config,
        "existing_prompt_registry_reused": "PromptRegistry(PostgresConfigRegistrySourceRepository"
        in "".join(config.split()),
        "existing_snapshot_pins_reused": "PostgresSnapshotRegistryPinRepository" in config,
        "canonical_capabilities_reused": "domain.metadata import ModelCapabilityCode" in domain,
        "all_seven_service_operations": all(
            "def " + op + "(" in ports
            for op in (
                "chat",
                "chat_stream",
                "structured_output",
                "embedding",
                "rerank",
                "count_tokens",
                "health_check",
            )
        ),
        "request_is_reference_only": "input_refs: tuple[InputReference" in domain
        and "tenant_id"
        not in domain.split("class LLMRequest")[1].split("class AuthorizedInput")[0],
        "policy_precedes_router_and_call": services.index("self.policy.evaluate")
        < services.index("self.router.route")
        < services.index("provider.execute"),
        "tenant_project_policy_intersection": "TENANT_PROJECT_POLICY_INTERSECTION" in policy
        and "RESOURCE_NOT_FOUND" in services,
        "model_policy_restricts_fallback_pool": "decision.allowed_model_ids" in policy
        and "decision.allowed_provider_ids" in policy,
        "redaction_proof_validated_before_external": "DataRedactionService.validate" in services
        and "REDACTION_NOT_VALIDATED" in redact,
        "irreversible_mapping_boundary": "reversible: Literal[False]" in domain
        and "result.reversibleor" in "".join(redact.split()),
        "secret_values_only_in_transport": "self.secrets.resolve" in http
        and "secret_ref" not in domain,
        "safe_audit_shape": "class GatewayAuditEvent" in domain
        and "texts:"
        not in domain.split("class GatewayAuditEvent")[1].split("class GatewayDenied")[0],
        "partial_stream_cannot_fallback": "PARTIAL_STREAM_FAILED" in services,
        "http_redirects_and_remote_schema_refs_denied": "follow_redirects=False" in http
        and "$dynamicRef" in services
        and "REMOTE_SCHEMA_REFERENCE_DENIED" in services,
    }
    return {
        "phase": "1K-A boundary",
        "passed": sum(checks.values()),
        "total": len(checks),
        "pass": all(checks.values()),
        "checks": checks,
    }


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)
