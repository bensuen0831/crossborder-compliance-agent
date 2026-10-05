from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
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


# Phase 1E executable guards
context_domain_file = SRC / "domain" / "context_resolution.py"
context_ports_file = SRC / "application" / "context_ports.py"
context_services_file = SRC / "application" / "context_services.py"
context_models_file = SRC / "infrastructure" / "persistence" / "context_models.py"
context_repo_file = SRC / "infrastructure" / "persistence" / "context_repositories.py"
context_domain_text = read_text(context_domain_file) if context_domain_file.exists() else ""
context_ports_text = read_text(context_ports_file) if context_ports_file.exists() else ""
context_services_text = read_text(context_services_file) if context_services_file.exists() else ""
context_models_text = read_text(context_models_file) if context_models_file.exists() else ""
context_repo_text = read_text(context_repo_file) if context_repo_file.exists() else ""

add(
    "candidate_not_formal_compliance_input",
    "class CandidateResolution" in context_domain_text
    and "save_candidate_resolution" in context_services_text
    and "CandidateResolutionEntity" in context_repo_text,
    "Candidate → Resolution → Formal object boundary is persisted; candidates are retained",
)

add(
    "product_context_is_registry_driven",
    "metadata_definition(" in context_services_text
    and "PRODUCT_DOMAIN" in context_services_text
    and "ProductContextDefinitionLinkEntity" in context_models_text,
    "Product Context resolves ACTIVE metadata definitions and persists registry bindings",
)

add(
    "no_product_search_all_scope",
    "effective = selected_flat or detected_flat" in context_services_text
    and "GENERIC_UNRESOLVED" in context_services_text
    and "search_all" not in context_services_text.lower(),
    "No selection uses document-detected scope or unresolved generic scope; never all products",
)

add(
    "product_conflict_is_explicit",
    "PRODUCT_CONTEXT_CONFLICT" in context_services_text
    and "selected_product_scope" in context_services_text
    and "detected_product_context" in context_services_text,
    "Explicit selection vs detected scope conflict is persisted as PRODUCT_CONTEXT_CONFLICT",
)

add(
    "business_fact_conflict_is_explicit",
    "BusinessFactConflict" in context_services_text
    and "BUSINESS_FACT_CONFLICT" in context_services_text
    and "MULTIPLE_NORMALIZED_VALUES_FOR_FACT_TYPE" in context_services_text,
    "Conflicting normalized values for one registry fact type create explicit reviewable conflict",
)

add(
    "possible_duplicate_requires_review_conflict",
    "DATA_ITEM_POSSIBLE_DUPLICATE" in context_services_text
    and "SEMANTIC_CANDIDATE_ONLY" in context_services_text
    and "reviewer_required" in context_services_text,
    "Semantic POSSIBLE_SAME remains candidate-only and enters ContextConflict/review",
)

add(
    "unresolved_party_requires_review_conflict",
    "PARTY_CONTEXT_CONFLICT" in context_services_text
    and "UNRESOLVED_PARTY" in context_services_text
    and "save_party_resolution" in context_services_text,
    "Unresolved PartyCandidate persists PartyResolution plus explicit reviewable conflict",
)

add(
    "data_item_source_trace_required",
    "formal DataItem requires SourceTrace" in context_services_text
    and "class DataItemSourceTraceLinkEntity" in context_models_text
    and "class DataItemCandidateLinkEntity" in context_models_text,
    "Formal data_items retain all candidate and SourceTrace links",
)

add(
    "formal_counts_are_separate",
    all(name in context_repo_text for name in [
        '"raw_field_count"', '"normalized_data_item_count"', '"data_group_count"'
    ])
    and "func.count" in context_repo_text,
    "Raw occurrence, normalized DataItem and DataGroup counts are separate programmatic aggregates",
)

parallel_item_names = ["formal_data_items", "resolved_data_items", "final_data_items"]
add(
    "no_parallel_data_item_source_of_truth",
    "DataItemEntity" in context_repo_text
    and not any(name in context_models_text for name in parallel_item_names),
    "Phase 1B data_items remains authoritative; Phase 1E adds detail/link tables only",
)

