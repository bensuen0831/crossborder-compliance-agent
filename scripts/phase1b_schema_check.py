from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import inspect, text

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine
from crossborder_compliance.infrastructure.persistence.models import Base


REQUIRED_TABLES = {
    "tenants",
    "organizations",
    "projects",
    "project_versions",
    "legal_entities",
    "project_parties",
    "party_role_assignments",
    "contract_party_links",
    "documents",
    "document_versions",
    "source_trace_refs",
    "document_parse_runs",
    "data_items",
    "data_item_groups",
    "data_flow_nodes",
    "data_flow_edges",
    "data_item_flow_links",
    "data_item_product_links",
    "data_flow_party_links",
    "path_step_responsible_parties",
    "jurisdictions",
    "jurisdiction_relations",
    "classification_schemes",
    "classification_categories",
    "classification_levels",
    "classification_results",
    "evidence_references",
    "citations",
    "legal_basis_items",
    "legal_basis_rule_hit_links",
    "legal_basis_evidence_links",
    "analysis_snapshots",
    "workflow_runs",
    "workflow_node_runs",
    "analysis_stage_results",
    "review_tasks",
    "review_decisions",
    "execution_idempotency_records",
    "interaction_sessions",
    "conversation_threads",
    "conversation_messages",
    "channel_contexts",
}

FORBIDDEN_FORMAL_TABLES = {
    "data_classifications",
    "workflow_stage_views",
}


def _write(name: str, text_body: str) -> None:
    evidence_dir = Path(os.getenv("EVIDENCE_DIR", "artifacts/phase1a-runtime"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / name).write_text(text_body.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    metadata_tables = set(Base.metadata.tables)

    with engine.connect() as conn:
        alembic_revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    required_missing = sorted(REQUIRED_TABLES - tables)
    forbidden_present = sorted(FORBIDDEN_FORMAL_TABLES & tables)
    checkpoint_owned_by_domain = sorted(
        name for name in metadata_tables if name.startswith("checkpoint")
    )

    project_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("project_versions")}
    legal_basis_rule_hit_fks = {
        fk["referred_table"] for fk in inspector.get_foreign_keys("legal_basis_rule_hit_links")
    }
    conversation_fks = {
        fk["referred_table"] for fk in inspector.get_foreign_keys("conversation_threads")
    }

    project_uniques = {
        tuple(sorted(uq["column_names"] or []))
        for uq in inspector.get_unique_constraints("project_versions")
    }
    legal_basis_uniques = {
        tuple(sorted(uq["column_names"] or []))
        for uq in inspector.get_unique_constraints("legal_basis_rule_hit_links")
    }
    project_indexes = {
        idx["name"] for idx in inspector.get_indexes("projects") if idx.get("name")
    }
    data_item_indexes = {
        idx["name"] for idx in inspector.get_indexes("data_items") if idx.get("name")
    }

    assertions = {
        "phase1b_schema_present_under_current_head": alembic_revision in {"0002_phase1b", "0003_phase1c"},
        "all_required_phase1b_tables_exist": not required_missing,
        "no_parallel_classification_source_table": "data_classifications" not in tables,
        "workflow_stage_view_not_persisted": "workflow_stage_views" not in tables,
        "regulatory_structure_node_present": "regulatory_structure_nodes" in tables,
        "legal_basis_rule_hit_m2m_table_present": "legal_basis_rule_hit_links" in tables,
        "legal_basis_evidence_m2m_table_present": "legal_basis_evidence_links" in tables,
        "api_and_execution_idempotency_separate": {
            "api_idempotency_records",
            "execution_idempotency_records",
        }.issubset(tables),
        "domain_metadata_excludes_langgraph_checkpoint_tables": not checkpoint_owned_by_domain,
        "project_version_fk_verified": "projects" in project_fks,
        "legal_basis_rule_hit_fk_verified": {
            "legal_basis_items",
            "rule_hits",
        }.issubset(legal_basis_rule_hit_fks),
        "conversation_fk_verified": "interaction_sessions" in conversation_fks,
        "project_version_unique_verified": tuple(sorted(("tenant_id", "project_id", "version_no")))
        in project_uniques,
        "legal_basis_rule_hit_unique_verified": tuple(
            sorted(("tenant_id", "legal_basis_id", "rule_hit_id"))
        )
        in legal_basis_uniques,
        "important_project_index_verified": "ix_projects_tenant_status" in project_indexes,
        "important_data_item_index_verified": "ix_data_items_project" in data_item_indexes,
    }

    result = {
        "pass": all(assertions.values()),
        "alembic_revision": alembic_revision,
        "assertions": assertions,
        "required_missing": required_missing,
        "forbidden_present": forbidden_present,
        "domain_checkpoint_tables": checkpoint_owned_by_domain,
        "table_count": len(tables),
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    rows = ["| Assertion | Result |", "|---|---|"]
    rows.extend(
        f"| `{name}` | **{'PASS' if passed else 'FAIL'}** |"
        for name, passed in assertions.items()
    )
    _write(
        "database_schema_result.md",
        "# Phase 1B Database Schema Result\n\n"
        f"**Decision: {'PASS' if result['pass'] else 'FAIL'}**\n\n"
        + "\n".join(rows)
        + f"\n\n- Alembic revision: `{alembic_revision}`"
        + f"\n- Database table count: `{len(tables)}`"
        + f"\n- Missing required tables: `{required_missing}`"
        + f"\n- Forbidden formal tables present: `{forbidden_present}`",
    )
    _write(
        "source_of_truth_check.md",
        "# Phase 1B Source-of-Truth Check\n\n"
        + "\n".join(
            [
                f"- classification_results authoritative / no data_classifications: **{'PASS' if assertions['no_parallel_classification_source_table'] else 'FAIL'}**",
                f"- RegulatoryStructureNode canonical persistence: **{'PASS' if assertions['regulatory_structure_node_present'] else 'FAIL'}**",
                f"- WorkflowStageView projection-only / not persisted: **{'PASS' if assertions['workflow_stage_view_not_persisted'] else 'FAIL'}**",
                f"- LegalBasis ↔ RuleHit M:N: **{'PASS' if assertions['legal_basis_rule_hit_m2m_table_present'] else 'FAIL'}**",
                f"- AnalysisSnapshot separate from LangGraph checkpoint metadata: **{'PASS' if assertions['domain_metadata_excludes_langgraph_checkpoint_tables'] else 'FAIL'}**",
                f"- API / workflow idempotency separated: **{'PASS' if assertions['api_and_execution_idempotency_separate'] else 'FAIL'}**",
            ]
        ),
    )
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
