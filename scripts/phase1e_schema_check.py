from __future__ import annotations
import json, os
from pathlib import Path

from sqlalchemy import inspect, text

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_engine

REQUIRED={
    "business_facts","business_fact_resolutions","candidate_resolutions","context_conflicts",
    "product_context_candidates","product_contexts","product_context_definition_links","product_scope_resolutions",
    "scenario_contexts","scenario_resolutions","system_contexts","device_contexts","party_candidates","party_resolutions",
    "data_item_resolution_details","data_item_candidate_links","data_item_source_trace_links",
    "data_item_deduplication_results","data_item_product_link_details",
    "jurisdiction_contexts","jurisdiction_resolutions","data_flow_node_details",
    "data_flow_edge_details","data_item_flow_link_details","context_resolution_runs",
    "analysis_snapshot_context_pins",
}
FORBIDDEN={
    "formal_data_items","resolved_data_items","final_data_items",
    "formal_data_flow_nodes","formal_data_flow_edges","resolved_data_flows",
    "context_review_tasks","phase1e_review_tasks",
}

def main():
    engine=build_engine(get_settings().database_url)
    insp=inspect(engine)
    tables=set(insp.get_table_names())
    cols=lambda t:{c["name"] for c in insp.get_columns(t)}
    fks=lambda t:insp.get_foreign_keys(t)
    with engine.connect() as conn:
        revision=conn.execute(text("select version_num from alembic_version")).scalar_one()

    product_fk={fk["referred_table"] for fk in fks("product_context_definition_links")}
    product_candidate_fk={fk["referred_table"] for fk in fks("product_context_candidates")}
    scenario_fk={fk["referred_table"] for fk in fks("scenario_contexts")}
    scenario_resolution_fk={fk["referred_table"] for fk in fks("scenario_resolutions")}
    item_source_fk={fk["referred_table"] for fk in fks("data_item_source_trace_links")}
    checks={
        "alembic_head_0005_phase1e": revision=="0005_phase1e",
        "phase1e_required_tables_present": REQUIRED<=tables,
        "no_parallel_data_item_source_of_truth": {"data_items"}<=tables and not (FORBIDDEN & tables),
        "no_parallel_data_flow_source_of_truth": {"data_flow_nodes","data_flow_edges","data_item_flow_links"}<=tables and not (FORBIDDEN & tables),
        "candidate_resolution_persists_candidate_formal_boundary": {"candidate_type","candidate_id","formal_object_type","formal_object_id","action","version"}<=cols("candidate_resolutions"),
        "business_fact_resolution_preserves_candidate": {"candidate_fact_id","business_fact_id","action"}<=cols("business_fact_resolutions"),
        "product_context_registry_fk": "metadata_definitions" in product_fk,
        "product_context_candidate_registry_fk": "metadata_definitions" in product_candidate_fk,
        "scenario_context_registry_fk": "metadata_definitions" in scenario_fk,
        "scenario_resolution_registry_fk": "metadata_definitions" in scenario_resolution_fk,
        "product_conflict_explicit": {"conflict_id","selected_product_scope_json","detected_product_context_json","effective_product_scope_json"}<=cols("product_scope_resolutions"),
        "data_item_detail_one_to_one": set(insp.get_pk_constraint("data_item_resolution_details").get("constrained_columns") or [])=={"data_item_id"},
        "formal_data_item_has_candidate_links": {"data_item_id","candidate_data_item_id"}<=cols("data_item_candidate_links"),
        "formal_data_item_has_source_trace_links": "source_trace_refs" in item_source_fk,
        "formal_counts_are_separate": {"statistics_json","data_inventory_version","data_flow_version"}<=cols("context_resolution_runs") and "data_item_groups" in tables,
        "data_flow_is_structured": {"system_id","party_id","jurisdiction_context_id","validation_status"}<=cols("data_flow_node_details") and {"direction","protocol_json","frequency_json","validation_status"}<=cols("data_flow_edge_details"),
        "data_item_flow_link_is_structured": {"relationship_type","source_trace_ids_json","confidence"}<=cols("data_item_flow_link_details"),
        "jurisdiction_is_context_not_regulation": {"jurisdiction_id","context_type","location_precision","source","confidence"}<=cols("jurisdiction_contexts") and not any("regulation" in c for c in cols("jurisdiction_contexts")),
        "canonical_coordinates_are_optional_context_fields": {"latitude","longitude","location_precision"}<=cols("jurisdiction_contexts"),
        "snapshot_context_pin_versioned": {"context_resolution_run_id","context_resolution_version","product_context_version","data_inventory_version","data_flow_version"}<=cols("analysis_snapshot_context_pins"),
        "existing_review_task_reused": "review_tasks" in tables and not ({"context_review_tasks","phase1e_review_tasks"} & tables),
        "phase1b_formal_tables_remain_present": {"data_items","data_item_groups","data_flow_nodes","data_flow_edges","data_item_flow_links","data_item_product_links","project_parties","party_role_assignments"}<=tables,
    }
    result={
        "pass":all(checks.values()),"passed":sum(checks.values()),"total":len(checks),
        "revision":revision,"checks":checks,"missing_tables":sorted(REQUIRED-tables),
        "forbidden_present":sorted(FORBIDDEN&tables),
    }
    print(json.dumps(result,indent=2,sort_keys=True))
    out=os.getenv("EVIDENCE_DIR")
    if out:
        p=Path(out);p.mkdir(parents=True,exist_ok=True)
        (p/"phase1e_schema_check.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        (p/"phase1e_database_schema_result.md").write_text(
            "# Phase 1E Database Schema Result\n\n"
            +f"**Decision: {'PASS' if result['pass'] else 'FAIL'} — {result['passed']}/{result['total']} checks passed.**\n\n"
            +f"- Alembic revision: `{revision}`\n"
            +f"- Missing tables: `{result['missing_tables']}`\n"
            +f"- Forbidden parallel SoT tables: `{result['forbidden_present']}`\n"
        )
    raise SystemExit(0 if result["pass"] else 2)

if __name__=="__main__":
    main()
