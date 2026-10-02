import json
import os
from pathlib import Path

from sqlalchemy import inspect, text

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine
from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after

REQUIRED = {
    "knowledge_documents",
    "knowledge_document_versions",
    "knowledge_structure_nodes",
    "knowledge_chunks",
    "knowledge_chunk_nodes",
    "knowledge_ingestion_runs",
    "knowledge_quality_results",
    "knowledge_translations",
    "knowledge_index_versions",
    "embedding_jobs",
    "embedding_records",
    "knowledge_change_events",
    "knowledge_version_diffs",
    "knowledge_scope_resolutions",
}


def main():
    engine = build_engine(get_settings().database_url)
    ins = inspect(engine)
    tables = set(ins.get_table_names())

    def cols(table):
        return {c["name"] for c in ins.get_columns(table)}

    def fk(table):
        return {f["referred_table"] for f in ins.get_foreign_keys(table)}

    def uq(table):
        return {c["name"] for c in ins.get_unique_constraints(table)}

    def ck(table):
        return {c["name"] for c in ins.get_check_constraints(table)}

    with engine.connect() as conn:
        revision = conn.execute(text("select version_num from alembic_version")).scalar_one()
        vector = (
            conn.execute(
                text("select count(*) from pg_extension where extname='vector'")
            ).scalar_one()
            == 1
        )
        indexes = conn.execute(
            text("select indexname,indexdef from pg_indexes where schemaname='public'")
        ).all()
        indexdefs = dict(indexes)
        vector_type = conn.execute(
            text(
                "select udt_name from information_schema.columns "
                "where table_name='embedding_records' and column_name='embedding_vector'"
            )
        ).scalar_one()
    checks = {
        "phase1f_schema_present_under_current_head": revision_at_or_after(revision, "0006_phase1f"),
        "required_canonical_tables": REQUIRED <= tables,
        "existing_collection_source_reused": {
            "knowledge_collections",
            "knowledge_collection_versions",
            "knowledge_source_definitions",
        }
        <= tables
        and not {"knowledge_collections_v2", "knowledge_sources", "final_knowledge_store"} & tables,
        "existing_bindings_extended": {
            "knowledge_version_id",
            "binding_version",
            "dimensions_json",
            "permission_scopes_json",
            "provenance_json",
            "review_status",
        }
        <= cols("knowledge_bindings"),
        "document_source_fk": "knowledge_source_definitions" in fk("knowledge_documents"),
        "version_document_collection_fk": {"knowledge_documents", "knowledge_collection_versions"}
        <= fk("knowledge_document_versions"),
        "version_sequence_unique": "uq_knowledge_document_version"
        in uq("knowledge_document_versions"),
        "version_lifecycle_constraint": "ck_knowledge_lifecycle"
        in ck("knowledge_document_versions"),
        "version_effective_dates_constraint": "ck_knowledge_effective_dates"
        in ck("knowledge_document_versions"),
        "one_active_document_version": "uq_active_knowledge_document" in indexdefs
        and "WHERE" in indexdefs["uq_active_knowledge_document"],
        "canonical_legal_node_reused": "regulatory_structure_nodes"
        in fk("knowledge_structure_nodes")
        and not {"articles", "sections"} & tables,
        "structure_hierarchy_fk": "knowledge_structure_nodes" in fk("knowledge_structure_nodes"),
        "structure_locator_unique": "uq_knowledge_structure_locator"
        in uq("knowledge_structure_nodes"),
        "structure_citation_fk": "citations" in fk("knowledge_structure_nodes"),
        "structure_provenance": {
            "source_trace_json",
            "provenance_json",
            "original_text",
            "normalized_text",
            "language",
            "effective_date",
        }
        <= cols("knowledge_structure_nodes"),
        "chunk_version_fk": "knowledge_document_versions" in fk("knowledge_chunks"),
        "chunk_structure_fk": {"knowledge_chunks", "knowledge_structure_nodes"}
        <= fk("knowledge_chunk_nodes"),
        "chunk_hash_strategy_tokens": {
            "content_hash",
            "chunking_strategy_version",
            "token_count",
            "canonical_locator",
        }
        <= cols("knowledge_chunks"),
        "fts_is_derived": "USING gin" in indexdefs.get("ix_knowledge_chunks_fts", "")
        and "search_vector" in cols("knowledge_chunks"),
        "vector_is_derived": vector
        and vector_type == "vector"
        and "ck_embedding_vector_dimension" in ck("embedding_records"),
        "embedding_registry_fk": "model_deployments" in fk("embedding_records"),
        "embedding_idempotency_unique": "uq_embedding_record_version" in uq("embedding_records"),
        "index_version_contract": {
            "knowledge_version_id",
            "chunking_strategy_version",
            "embedding_config_id",
            "fts_config_version",
            "content_hash",
            "build_status",
            "derived",
        }
        <= cols("knowledge_index_versions"),
        "ingestion_idempotency_outbox": "uq_knowledge_ingestion_idempotency"
        in uq("knowledge_ingestion_runs")
        and "registry_sync_events" in fk("knowledge_ingestion_runs"),
        "quality_seven_checks_contract": {"checks_json", "reason_codes_json", "status"}
        <= cols("knowledge_quality_results"),
        "translation_review_constraint": "ck_translation_reviewer" in ck("knowledge_translations"),
        "durable_review_reused": "admin_review_tasks" in fk("knowledge_document_versions")
        and not {"knowledge_review_tasks", "phase1f_review_tasks"} & tables,
        "snapshot_scope_unique_fk": "uq_snapshot_knowledge_scope"
        in uq("knowledge_scope_resolutions")
        and {"analysis_snapshots", "projects"} <= fk("knowledge_scope_resolutions"),
        "tenant_audit_every_new_table": all(
            {"tenant_id", "record_version", "created_at", "updated_at"} <= cols(t) for t in REQUIRED
        ),
    }
    result = {
        "pass": all(checks.values()),
        "passed": sum(checks.values()),
        "total": len(checks),
        "revision": revision,
        "checks": checks,
    }
    print(json.dumps(result, indent=2))
    if os.getenv("EVIDENCE_DIR"):
        path = Path(os.environ["EVIDENCE_DIR"])
        path.mkdir(parents=True, exist_ok=True)
        (path / "phase1f_schema_check.json").write_text(json.dumps(result, indent=2) + "\n")
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