parallel_flow_names = ["formal_data_flow_nodes", "formal_data_flow_edges", "resolved_data_flows"]
add(
    "no_parallel_data_flow_source_of_truth",
    all(name in context_repo_text for name in ["DataFlowNodeEntity", "DataFlowEdgeEntity", "DataItemFlowLinkEntity"])
    and not any(name in context_models_text for name in parallel_flow_names),
    "Phase 1B data_flow_nodes/data_flow_edges/data_item_flow_links remain authoritative",
)

add(
    "data_flow_is_structured",
    "class DataFlowNodeDetailEntity" in context_models_text
    and "class DataFlowEdgeDetailEntity" in context_models_text
    and "class DataItemFlowLinkDetailEntity" in context_models_text
    and "create_formal_flow_edge" in context_repo_text,
    "Formal flow uses structured Node/Edge/DataItemFlowLink plus versioned detail",
)

add(
    "jurisdiction_not_regulation_decision",
    "class JurisdictionContext" in context_domain_text
    and "ApplicableRegulation" not in context_domain_text
    and "regulation_applicability" not in context_services_text.lower()
    and "cross_border_legal" not in context_services_text.lower(),
    "Jurisdiction Context carries location context only; no regulation/cross-border legal decision",
)

add(
    "semantic_resolution_candidate_only",
    "class CandidateSimilarityPort" in context_ports_text
    and "POSSIBLE_SAME" in context_services_text
    and "Semantic evidence is suggestion-only" in context_services_text,
    "Semantic similarity can create candidate/review evidence but does not directly merge formal DataItems",
)

add(
    "context_snapshot_versioned",
    "class AnalysisSnapshotContextPinEntity" in context_models_text
    and all(name in context_models_text for name in [
        "context_resolution_version", "product_context_version",
        "data_inventory_version", "data_flow_version"
    ])
    and "analysis snapshot context pin is immutable" in context_repo_text,
    "AnalysisSnapshot pins immutable versioned Context/DataInventory/DataFlow versions",
)

phase1e_fixed_rule_logic = occurrences(
    r"\bif\s+.*\b(country|country_code|product_code|regulation_code)\b.*(?:==|in)\s*[\"'\[{]",
    [context_services_file],
)
add(
    "no_country_product_rule_logic",
    not phase1e_fixed_rule_logic
    and "risk_score" not in context_services_text
    and "compliance_path" not in context_services_text.lower(),
    phase1e_fixed_rule_logic or "No country/product-code/regulation decision routing, risk, or compliance-path logic",
)


