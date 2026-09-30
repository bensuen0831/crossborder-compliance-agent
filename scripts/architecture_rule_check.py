from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "crossborder_compliance"


def files_under(path: Path, pattern: str = "*.py") -> list[Path]:
    return list(path.rglob(pattern)) if path.exists() else []


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def occurrences(pattern: str, paths: list[Path]) -> list[str]:
    out: list[str] = []
    rx = re.compile(pattern, re.I | re.M)
    for path in paths:
        if rx.search(read_text(path)):
            out.append(str(path.relative_to(ROOT)))
    return out


def class_block(text: str, class_name: str) -> str:
    match = re.search(rf"class\s+{re.escape(class_name)}\b[\s\S]*?(?=\nclass\s+|\Z)", text)
    return match.group(0) if match else ""


pyfiles = files_under(SRC)
domain = files_under(SRC / "domain")
application = files_under(SRC / "application")
migration_files = files_under(ROOT / "alembic" / "versions")
interfaces = files_under(SRC / "interfaces")
state_file = SRC / "workflows" / "state.py"
contracts = SRC / "domain" / "contracts.py"
adapter = SRC / "workflows" / "langgraph_adapter.py"
models = SRC / "infrastructure" / "persistence" / "models.py"
repositories = SRC / "infrastructure" / "persistence" / "postgres_repositories.py"
metadata_models = SRC / "infrastructure" / "persistence" / "metadata_models.py"
metadata_repositories = SRC / "infrastructure" / "persistence" / "metadata_repositories.py"
registry_file = SRC / "infrastructure" / "registry.py"
metadata_domain = SRC / "domain" / "metadata.py"
smoke_resume_file = ROOT / "smoke" / "smoke_resume.py"
checks: list[dict[str, object]] = []


def add(name: str, ok: bool, evidence: object) -> None:
    checks.append({"check": name, "pass": bool(ok), "evidence": evidence})


domain_lg = occurrences(r"\b(import|from)\s+langgraph\b", domain)
add("domain_has_no_langgraph_import", not domain_lg, domain_lg or "clean")

domain_sa = occurrences(r"\b(import|from)\s+sqlalchemy\b", domain)
add("domain_has_no_sqlalchemy_import", not domain_sa, domain_sa or "clean")

application_sa = occurrences(r"\b(import|from)\s+sqlalchemy\b", application)
add("application_has_no_sqlalchemy_import", not application_sa, application_sa or "clean")

langgraph_refs = occurrences(r"\b(import|from)\s+langgraph\b", pyfiles)
add(
    "langgraph_runtime_isolated_to_adapter",
    all(path.endswith("workflows/langgraph_adapter.py") for path in langgraph_refs),
    langgraph_refs or ["clean"],
)

bad_eval = occurrences(r"\b(eval|exec)\s*\(", pyfiles)
add("no_eval_exec", not bad_eval, bad_eval or "clean")

human_review_refs = occurrences(r"HumanReviewNode", pyfiles)
add("human_review_node_not_agent", not human_review_refs, human_review_refs or "clean")

model_text = read_text(models)
add(
    "classification_results_is_only_formal_classification_source",
    "classification_results" in model_text and "data_classifications" not in model_text,
    "classification_results present; data_classifications absent",
)

add(
    "workflow_stage_view_not_persisted",
    "WorkflowStageView" not in model_text and "workflow_stage_views" not in model_text,
    "no WorkflowStageView persistence model/table",
)

add(
    "regulatory_structure_node_is_canonical_persistence",
    "class RegulatoryStructureNodeEntity" in model_text
    and '__tablename__ = "regulatory_structure_nodes"' in model_text,
    "RegulatoryStructureNodeEntity present",
)

contract_text = read_text(contracts)
add(
    "stage1_explicit_cross_border_results",
    bool(re.search(r"class\s+Stage1ComplianceResultDTO[\s\S]*?cross_border_results\s*:", contract_text)),
    "Stage1ComplianceResultDTO.cross_border_results",
)
add(
    "legal_basis_rulehit_many_to_many_contract",
    bool(re.search(r"class\s+LegalBasisItemDTO[\s\S]*?rule_hit_ids\s*:\s*list\[UUID\]", contract_text)),
    "LegalBasisItemDTO.rule_hit_ids[]",
)
add(
    "legal_basis_rulehit_many_to_many_persistence",
    "class LegalBasisRuleHitLinkEntity" in model_text
    and '__tablename__ = "legal_basis_rule_hit_links"' in model_text,
    "association table legal_basis_rule_hit_links",
)

