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