# Phase 1F: static executable boundaries, complemented by mandatory PostgreSQL cases.
ks=read_text(SRC/'application/knowledge_services.py')
kp=read_text(SRC/'application/knowledge_ports.py')
kd=read_text(SRC/'domain/knowledge.py')
kr=read_text(SRC/'infrastructure/persistence/knowledge_repositories.py')
km=read_text(SRC/'infrastructure/persistence/knowledge_models.py')
kw=read_text(SRC/'infrastructure/knowledge_worker.py')
kdl=read_text(SRC/'infrastructure/knowledge_download.py')
migration=read_text(ROOT/'alembic/versions/0006_phase1f_knowledge_scope.py')
scope_ast=next(n for n in ast.parse(ks).body if isinstance(n,ast.ClassDef) and n.name=='KnowledgeScopeResolver')
calls={ast.unparse(n.func) for n in ast.walk(scope_ast) if isinstance(n,ast.Call)}
new_checks={
 'knowledge_platform_not_vector_db':all(x in km for x in ('knowledge_documents','knowledge_document_versions','knowledge_structure_nodes')),
 'scope_resolver_has_no_retrieval':not any(re.search(r'top_k|similarity_search|rerank|embed|llm|vector_search',call,re.I) for call in calls),
 'hard_filter_precedes_similarity':all(x in kd for x in ('tenant_filter','permission_filter','lifecycle_filter','version_filter','product_filter','jurisdiction_filter')) and 'filter_order' in kd,
 'unrelated_product_knowledge_excluded':'class ProductScopeResolver' in ks and 'PRODUCT_DIMENSIONS' in ks and 'all(' in class_block(ks,'DimensionScopeResolver'),
 'unresolved_product_scope_fail_safe':'formal.product_unresolved' in ks and 'UNRESOLVED_PRODUCT_SCOPE' in ks and 'ALL_PRODUCTS' not in ks,
 'knowledge_chunk_has_provenance':all(x in kr for x in ('KnowledgeChunkNodeEntity','CitationEntity','EvidenceReferenceEntity','RegulatoryStructureNodeEntity')),
 'vector_index_is_derived':'embedding_vector' in migration and 'derived=True' in kr,
 'fts_index_is_derived':'GENERATED ALWAYS' in migration and 'USING gin' in migration,
 'registry_not_knowledge_source':'KnowledgeSourceDefinitionEntity' in kr and 'KnowledgeCollectionEntity' in kr,
 'translation_review_boundary':'independent translation reviewer required' in kr and 'official_evidence=False' in kr,
 'knowledge_quality_before_active':'quality gate failed' in kr and 'review required before ACTIVE' in kr,
 'snapshot_pins_knowledge_version':all(x in kr for x in ('KNOWLEDGE_VERSION','KNOWLEDGE_BINDING','KNOWLEDGE_INDEX_VERSION','EMBEDDING_CONFIG_VERSION')) and 'saved_scope' in ks,
 'phase1f_uses_phase1e_context':all(x in kr for x in ('ContextResolutionRunEntity','ProductScopeResolutionEntity','ScenarioContextEntity','JurisdictionContextEntity','DataItemResolutionDetailEntity')) and 'PHASE1E_FORMAL_CONTEXT_REQUIRED' in kr,
 'no_country_specific_knowledge_branch':not occurrences(r"\bif\s+.*\b(country|country_code|product_code|regulation_code)\b.*(?:==|in)\s*[\"'\[{]",[SRC/'application/knowledge_services.py',SRC/'infrastructure/persistence/knowledge_repositories.py']),
 'no_regulation_business_decision':not any(x in ks.lower() for x in ('risk_score','regulation_applicability','legal_conclusion','compliance_path')),
 'controlled_downloader_boundary':'class ControlledDownloaderPort' in kp and all(x in kdl for x in ('PRIVATE_IP_BLOCKED','MIME_POLICY','REDIRECT_LIMIT','source_hash','content_hash','request_audit')),
 'knowledge_ingestion_no_graph_checkpoints':'class KnowledgeIngestionWorker' in kw and not re.search(r'from .*langgraph|import langgraph|checkpoint',kw.split('"""')[-1]),
 'no_parallel_knowledge_source':not any(x in km for x in ('knowledge_sources"','knowledge_collections_v2','formal_knowledge_document','final_knowledge_store')),
}
for name,passed in new_checks.items(): add(name,passed,'Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage')

# Phase 1G executable boundaries; mandatory PostgreSQL tests prove the behavioral cases.
gd=read_text(SRC/'domain/retrieval.py')
gs=read_text(SRC/'application/retrieval_services.py')
ga=read_text(SRC/'application/retrieval_algorithms.py')
ge=read_text(SRC/'application/external_evidence_services.py')
gr=read_text(SRC/'infrastructure/persistence/retrieval_repositories.py')
gn=read_text(SRC/'infrastructure/persistence/retrieval_navigation.py')
gm=read_text(SRC/'infrastructure/persistence/retrieval_models.py')
gsearch=read_text(SRC/'infrastructure/retrieval_search.py')
gfiles=[SRC/'application/retrieval_services.py',SRC/'application/retrieval_algorithms.py',
        SRC/'application/external_evidence_services.py',SRC/'domain/retrieval.py']
gimports=[n.module or '' for p in gfiles for n in ast.walk(ast.parse(read_text(p)))
          if isinstance(n,ast.ImportFrom)]