migration_text = "\n".join(read_text(path) for path in migration_files)
forbidden_cp_ddl = bool(
    re.search(
        r"(create_table\s*\(\s*[\"']checkpoint|CREATE\s+TABLE\s+checkpoint|DROP\s+TABLE\s+checkpoint|ALTER\s+TABLE\s+checkpoint)",
        migration_text,
        re.I,
    )
)
add(
    "domain_migration_does_not_own_checkpointer_schema",
    not forbidden_cp_ddl,
    "no checkpoint internal DDL in Domain Alembic",
)

add(
    "api_workflow_idempotency_separated",
    "execution_idempotency_records" in model_text and "api_idempotency_records" in model_text,
    "separate tables present",
)

state_text = read_text(state_file)
forbidden_state = [
    "db_session", "repository", "client", "secret", "api_key", "provider",
    "document_bytes", "knowledge_chunks",
]
add(
    "workflow_state_has_no_runtime_services_or_secrets",
    all(token not in state_text for token in forbidden_state),
    {"forbidden": forbidden_state},
)

adapter_text = read_text(adapter)
add(
    "durable_postgres_checkpointer_setup_present",
    "PostgresSaver" in adapter_text
    and bool(re.search(r"\b(checkpointer|cp)\.setup\(\)", adapter_text)),
    "PostgresSaver + official setup() path",
)
add(
    "thread_id_backend_bound_to_workflow_run_id",
    bool(re.search(r'[\"\']thread_id[\"\']\s*:\s*str\(workflow_run_id\)', adapter_text))
    and bool(re.search(r"thread_id\s*=\s*str\(workflow_run_id\)", adapter_text)),
    "workflow_run_id used as LangGraph thread_id",
)

conversation_block = class_block(model_text, "ConversationThreadEntity")
add(
    "conversation_thread_not_langgraph_thread_id",
    bool(conversation_block)
    and re.search(r"^\\s*thread_id\\s*:", conversation_block, re.M) is None,
    "ConversationThreadEntity has no standalone LangGraph thread_id field",
)

add(
    "interrupt_pre_side_effect_event_idempotent",
    'event_key="node_b:review-required"' in adapter_text and "ensure_review_task" in adapter_text,
    "deterministic event + idempotent review key",
)

interface_raw_refs = occurrences(r"\b(import|from)\s+langgraph\b|checkpoint_(writes|blobs)", interfaces)
add(
    "raw_langgraph_event_not_external_contract",
    not interface_raw_refs and "return iter(())" in adapter_text,
    interface_raw_refs or "canonical event boundary present",
)

orm_route_refs = occurrences(
    r"from\s+crossborder_compliance\.infrastructure\.persistence\.models\s+import|Mapped\[|DeclarativeBase",
    interfaces,
)
add(
    "api_routes_do_not_return_or_import_orm_models",
    not orm_route_refs,
    orm_route_refs or "API layer uses Pydantic/Application DTOs only",
)

repo_text = read_text(repositories)
repo_classes = re.findall(r"class\s+(Postgres\w+Repository)\(([^)]*)\)", repo_text)
unscoped_repos = [name for name, bases in repo_classes if "_TenantScopedRepository" not in bases]
add(
    "domain_repositories_are_automatically_tenant_scoped",
    bool(repo_classes) and not unscoped_repos
    and "RepositoryContext" in repo_text
    and "model.tenant_id == self.tenant_id" in repo_text,
    unscoped_repos or [name for name, _ in repo_classes],
)

add(
    "no_second_classification_repository",
    repo_text.count("class PostgresClassificationRepository") == 1
    and "DataClassificationRepository" not in repo_text,
    "one ClassificationRepository adapter; no parallel DataClassificationRepository",
)

named_rule_refs = occurrences(
    r"\b(SCCRequirementSkill|DPIARequirementSkill|TIARequirementSkill)\b", pyfiles
)
add(
    "no_country_product_regulation_fixed_business_logic",
    not named_rule_refs,
    named_rule_refs or "no fixed country/product/regulatory-document business skills",
)


# Phase 1C executable guards
frontend_files = files_under(ROOT / "frontend") + files_under(ROOT / "web")
frontend_business_enum_refs = occurrences(
    r"\b(country|jurisdiction|scenario|product|data_type|data_flow_type)\b\s*=\s*\[(?:.|\n)*?\]",
    frontend_files,
)
add(
    "frontend_has_no_business_metadata_enum",
    not frontend_business_enum_refs,
    frontend_business_enum_refs or "no hard-coded frontend business option lists",
)

