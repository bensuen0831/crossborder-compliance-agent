from __future__ import annotations
import json, os
from pathlib import Path
from sqlalchemy import inspect, text
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine

REQUIRED_TABLES={
"canonical_document_nodes","document_parse_run_details","document_parse_quality_results","document_parse_tasks",
"business_fact_candidates","candidate_data_items","candidate_data_flow_nodes","candidate_data_flow_edges",
"cross_document_links","business_fact_source_links","candidate_data_item_source_links",
"candidate_data_flow_node_source_links","candidate_data_flow_edge_source_links","cross_document_link_sources",
"analysis_snapshot_parse_run_pins","document_translation_records",
}
TRACE_COLUMNS={"document_id","document_version_id","parse_run_id","structure_node_id","page_no","sheet_name","slide_no","section_path","table_id","row_index","column_index","bbox_json","original_text_hash"}
RUN_COLUMNS={"parse_run_version","parser_profile_id","parser_name","parser_version","started_at","completed_at","native_parse_used","ocr_used","vision_used","page_count","table_count","image_count","warning_count","quality_score","error_code","language","provenance_json"}

def main():
    settings=get_settings(); engine=build_engine(settings.database_url); insp=inspect(engine)
    tables=set(insp.get_table_names())
    cols=lambda t:{c["name"]:str(c["type"]) for c in insp.get_columns(t)}
    with engine.connect() as conn:
        revision=conn.execute(text("select version_num from alembic_version")).scalar_one()
    document_tables={t for t in tables if t.startswith(("document","canonical_","candidate_","business_fact_","cross_document_","analysis_snapshot_parse_run"))}
    binary_cols=[f"{t}.{n}" for t in document_tables for n,tp in cols(t).items() if any(x in tp.upper() for x in ["BYTEA","BLOB","LARGEBINARY"])]
    document_version_aggregate_columns = set(cols("document_versions")) | set(cols("document_version_intelligence"))
    source_trace_aggregate_columns = set(cols("source_trace_refs")) | set(cols("source_trace_details"))
    checks={
        "phase1d_schema_present_under_current_head":revision in {"0004_phase1d","0005_phase1e"},
        "required_tables_present":REQUIRED_TABLES<=tables,
        "document_versions_metadata_fields": {"filename","size_bytes","language","storage_ref","content_hash","mime_type"}<=document_version_aggregate_columns,
        "document_version_intelligence_one_to_one": set(insp.get_pk_constraint("document_version_intelligence").get("constrained_columns") or [])=={"document_version_id"},
        "parse_run_versioned_fields":RUN_COLUMNS<=set(cols("document_parse_run_details")),
        "source_trace_exact_locator_fields":TRACE_COLUMNS<=source_trace_aggregate_columns,
        "source_trace_detail_one_to_one": set(insp.get_pk_constraint("source_trace_details").get("constrained_columns") or [])=={"source_trace_ref_id"},
        "canonical_structure_not_plain_text_blob_only":{"node_type","parent_node_id","sequence","page_no","sheet_name","slide_no","source_locator_json","original_text","normalized_text"}<=set(cols("canonical_document_nodes")),
        "spreadsheet_provenance_storage": {"metadata_json","source_locator_json"}<=set(cols("canonical_document_nodes")),
        "snapshot_parse_run_pin_present":"analysis_snapshot_parse_run_pins" in tables,
        "candidate_fact_item_flow_sources_present":{"business_fact_source_links","candidate_data_item_source_links","candidate_data_flow_node_source_links","candidate_data_flow_edge_source_links"}<=tables,
        "original_binary_not_stored_in_domain_db":not binary_cols,
        "parse_task_idempotency_unique": any(c.get("name")=="uq_parse_task_idempotency" for c in insp.get_unique_constraints("document_parse_tasks")),
        "parse_run_version_unique": any(c.get("name")=="uq_document_parse_run_detail_version" for c in insp.get_unique_constraints("document_parse_run_details")),
        "parse_run_detail_one_to_one": "parse_run_id" in cols("document_parse_run_details"),
    }
    result={"pass":all(checks.values()),"passed":sum(checks.values()),"total":len(checks),"revision":revision,"checks":checks,"binary_columns":binary_cols,"document_tables":sorted(document_tables)}
    print(json.dumps(result,indent=2,sort_keys=True))
    out=os.getenv("EVIDENCE_DIR")
    if out:
        p=Path(out);p.mkdir(parents=True,exist_ok=True)
        (p/"phase1d_schema_check.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        (p/"phase1d_database_schema_result.md").write_text("# Phase 1D Database Schema Result\n\n"+f"**Decision: {'PASS' if result['pass'] else 'FAIL'} — {result['passed']}/{result['total']} checks passed.**\n\n"+f"- Alembic revision: `{revision}`\n- Domain binary columns: `{binary_cols}`\n")
    raise SystemExit(0 if result["pass"] else 2)

if __name__=="__main__": main()