pipeline=next(n for n in ast.walk(ast.parse(gs)) if isinstance(n,ast.FunctionDef) and n.name=='retrieve')
call_lines={ast.unparse(n.func):n.lineno for n in ast.walk(pipeline) if isinstance(n,ast.Call)}
hard_cte=gsearch.split('class ScopedPostgresSearch')[0]
checks1g={
 'retrieval_consumes_phase1f_scope':all(x in gs for x in ('KnowledgeScopeResolver','filter_spec')) and
     'KnowledgeScope' in gd and not any('document_parsers' in x for x in gimports),
 'retrieval_hard_filters_before_similarity':'filtered AS MATERIALIZED' in hard_cte and
     all(x in hard_cte for x in ('tenant_id=:tenant','v.lifecycle IN','b.permission_scopes_json',
         'b.knowledge_binding_id IN','c.knowledge_version_id IN','effective_from')) and
     'FROM filtered WHERE search_vector' in gsearch and 'FROM filtered f' in gsearch,
 'retrieval_indexes_are_derived':'i.derived=true' in hard_cte and 'legal_source_of_truth' in gm and
     'knowledge_document_versions' in hard_cte,
 'hybrid_merge_deterministic_score_provenance':'RECIPROCAL_RANK_FUSION' in gd and all(x in ga for x in ('WEIGHTED_SCORE','lexical_score',
     'vector_score','hybrid_score','chunk_id')) and 'sorted(' in ga,
 'reranker_allowed_candidates_only':'RERANK_OUTSIDE_ALLOWED_SET' in ga and 'candidate_hash' in ga,
 'rerank_scope_revalidation':call_lines.get('RetrievalScopeValidator(repo).validate',0)>
     call_lines.get('RerankService(self.reranker).rerank',0)>0,
 'evidence_pack_complete_provenance':all(x in gd for x in ('knowledge_document_id','knowledge_version_id',
     'structure_node_id','chunk_id','citation_id','source_url','content_hash','knowledge_index_version',
     'retrieval_policy_version','analysis_snapshot_id')),
 'rag_context_not_legal_source':'legal_source_of_truth: Literal[False]' in gd and
     'legal_decision: Literal[False]' in gd,
 'sufficiency_is_policy_driven':all(x in ga for x in ('policy.required_topic_refs',
     'policy.required_regulation_refs','policy.minimum_evidence_quality','policy.authoritative_tiers')) and
     not any(re.search(r'openai|ollama|langgraph|vector',x,re.I) for x in gimports),
 'generic_knowledge_not_jurisdiction_sufficient':'and e.jurisdiction_specific' in ga and
     'JURISDICTION_SPECIFIC_EVIDENCE_MISSING' in ga,
 'external_preserves_formal_scope':all(x in ge for x in ('rule_permits','ProductScopeResolver',
     'JurisdictionScopeResolver','PermissionScopeResolver','repo.retrieval_context')),
 'unverified_discovery_not_evidence':'DISCOVERY_CANNOT_BECOME_EVIDENCE' in ge and
     'discovery-only source cannot enter evidence' in gd,
 'official_external_validation':all(x in ge for x in ('ATTRIBUTION_MISMATCH','EXTERNAL_EVIDENCE_NOT_EFFECTIVE',
     'EXTERNAL_HASH_OR_SIZE_FAILED','EXTERNAL_CITATION_INVALID','OFFICIAL_SOURCE_TYPE_MISMATCH')),
 'runtime_external_not_active':'ck_runtime_external_not_active' in gm and
     "status='VERIFIED' AND NOT active_knowledge" in gm and 'active_knowledge: Literal[False]' in gd,
 'external_snapshot_reproducible':'repo.saved_external' in ge and 'RUNTIME_EXTERNAL_EVIDENCE' in gr and
     'parsed_artifact_version' in gd and 'original_content' in gm,
 'fallback_guidance_nonempty':all(x in ga for x in ('conservative_controls=action(',
     'evidence_acquisition_steps=action(','operational_next_steps=action(')),
 'fallback_not_compliance_path':'compliance_path: Literal[False]' in gd and
     'finalization_requires_verification: Literal[True]' in gd,
 'retrieval_policy_snapshot_pinned':'snapshot policy family immutable' in gr and
     'PHASE1G_' in gr and 'AnalysisSnapshotRegistryPinEntity' in gr,
 'no_country_product_regulation_retrieval_branch':not occurrences(
     r"\bif\s+.*\b(country_code|product_code|regulation_code)\b.*(?:==|in)\s*[\"'\[{]",gfiles),
 'retrieval_services_no_provider_sql_graph_sdk':not any(re.search(
     r'sqlalchemy|pgvector|openai|qwen|deepseek|ollama|vllm|neo4j|langgraph',x,re.I) for x in gimports),
 'wiki_reuses_durable_review':'AdminReviewTaskEntity' in gn and 'wiki_reviews' in gm and
     'ck_wiki_review_boundary' in gm and 'independent pending human review required' in gn,
 'wiki_not_official_legal_evidence':'ck_wiki_derived' in gm and 'NOT official_evidence AND NOT legal_basis' in gm,
 'graph_reviewed_derived_provenance':'source_evidence_id' in gm and 'review_task_id' in gm and
     'legal_applicability' in gm and 'graph_provenance' in gn,
 'runtime_client_cannot_supply_scope':'KnowledgeScope' not in read_text(SRC/'interfaces/api/retrieval_schemas.py') and
     "extra='forbid'" in read_text(SRC/'interfaces/api/retrieval_schemas.py').replace('"',"'"),
}
for name,passed in checks1g.items():
    add(name,passed,'Rules 115–132, AST/order/SQL/model constraints; tests/test_phase1g_* empirical cases')


