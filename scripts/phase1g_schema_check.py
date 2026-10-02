"""Measured PostgreSQL Phase 1G schema assertions; preserves all earlier schema gates."""

import json
import os
from pathlib import Path

from sqlalchemy import inspect, text

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine

REQUIRED = {
    "knowledge_runtime_publications",
    "retrieval_policies",
    "retrieval_runs",
    "evidence_packs",
    "evidence_pack_items",
    "knowledge_sufficiency_policies",
    "knowledge_sufficiency_results",
    "trusted_source_policies",
    "external_evidence_candidates",
    "external_evidence_validation_results",
    "runtime_verified_external_evidence",
    "wiki_pages",
    "wiki_versions",
    "wiki_source_bindings",
    "wiki_citations",
    "wiki_reviews",
    "wiki_publish_records",
    "knowledge_graph_nodes",
    "knowledge_graph_edges",
}


def main():
    engine = build_engine(get_settings().database_url)
    ins = inspect(engine)
    tables = set(ins.get_table_names())

    def ck(t):
        return {c["name"] for c in ins.get_check_constraints(t)}

    def fk(t):
        return {c["referred_table"] for c in ins.get_foreign_keys(t)}

    def uq(t):
        return {c["name"] for c in ins.get_unique_constraints(t)}

    with engine.connect() as c:
        revision = c.scalar(text("SELECT version_num FROM alembic_version"))
        indexes = dict(
            c.execute(
                text("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public'")
            ).all()
        )
    checks = {
        "alembic_head_0007_phase1g": revision == "0007_phase1g",
        "required_derived_tables": REQUIRED <= tables,
        "no_parallel_canonical_knowledge": not {
            "formal_knowledge_documents",
            "retrieval_knowledge_chunks",
            "final_knowledge_store",
            "vector_knowledge_store",
            "external_active_knowledge",
        }
        & tables,
        "run_snapshot_project_policy_fk": {"analysis_snapshots", "projects", "retrieval_policies"}
        <= fk("retrieval_runs"),
        "run_idempotency_unique": "uq_retrieval_idempotency" in uq("retrieval_runs"),
        "run_status_constraint": "ck_retrieval_run_status" in ck("retrieval_runs"),
        "one_pack_per_run": "uq_retrieval_pack" in uq("evidence_packs"),
        "pack_derived_constraint": "ck_pack_derived" in ck("evidence_packs"),
        "items_exact_source_chain": "ck_evidence_exact_source_chain" in ck("evidence_pack_items"),
        "items_canonical_and_external_fk": {
            "knowledge_document_versions",
            "knowledge_chunks",
            "knowledge_structure_nodes",
            "runtime_verified_external_evidence",
            "citations",
        }
        <= fk("evidence_pack_items"),
        "sufficiency_policy_pack_fk": {"knowledge_sufficiency_policies", "evidence_packs"}
        <= fk("knowledge_sufficiency_results"),
        "sufficiency_status_constraint": "ck_sufficiency_status"
        in ck("knowledge_sufficiency_results"),
        "one_sufficiency_per_pack": "uq_pack_sufficiency" in uq("knowledge_sufficiency_results"),
        "external_validation_candidate_fk": "external_evidence_candidates"
        in fk("external_evidence_validation_results"),
        "external_validation_status_constraint": "ck_external_validation"
        in ck("external_evidence_validation_results"),
        "external_never_active": "ck_runtime_external_not_active"
        in ck("runtime_verified_external_evidence"),
        "external_snapshot_source_policy_unique": "uq_snapshot_external_source"
        in uq("runtime_verified_external_evidence"),
        "external_snapshot_policy_source_fk": {
            "analysis_snapshots",
            "trusted_source_policies",
            "retrieval_policies",
            "knowledge_sufficiency_policies",
            "knowledge_source_definitions",
        }
        <= fk("runtime_verified_external_evidence"),
        "wiki_canonical_sources_fk": "knowledge_document_versions" in fk("wiki_source_bindings"),
        "wiki_canonical_citations_fk": "citations" in fk("wiki_citations"),
        "wiki_durable_review_reuse": "admin_review_tasks" in fk("wiki_reviews")
        and not {"wiki_review_tasks", "retrieval_review_tasks"} & tables,
        "wiki_publish_unique": "uq_wiki_publish" in uq("wiki_publish_records"),
        "wiki_draft_review_legal_boundary": {
            "ck_wiki_derived",
            "ck_wiki_review_boundary",
            "ck_wiki_lifecycle",
        }
        <= ck("wiki_versions"),
        "wiki_one_active_version": "uq_wiki_active_version" in indexes,
        "graph_node_review_and_derived": {"ck_graph_node_derived", "ck_graph_node_review"}
        <= ck("knowledge_graph_nodes"),
        "graph_edge_review_and_derived": {"ck_graph_edge_derived", "ck_graph_edge_review"}
        <= ck("knowledge_graph_edges"),
        "graph_source_chain_fk": {
            "knowledge_documents",
            "knowledge_document_versions",
            "evidence_references",
            "jurisdictions",
            "admin_review_tasks",
        }
        <= fk("knowledge_graph_nodes"),
        "graph_edge_node_registry_fk": {"knowledge_graph_nodes", "metadata_definitions"}
        <= fk("knowledge_graph_edges"),
    }
    checks.update(
        {
            "runtime_publication_version_outbox_fk": {
                "knowledge_document_versions",
                "registry_sync_events",
            }
            <= fk("knowledge_runtime_publications"),
            "runtime_ready_index_registry_cache_barrier": "ck_runtime_ready_barrier"
            in ck("knowledge_runtime_publications"),
            "runtime_publication_status_constraint": "ck_runtime_publication_status"
            in ck("knowledge_runtime_publications"),
            "runtime_publication_one_event": "uq_runtime_publication_event"
            in uq("knowledge_runtime_publications"),
            "runtime_pins_index_embedding_policy_fk": {
                "knowledge_index_versions",
                "model_deployments",
                "retrieval_policies",
            }
            <= fk("knowledge_runtime_publications"),
        }
    )
    for table in sorted(REQUIRED):
        checks[table + "_tenant_audit"] = {
            "tenant_id",
            "record_version",
            "created_at",
            "updated_at",
        } <= {c["name"] for c in ins.get_columns(table)}
    for kind, table in [
        ("retrieval", "retrieval_policies"),
        ("sufficiency", "knowledge_sufficiency_policies"),
        ("trusted_source", "trusted_source_policies"),
    ]:
        checks[kind + "_policy_version_unique"] = "uq_" + kind + "_policy_version" in uq(table)
        checks[kind + "_one_active_policy"] = "uq_" + kind + "_active_policy" in indexes
    result = dict(
        pass_=all(checks.values()),
        passed=sum(checks.values()),
        total=len(checks),
        revision=revision,
        checks=checks,
    )
    result["pass"] = result.pop("pass_")
    print(json.dumps(result, indent=2))
    if os.getenv("EVIDENCE_DIR"):
        (Path(os.environ["EVIDENCE_DIR"]) / "phase1g_schema_check.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