agent_skill_files = files_under(SRC / "agents") + files_under(SRC / "skills") + files_under(SRC / "workflows")
model_binding_refs = occurrences(
    r"(https?://[^\s\"']+|base_url\s*=|model_name\s*=|model\s*=\s*[\"'][A-Za-z0-9_.:/-]+[\"'])",
    agent_skill_files,
)
add(
    "agent_skill_has_no_model_name_or_base_url",
    not model_binding_refs,
    model_binding_refs or "no provider/model/base-url binding in agent/skill/workflow code",
)

prompt_embedding_refs = occurrences(
    r"(SYSTEM_PROMPT|business_prompt|compliance_prompt)\s*=\s*[\"']",
    files_under(SRC / "agents") + files_under(SRC / "skills"),
)
add(
    "prompt_business_content_not_embedded_in_agent",
    not prompt_embedding_refs,
    prompt_embedding_refs or "no embedded business prompt in agent/skill code",
)

registry_file = SRC / "infrastructure" / "registry.py"
registry_text = read_text(registry_file) if registry_file.exists() else ""
add(
    "registry_not_source_of_truth",
    "source_of_truth" in registry_text
    and '"source_of_truth": False' in registry_text
    and "DB/versioned config remains source of truth" in registry_text,
    "ProjectionRegistry explicitly identifies itself as non-authoritative projection",
)

metadata_repo_file = SRC / "infrastructure" / "persistence" / "metadata_repositories.py"
metadata_repo_text = read_text(metadata_repo_file) if metadata_repo_file.exists() else ""
add(
    "admin_draft_not_runtime_visible",
    "lifecycle_status == GovernanceStatus.ACTIVE.value" in metadata_repo_text
    and "load_active" in metadata_repo_text,
    "runtime loaders filter ACTIVE lifecycle versions only",
)

metadata_models_file = SRC / "infrastructure" / "persistence" / "metadata_models.py"
metadata_models_text = read_text(metadata_models_file) if metadata_models_file.exists() else ""
secret_forbidden = bool(re.search(r"\b(api_key|access_token|client_secret|password|credential_value)\b", metadata_models_text, re.I))
add(
    "model_secret_not_persisted_in_metadata",
    "secret_ref" in metadata_models_text and not secret_forbidden,
    "model metadata stores secret_ref only; no credential-value columns",
)

add(
    "snapshot_not_dynamic_registry_lookup_on_resume",
    "infrastructure.registry" not in adapter_text
    and "AnalysisSnapshotRegistryPinEntity" in metadata_models_text
    and "analysis snapshot pin is immutable" in metadata_repo_text,
    "resume adapter does not consult registry; snapshot pins are immutable",
)

add(
    "registry_publish_uses_transactional_outbox",
    "RegistrySyncEventEntity" in metadata_repo_text
    and "session.add(" in metadata_repo_text
    and "target_status == GovernanceStatus.ACTIVE.value" in metadata_repo_text,
    "publish and RegistrySyncEvent are written inside the same DB transaction",
)

country_branch_refs = occurrences(
    r"\bif\s+.*\b(country|jurisdiction_code)\b.*(?:==|in)\s*[\"'\[{]",
    [registry_file] if registry_file.exists() else [],
)
add(
    "no_country_specific_registry_branch",
    not country_branch_refs,
    country_branch_refs or "registry resolution is metadata/binding driven",
)


# Phase 1D executable guards
document_domain_file = SRC / "domain" / "document_intelligence.py"
document_ports_file = SRC / "application" / "document_ports.py"
document_services_file = SRC / "application" / "document_services.py"
document_parser_file = SRC / "infrastructure" / "document_parsers.py"
document_repo_file = SRC / "infrastructure" / "persistence" / "document_repositories.py"
document_models_file = SRC / "infrastructure" / "persistence" / "document_models.py"
document_domain_text = read_text(document_domain_file) if document_domain_file.exists() else ""
document_ports_text = read_text(document_ports_file) if document_ports_file.exists() else ""
document_services_text = read_text(document_services_file) if document_services_file.exists() else ""
document_parser_text = read_text(document_parser_file) if document_parser_file.exists() else ""
document_repo_text = read_text(document_repo_file) if document_repo_file.exists() else ""
document_models_text = read_text(document_models_file) if document_models_file.exists() else ""

add(
    "graph_state_has_no_document_binary",
    all(token not in state_text for token in ["document_bytes", "raw_binary", "file_bytes", "document_content"]),
    "LangGraph state contains references only; no document binary fields",
)