# Final Addendum: publish-driven runtime synchronization.
grt=read_text(SRC/'application/knowledge_runtime_services.py')
grw=read_text(SRC/'infrastructure/knowledge_publication_worker.py')
grr=read_text(SRC/'infrastructure/persistence/knowledge_runtime_repository.py')
gmain=read_text(SRC/'interfaces/api/main.py')
pub_checks={
 'normal_publish_automatic_runtime_sync':'KNOWLEDGE_VERSION_PUBLISHED' in kr and 'worker.start()' in gmain and 'self.consumer(t).run_once()' in grw,
 'publication_reuses_registry_outbox_service':any(isinstance(n,ast.Call) and ast.unparse(n.func)=='RegistrySyncService' for n in ast.walk(ast.parse(grt))) and 'PostgresRegistrySyncEventRepository' in grw and 'registry_sync_events' in gm,
 'runtime_ready_before_new_retrieval':"r.status='READY'" in gsearch and 'KnowledgeRuntimePublicationEntity.status == "READY"' in gr and 'ck_runtime_ready_barrier' in gm,
 'publication_snapshot_stability':'publication_lease' in grr and 'index.index_version_id' in gr and 'snapshot' in gs and 'pinned_version_ids' in gr,
 'publication_duplicate_retry_safe':'pg_advisory_lock' in grr and 'stable_id' in grr and 'self.sync.run_once' in grt,
 'publication_failed_build_not_ready':'RUNTIME_ASSET_BUILD_FAILED' in grt and 'state.status != "READY"' in grr and 'state.status = "FAILED"' in grr,
 'runtime_materialization_no_agent_graph':not occurrences(r'from .*langgraph|from .*agents|import langgraph', [SRC/'application/knowledge_runtime_services.py',SRC/'infrastructure/knowledge_publication_worker.py']),
}
for name,passed in pub_checks.items():
    add(name,passed,'Final Addendum / Rule 133; tests/test_phase1g_publication_postgres.py')

