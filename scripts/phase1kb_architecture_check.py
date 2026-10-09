"""Additive LLM governance checks; permanent architecture rules remain unchanged."""

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.phase1kb_ownership import overlay


def check(root):
    root = Path(root)
    src = root / "src/crossborder_compliance"

    def read(path):
        return (src / path).read_text()

    policy = read("application/llm_invocation_policy.py")
    invocation = read("application/llm_invocation_services.py")
    domain = read("domain/llm_invocation.py")
    router = read("application/llm_gateway_policy.py")
    pins = read("infrastructure/llm_snapshot_pins.py")
    frozen = read("infrastructure/llm_invocation_governance.py")
    query = read("infrastructure/llm_query_expansion.py")
    retrieval = read("application/retrieval_services.py")
    extract = read("application/llm_document_extraction.py")
    ui = (root / "frontend/src/features/models/AISettings.tsx").read_text()
    admin = (root / "frontend/src/features/models/ModelProviders.tsx").read_text()
    api = read("interfaces/api/model_schemas.py")
    secret = read("infrastructure/llm_secrets.py")
    table_names = [
        n.value.value
        for p in (src / "infrastructure/persistence").glob("*.py")
        for n in ast.walk(ast.parse(p.read_text()))
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in n.targets)
        and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
    ]
    legal_types = (
        "ClassificationResultEntity(",
        "RegulationApplicabilityResultEntity(",
        "CrossBorderAssessmentEntity(",
        "ComplianceObligationEntity(",
        "FormalRiskResultEntity(",
        "FinalCompliancePathEntity(",
        "RequiredDocumentEntity(",
    )
    llm_source = "\n".join(
        p.read_text()
        for folder in ("application", "infrastructure")
        for p in (src / folder).glob("llm_*.py")
    )
    valid, paths, source = overlay(root)
    candidate_only = all(t not in llm_source for t in legal_types)
    checks = {
        "single_model_registry": table_names.count("model_definitions") == 1,
        "single_provider_registry": table_names.count("model_providers") == 1,
        "llm_invocation_requires_policy_trigger": "evaluate(policy, preference, facts)"
        in invocation,
        "rag_first_boundary_preserved": "query_expansion" in retrieval
        and '"INSUFFICIENT"' in retrieval,
        "evidence_first_boundary_preserved": "EvidencePack" in retrieval
        and "DERIVED_QUERY_NOT_LEGAL_EVIDENCE" in retrieval,
        "llm_parametric_knowledge_is_not_evidence": "LegalBasisEntity(" not in query
        and "EvidenceEntity(" not in query,
        "frontend_never_calls_provider_directly": "client.saveProvider(" in admin
        and "eligible-models" in ui
        and "fetch('https:" not in admin + ui,
        "admin_secret_is_write_only": "repr=False, exclude=True" in read("domain/model_control.py")
        and "form.resetFields()" in admin,
        "api_key_never_returned": "credential:" not in api and "secret_ref:" not in api,
        "multiple_provider_instances_supported": table_names.count("model_provider_versions") == 1
        and "provider_id" in read("domain/model_control.py"),
        "multiple_models_per_provider_supported": "provider_id"
        in read("infrastructure/persistence/model_control.py")
        and table_names.count("model_deployments") == 1,
        "vendor_preset_not_legal_logic": all(
            "vendor_preset" not in read(p)
            for p in ("domain/decision_engine.py", "domain/formal_result_engine.py")
        ),
        "user_model_selection_is_allowlisted": "selected_model_ids" in invocation
        and "MODEL_SELECTION_NOT_ALLOWED" in router,
        "user_selection_does_not_bypass_policy": "prepare_selected_models" in invocation
        and "ModelUsagePolicyService" in read("application/llm_gateway_services.py"),
        "model_selection_is_snapshot_pinned": '"LLM_SELECTION"' in pins
        and '"LLM_MODEL"' in read("infrastructure/llm_gateway_configuration.py"),
        "historical_model_pin_is_immutable": valid
        and source is not None
        and 'config._saved(request, "LLM_INVOCATION_POLICY")' in frozen,
        "multi_model_result_is_derived": "DERIVED_CANDIDATE" in domain,
        "multi_model_vote_not_legal_authority": "majority" not in invocation and candidate_only,
        "llm_cannot_own_classification": candidate_only,
        "llm_cannot_own_applicability": candidate_only,
        "llm_cannot_own_crossborder": candidate_only,
        "llm_cannot_own_obligation": candidate_only,
        "llm_cannot_own_risk": candidate_only,
        "llm_cannot_own_final_path": candidate_only,
        "stage2_not_started": "STAGE2" in policy and "generate_document(" not in llm_source,
        "document_candidates_have_genuine_trace": "source_trace" in extract
        and "save_business_fact(" not in extract,
        "encrypted_secret_infrastructure_only": "Fernet" in secret and "os.O_NOFOLLOW" in secret,
    }
    return dict(
        pass_=all(checks.values()),
        passed=sum(checks.values()),
        total=len(checks),
        checks=checks,
        ownership_paths=len(paths),
    )


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["pass_"])