add(
    "canonical_document_not_llm_narrative",
    "class CanonicalStructureNode" in document_domain_text
    and "original_text" in document_domain_text
    and "normalized_text" in document_domain_text
    and "llm" not in document_parser_text.lower(),
    "canonical parser output is structured and parser-driven, not LLM narrative",
)

vision_block = class_block(document_domain_text, "CandidateDiagramResult")
add(
    "candidate_vision_has_no_legal_result",
    bool(vision_block)
    and not re.search(r"(legal|classification|compliance_path|risk_score)", vision_block, re.I),
    "CandidateDiagramResult contains candidate nodes/edges only",
)

source_trace_contract_ok = all(
    name in document_domain_text and "source_trace_refs" in class_block(document_domain_text, name)
    for name in ["BusinessFactCandidate", "CandidateDataItem", "CandidateDataFlowNode", "CandidateDataFlowEdge"]
)
add(
    "extracted_result_has_source_trace",
    source_trace_contract_ok and "requires SourceTraceRef" in document_repo_text,
    "candidate facts/items/flows carry SourceTraceRef and persistence rejects empty provenance",
)

add(
    "spreadsheet_preserves_row_column_provenance",
    "class XLSXParserAdapter" in document_parser_text
    and '"row_index"' in document_parser_text
    and '"column_index"' in document_parser_text
    and '"header"' in document_parser_text
    and '"merged_range"' in document_parser_text
    and '"formula"' in document_parser_text,
    "XLSX adapter preserves row/column/header/formula/merged-cell metadata",
)

add(
    "formal_counts_not_llm",
    "aggregate_project_summary" in document_repo_text
    and "func.count" in document_repo_text
    and not re.search(r"(llm|model).*count", document_repo_text, re.I),
    "DocumentAnalysisSummary is programmatically aggregated from persistence",
)

add(
    "parse_run_is_versioned",
    "class DocumentParseRunEntity" in model_text
    and "class DocumentParseRunDetailEntity" in document_models_text
    and "parse_run_version" in document_models_text
    and "uq_document_parse_run_detail_version" in document_models_text,
    "Phase 1B parse-run identity + Phase 1D one-to-one detail extension has explicit version and unique tenant/document/version constraint",
)

add(
    "snapshot_can_pin_parse_run",
    "class AnalysisSnapshotParseRunPinEntity" in document_models_text
    and "analysis_snapshot_parse_run_pins" in document_models_text
    and "pin_parse_run" in document_repo_text,
    "AnalysisSnapshot has immutable parse-run pin persistence",
)

provider_sdk_refs = occurrences(
    r"\b(import|from)\s+(pypdf|docx|openpyxl|pptx|PIL)\b",
    domain + application + files_under(SRC / "workflows"),
)
add(
    "parser_provider_is_adapter_only",
    not provider_sdk_refs
    and all(token in document_parser_text for token in ["PDFParserAdapter", "DOCXParserAdapter", "XLSXParserAdapter", "PPTXParserAdapter"]),
    provider_sdk_refs or "provider SDKs isolated to infrastructure/document_parsers.py",
)

phase1d_fixed_logic = occurrences(
    r"\bif\s+.*\b(country|product|regulation)\b.*(?:==|in)\s*[\"'\[{]",
    [document_services_file, document_parser_file, document_repo_file],
)
add(
    "phase1d_has_no_country_product_regulation_logic",
    not phase1d_fixed_logic,
    phase1d_fixed_logic or "Document Intelligence foundation contains no fixed country/product/regulation decisions",
)

failed = [check for check in checks if not check["pass"]]
result = {
    "pass": not failed,
    "passed": len(checks) - len(failed),
    "total": len(checks),
    "checks": checks,
}
print(json.dumps(result, indent=2, ensure_ascii=False))

evidence_dir = os.getenv("EVIDENCE_DIR")
if evidence_dir:
    out = Path(evidence_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = ["| # | Architecture rule check | Result | Evidence |", "|---:|---|---|---|"]
    for i, check in enumerate(checks, start=1):
        evidence = json.dumps(check["evidence"], ensure_ascii=False, sort_keys=True).replace("|", "\\|")
        rows.append(
            f"| {i} | `{check['check']}` | **{'PASS' if check['pass'] else 'FAIL'}** | `{evidence}` |"
        )
    (out / "architecture_rule_check.md").write_text(
        "# Phase 1B Architecture Rule Check\n\n"
        f"**Decision: {'PASS' if not failed else 'FAIL'} — {result['passed']}/{result['total']} checks passed.**\n\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    (out / "architecture_rule_check.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

raise SystemExit(1 if failed else 0)