# Phase 1H additions preserve all preceding checks and rule numbers 1-133.
ast_h = read_text(SRC / "domain" / "rule_ast.py")
rules_h = read_text(SRC / "domain" / "rules.py")
classification_h = read_text(SRC / "domain" / "classification.py")
service_h = read_text(SRC / "application" / "classification_services.py")
governance_h = read_text(SRC / "infrastructure" / "persistence" / "rule_governance.py")
api_h = read_text(SRC / "interfaces" / "api" / "routes" / "classification.py")
migration_h = read_text(ROOT / "alembic" / "versions" / "0008_phase1h_rule_classification.py")
evidence_h = read_text(SRC / "infrastructure" / "classification_evidence.py")
checks1h = {
    "rule_runtime_validated_typed_ast": "class ValidatedAST" in ast_h and "parse_ast(c.conditions, c.fields)" in rules_h,
    "rule_ast_no_unrestricted_calls": not occurrences(r"\b(eval|exec|compile|__import__|getattr|setattr|open)\s*\(", [SRC / "domain" / "rule_ast.py", SRC / "domain" / "rules.py"]),
    "rule_domain_no_external_dependencies": not occurrences(r"\b(import|from)\s+(sqlalchemy|psycopg|redis|httpx|requests|langgraph|boto3|subprocess|os|importlib)\b", [SRC / "domain" / "rule_ast.py", SRC / "domain" / "rules.py", SRC / "domain" / "classification.py"]),
    "formal_classification_versioned_provenance": all(field in classification_h for field in ("scheme_version_id", "jurisdiction_id", "rule_hit_ids", "evidence_ids", "source_fact_refs", "analysis_snapshot_id", "context_version")),
    "no_data_typed_outcome": "facts.data_item_id is None" in service_h and 'reason_codes=("NO_DATA_ITEM",)' in service_h,
    "rule_publish_gate_uses_existing_transaction": "transition_gate(session, row" in read_text(SRC / "infrastructure" / "persistence" / "config_admin_repositories.py") and all(value in governance_h for value in ("run_rule_tests", "validate_conflicts", "approved_by", "submitted_by")),
    "rule_and_scheme_content_immutable": "phase1h_immutable_rule" in migration_h and "phase1h_immutable_scheme" in migration_h,
    "api_references_only_no_narrative": all(value in class_block(api_h, "ClassificationRequest") for value in ("analysis_snapshot_id", "data_item_id", "scheme_version_id")) and not re.search(r"\b(values|facts|narrative|result|tenant_id)\s*:", class_block(api_h, "ClassificationRequest")),
    "classification_reuses_scope_checked_evidence": "scoped_saved_response" in evidence_h and "source.retrieve(" not in evidence_h,
    "classification_persisted_retry_unique": "uq_formal_classification_snapshot" in migration_h,
}
for name, passed in checks1h.items():
    add(name, passed, "Phase 1H Rules 134-139; tests/test_phase1h_* include actual PostgreSQL/API evidence")

