"""Phase 1E context resolution and formal data inventory/data flow foundation.

Revision ID: 0005_phase1e
Revises: 0004_phase1d

Phase 1B formal DataItem/DataFlow/Party tables remain authoritative.
Phase 1E adds resolution, provenance, versioning, context and detail extensions only.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_phase1e"
down_revision = "0004_phase1d"
branch_labels = None
depends_on = None


def _audit_cols():
    return [
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade():
    op.create_table(
        "business_facts",
        sa.Column("fact_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_type", sa.String(160), nullable=False),
        sa.Column("normalized_key", sa.String(500), nullable=False),
        sa.Column("normalized_value_json", sa.JSON(), nullable=False),
        sa.Column("original_values_json", sa.JSON(), nullable=False),
        sa.Column("source_document_ids_json", sa.JSON(), nullable=False),
        sa.Column("resolution_method", sa.String(120), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("conflict_status", sa.String(40), nullable=False, server_default="NONE"),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "fact_type", "version", "normalized_key", name="uq_business_fact_version"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_business_fact_confidence"),
    )
    op.create_index("ix_business_fact_project_type", "business_facts", ["tenant_id", "project_id", "fact_type"])

    op.create_table(
        "business_fact_resolutions",
        sa.Column("resolution_id", sa.String(36), primary_key=True),
        sa.Column("candidate_fact_id", sa.String(36), sa.ForeignKey("business_fact_candidates.fact_id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_fact_id", sa.String(36), sa.ForeignKey("business_facts.fact_id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason_code", sa.String(120), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("reviewer_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "candidate_fact_id", "version", name="uq_business_fact_resolution_candidate_version"),
    )

    op.create_table(
        "candidate_resolutions",
        sa.Column("resolution_id", sa.String(36), primary_key=True),
        sa.Column("candidate_type", sa.String(100), nullable=False),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("formal_object_type", sa.String(100), nullable=False),
        sa.Column("formal_object_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("resolution_reason_code", sa.String(120), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("reviewer_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_type", sa.String(80), nullable=False, server_default="POLICY"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "candidate_type", "candidate_id", "version", name="uq_candidate_resolution_version"),
    )
    op.create_index("ix_candidate_resolution_formal", "candidate_resolutions", ["tenant_id", "formal_object_type", "formal_object_id"])

    op.create_table(
        "context_conflicts",
        sa.Column("conflict_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("conflict_type", sa.String(120), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=False),
        sa.Column("object_ids_json", sa.JSON(), nullable=False),
        sa.Column("reason_code", sa.String(120), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("resolution_status", sa.String(40), nullable=False, server_default="OPEN"),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(160), nullable=True),
        sa.Column("resolution_json", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_audit_cols(),
    )
    op.create_index("ix_context_conflict_project_status", "context_conflicts", ["tenant_id", "project_id", "resolution_status"])

    op.create_table(
        "product_context_candidates",
        sa.Column("product_context_candidate_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension_type", sa.String(40), nullable=False),
        sa.Column("definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "dimension_type", "definition_id", "source", "version",
            name="uq_product_context_candidate_version",
        ),
    )

    op.create_table(
        "product_contexts",
        sa.Column("product_context_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("effective_scope_json", sa.JSON(), nullable=False),
        sa.Column("resolution_status", sa.String(40), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "version", name="uq_product_context_project_version"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_product_context_confidence"),
    )

    op.create_table(
        "product_context_definition_links",
        sa.Column("product_context_definition_link_id", sa.String(36), primary_key=True),
        sa.Column("product_context_id", sa.String(36), sa.ForeignKey("product_contexts.product_context_id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension_type", sa.String(40), nullable=False),
        sa.Column("definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "product_context_id", "dimension_type", "definition_id", name="uq_product_context_definition"),
    )

    op.create_table(
        "product_scope_resolutions",
        sa.Column("product_scope_resolution_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_product_scope_json", sa.JSON(), nullable=False),
        sa.Column("detected_product_context_json", sa.JSON(), nullable=False),
        sa.Column("effective_product_scope_json", sa.JSON(), nullable=False),
        sa.Column("conflict_id", sa.String(36), sa.ForeignKey("context_conflicts.conflict_id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution_status", sa.String(40), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "version", name="uq_product_scope_resolution_version"),
    )

    op.create_table(
        "scenario_contexts",
        sa.Column("scenario_context_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "scenario_definition_id", "version", name="uq_scenario_context_version"),
    )

    op.create_table(
        "scenario_resolutions",
        sa.Column("scenario_resolution_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "scenario_definition_id", "source", "version",
            name="uq_scenario_resolution_version",
        ),
    )

    op.create_table(
        "system_contexts",
        sa.Column("system_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(250), nullable=False),
        sa.Column("system_type_ref", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("product_context_refs_json", sa.JSON(), nullable=False),
        sa.Column("party_refs_json", sa.JSON(), nullable=False),
        sa.Column("location_refs_json", sa.JSON(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "display_name", "version", name="uq_system_context_version"),
    )

    op.create_table(
        "device_contexts",
        sa.Column("device_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(250), nullable=False),
        sa.Column("device_type_ref", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("system_contexts.system_id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_context_refs_json", sa.JSON(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "display_name", "version", name="uq_device_context_version"),
    )

    op.create_table(
        "system_relations",
        sa.Column("system_relation_id", sa.String(36), primary_key=True),
        sa.Column("source_system_id", sa.String(36), sa.ForeignKey("system_contexts.system_id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_system_id", sa.String(36), sa.ForeignKey("system_contexts.system_id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(120), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "source_system_id", "target_system_id", "relation_type", name="uq_system_relation"),
    )

    op.create_table(
        "party_candidates",
        sa.Column("party_candidate_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(250), nullable=False),
        sa.Column("role_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        *_audit_cols(),
    )

    op.create_table(
        "party_resolutions",
        sa.Column("party_resolution_id", sa.String(36), primary_key=True),
        sa.Column("party_candidate_id", sa.String(36), sa.ForeignKey("party_candidates.party_candidate_id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_party_id", sa.String(36), sa.ForeignKey("project_parties.project_party_id", ondelete="SET NULL"), nullable=True),
        sa.Column("legal_entity_id", sa.String(36), sa.ForeignKey("legal_entities.legal_entity_id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason_code", sa.String(120), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "party_candidate_id", "version", name="uq_party_resolution_version"),
    )

    op.create_table(
        "data_item_resolution_details",
        sa.Column("data_item_id", sa.String(36), sa.ForeignKey("data_items.data_item_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("value_type", sa.String(120), nullable=True),
        sa.Column("format", sa.String(160), nullable=True),
        sa.Column("unit", sa.String(120), nullable=True),
        sa.Column("frequency_quantity_json", sa.JSON(), nullable=False),
        sa.Column("system_ids_json", sa.JSON(), nullable=False),
        sa.Column("device_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
    )

    op.create_table(
        "data_item_candidate_links",
        sa.Column("data_item_candidate_link_id", sa.String(36), primary_key=True),
        sa.Column("data_item_id", sa.String(36), sa.ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_data_item_id", sa.String(36), sa.ForeignKey("candidate_data_items.candidate_data_item_id", ondelete="CASCADE"), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "data_item_id", "candidate_data_item_id", name="uq_data_item_candidate_link"),
    )

    op.create_table(
        "data_item_source_trace_links",
        sa.Column("data_item_source_trace_link_id", sa.String(36), primary_key=True),
        sa.Column("data_item_id", sa.String(36), sa.ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_trace_ref_id", sa.String(36), sa.ForeignKey("source_trace_refs.source_trace_ref_id", ondelete="RESTRICT"), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "data_item_id", "source_trace_ref_id", name="uq_data_item_source_trace_link"),
    )

    op.create_table(
        "data_item_deduplication_results",
        sa.Column("deduplication_result_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("left_candidate_id", sa.String(36), sa.ForeignKey("candidate_data_items.candidate_data_item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("right_candidate_id", sa.String(36), sa.ForeignKey("candidate_data_items.candidate_data_item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("deterministic_score", sa.Float(), nullable=False),
        sa.Column("semantic_candidate_score", sa.Float(), nullable=True),
        sa.Column("reason_code", sa.String(120), nullable=False),
        sa.Column("reviewer_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "left_candidate_id", "right_candidate_id", "version", name="uq_data_item_dedup_version"),
    )

    op.create_table(
        "data_item_product_link_details",
        sa.Column("data_item_product_link_id", sa.String(36), sa.ForeignKey("data_item_product_links.data_item_product_link_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_domain_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("product_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=True),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        *_audit_cols(),
    )

    op.create_table(
        "jurisdiction_contexts",
        sa.Column("jurisdiction_context_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("jurisdiction_id", sa.String(36), sa.ForeignKey("jurisdictions.jurisdiction_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("context_type", sa.String(80), nullable=False),
        sa.Column("location_precision", sa.String(40), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "context_type", "jurisdiction_id", "version", name="uq_jurisdiction_context_version"),
    )

    op.create_table(
        "jurisdiction_resolutions",
        sa.Column("jurisdiction_resolution_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("input_value", sa.String(250), nullable=False),
        sa.Column("jurisdiction_context_id", sa.String(36), sa.ForeignKey("jurisdiction_contexts.jurisdiction_context_id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason_code", sa.String(120), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "input_value", "version", name="uq_jurisdiction_resolution_version"),
    )

    op.create_table(
        "data_flow_node_details",
        sa.Column("flow_node_id", sa.String(36), sa.ForeignKey("data_flow_nodes.flow_node_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("system_contexts.system_id", ondelete="SET NULL"), nullable=True),
        sa.Column("party_id", sa.String(36), sa.ForeignKey("project_parties.project_party_id", ondelete="SET NULL"), nullable=True),
        sa.Column("jurisdiction_context_id", sa.String(36), sa.ForeignKey("jurisdiction_contexts.jurisdiction_context_id", ondelete="SET NULL"), nullable=True),
        sa.Column("storage_or_processing_role", sa.String(120), nullable=True),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
    )

    op.create_table(
        "data_flow_edge_details",
        sa.Column("flow_edge_id", sa.String(36), sa.ForeignKey("data_flow_edges.flow_edge_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("transfer_type_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("direction", sa.String(80), nullable=False),
        sa.Column("protocol_json", sa.JSON(), nullable=False),
        sa.Column("frequency_json", sa.JSON(), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_audit_cols(),
    )

    op.create_table(
        "data_item_flow_link_details",
        sa.Column("link_id", sa.String(36), sa.ForeignKey("data_item_flow_links.link_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relationship_type", sa.String(80), nullable=False),
        sa.Column("source_trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        *_audit_cols(),
    )

    op.create_table(
        "context_resolution_runs",
        sa.Column("context_resolution_run_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("product_context_version", sa.Integer(), nullable=False),
        sa.Column("data_inventory_version", sa.Integer(), nullable=False),
        sa.Column("data_flow_version", sa.Integer(), nullable=False),
        sa.Column("statistics_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("unresolved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflict_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_required_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "project_id", "version", name="uq_context_resolution_run_version"),
    )
    op.create_index("ix_context_resolution_run_project", "context_resolution_runs", ["tenant_id", "project_id", "status"])

    op.create_table(
        "analysis_snapshot_context_pins",
        sa.Column("analysis_snapshot_context_pin_id", sa.String(36), primary_key=True),
        sa.Column("analysis_snapshot_id", sa.String(36), sa.ForeignKey("analysis_snapshots.analysis_snapshot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("context_resolution_run_id", sa.String(36), sa.ForeignKey("context_resolution_runs.context_resolution_run_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("context_resolution_version", sa.Integer(), nullable=False),
        sa.Column("product_context_version", sa.Integer(), nullable=False),
        sa.Column("data_inventory_version", sa.Integer(), nullable=False),
        sa.Column("data_flow_version", sa.Integer(), nullable=False),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id", "analysis_snapshot_id", "project_id", name="uq_analysis_snapshot_context_pin"),
    )


def downgrade():
    for table in [
        "analysis_snapshot_context_pins",
        "context_resolution_runs",
        "data_item_flow_link_details",
        "data_flow_edge_details",
        "data_flow_node_details",
        "jurisdiction_resolutions",
        "jurisdiction_contexts",
        "data_item_product_link_details",
        "data_item_deduplication_results",
        "data_item_source_trace_links",
        "data_item_candidate_links",
        "data_item_resolution_details",
        "party_resolutions",
        "party_candidates",
        "system_relations",
        "device_contexts",
        "system_contexts",
        "scenario_resolutions",
        "scenario_contexts",
        "product_scope_resolutions",
        "product_context_definition_links",
        "product_contexts",
        "product_context_candidates",
        "context_conflicts",
        "candidate_resolutions",
        "business_fact_resolutions",
        "business_facts",
    ]:
        op.drop_table(table)