# Phase1I append-only executable checks; preceding architecture checks remain intact.
profiles_i = read_text(SRC / "domain/compliance_profiles.py")
applicability_i = read_text(SRC / "domain/regulation_applicability.py")
service_i = read_text(SRC / "application/country_compliance_services.py")
repository_i = read_text(SRC / "infrastructure/persistence/country_compliance_repository.py")
governance_i = read_text(SRC / "infrastructure/persistence/compliance_profile_governance.py")
model_i = read_text(SRC / "infrastructure/persistence/applicability_models.py")
worker_i = read_text(SRC / "infrastructure/compliance_profile_worker.py")
api_i = read_text(SRC / "interfaces/api/routes/country_compliance.py")
migration_i = read_text(ROOT / "alembic/versions/0009_phase1i_applicability.py")
i_files = [SRC / "domain/compliance_profiles.py", SRC / "domain/regulation_applicability.py", SRC / "application/country_compliance_services.py"]
checks1i = {
    "applicability_canonical_identity": all(x in model_i for x in ("knowledge_document_versions.knowledge_version_id", "metadata_versions.version_id", "retrieval_runs.retrieval_run_id")) and all(x in repository_i for x in ("RegulatoryStructureNodeEntity", "LegalBasisItemEntity", "KnowledgeStructureNodeEntity")),
    "profile_reuses_metadata_governance": all(x in governance_i for x in ("MetadataDefinitionEntity", "MetadataVersionEntity", "independent Phase1I")) and "validate_payload(session, definition, payload)" in read_text(metadata_repositories),
    "profile_reuses_registry_outbox": "RegistrySyncService(" in worker_i and "PostgresRegistrySyncEventRepository" in worker_i and "profile_worker.start()" in gmain,
    "scenario_fixed_pipeline_deterministic": "STANDARD_COMPLIANCE_PIPELINE" in profiles_i and "def fixed_pipeline" in profiles_i and "ordered = sorted(profiles" in profiles_i,
    "scenario_conflicts_typed": all(x in profiles_i for x in ("REQUIRED_DISABLED_SKILL_CONFLICT", "EVIDENCE_PROFILE_CONFLICT", "risk_dimension_priorities", "scenario_specific_checks", 'field.upper() + "_CONFLICT"')),
    "generic_country_capabilities_only": all(x in profiles_i for x in ("CLASSIFICATION", "CROSS_BORDER", "LOCALIZATION", "FILING", "IMPACT_ASSESSMENT", "CONTRACT", "REGULATOR", "CAPABILITY_NOT_CONFIGURED")) and "legal_obligation: Literal[False]" in profiles_i,
    "generic_skills_pure": not occurrences(r"\b(import|from)\s+(sqlalchemy|psycopg|redis|httpx|requests|langgraph|boto3|openai|subprocess)\b", i_files),
    "applicability_scope_revalidation": all(x in repository_i for x in ("AnalysisSnapshotContextPinEntity", "scoped_saved_response", "RULE_V1", "scope.filter_spec.version_filter", "classification_result_ids")),
    "applicability_reference_only_api": not re.search(r"\b(tenant_id|facts|knowledge_scope|narrative|applicability_status)\s*:", class_block(api_i, "ApplicabilityExecutionRequest")),
    "profile_new_pin_ready_and_historical": all(x in repository_i for x in ('legal.lifecycle != "ACTIVE"', 'KnowledgeRuntimePublicationEntity.status == "READY"', '"SUPERSEDED", "EXPIRED", "ARCHIVED"', '"PHASE1I_CONFIGURATION"')),
    "applicability_conflicts_and_insufficiency": all(x in applicability_i for x in ("CONTRADICTORY_PHASE1H_RULEHITS", "EVIDENCE_NOT_SUFFICIENT", "fallback_guidance_context=inputs.fallback_guidance_context")),
    "scenario_no_fake_classification": '"SCENARIO"' in repository_i and "SafeRuleEngine().evaluate" in repository_i and "data_item_id=None" in repository_i and "ClassificationResultEntity(" not in repository_i,
    "applicability_immutable_retry_canonical_links": all(x in model_i for x in ("uq_applicability_resolution", "input_fingerprint", "result_json")) and all(x in repository_i for x in ("LegalBasisRuleHitLinkEntity", "LegalBasisEvidenceLinkEntity", "formal_hit.legal_basis_ids")) and "phase1i_applicability_immutable" in migration_i,
    "applicability_has_no_country_branch_or_provider": not occurrences(r"\bif\s+.*\b(country_code|regulation_code)\b.*(?:==|in)\s*[\"'\[{]", i_files),
    "phase1i_migration_frozen_explicit_dual_path": 'down_revision = "0008_phase1h"' in migration_i and 'op.create_table(' in migration_i and 'archive/export Phase1I' in migration_i and (ROOT / "tests/test_phase1i_migrations.py").exists(),
}
locale_i = read_text(SRC / "domain/localized_metadata.py")
presenter_i = read_text(SRC / "interfaces/api/metadata_presenter.py")
checks1i["locale_metadata_single_versioned_authority"] = "localized_display: LocalizedDisplayMetadata" in profiles_i and "validate_localized_payload" in governance_i and all(x in locale_i for x in ('"zh-CN"', '"zh-HK"', '"en-US"', "fallback_locale")) and "deepcopy(result)" in presenter_i
checks1i["locale_no_business_translations_in_domain_application"] = not occurrences(r"[\u3400-\u9fff]", [*i_files, SRC / "domain/localized_metadata.py"])
for name, passed in checks1i.items():
    add(name, passed, "Phase1I Rules140–150; tests/test_phase1i_domain.py, test_phase1i_postgres.py, test_phase1i_migrations.py")

from scripts.phase1j_architecture_checks import check as check_phase1j
for name, passed in check_phase1j(ROOT).items():
    add(name, passed, "Phase1J Rules152–155; focused contracts/engines/PostgreSQL/migration tests")

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
        "# Phase 1G Architecture Rule Check\n\n"
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
