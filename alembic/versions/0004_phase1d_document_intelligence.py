"""Phase 1D document intelligence foundation.

Revision ID: 0004_phase1d
Revises: 0003_phase1c

Phase 1B identity tables remain frozen. Phase 1D adds 1:1 detail/projection tables
and document-intelligence persistence without altering LangGraph checkpoint internals.
"""
from alembic import op
import sqlalchemy as sa

revision="0004_phase1d"
down_revision="0003_phase1c"
branch_labels=None
depends_on=None


def _audit_cols():
    return [
        sa.Column("tenant_id",sa.String(36),nullable=False),
        sa.Column("record_version",sa.Integer(),nullable=False,server_default="1"),
        sa.Column("status",sa.String(40),nullable=False,server_default="ACTIVE"),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade():
    op.create_table("document_version_intelligence",
        sa.Column("document_version_id",sa.String(36),sa.ForeignKey("document_versions.document_version_id",ondelete="CASCADE"),primary_key=True),
        sa.Column("filename",sa.String(255),nullable=False),
        sa.Column("size_bytes",sa.Integer(),nullable=False),
        sa.Column("language",sa.String(40),nullable=True),
        *_audit_cols())

    op.create_table("document_parse_run_details",
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),primary_key=True),
        sa.Column("document_version_id",sa.String(36),sa.ForeignKey("document_versions.document_version_id",ondelete="CASCADE"),nullable=False),
        sa.Column("parse_run_version",sa.Integer(),nullable=False),
        sa.Column("parser_profile_id",sa.String(120),nullable=False),
        sa.Column("parser_name",sa.String(120),nullable=False),
        sa.Column("parser_version",sa.String(80),nullable=False),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("native_parse_used",sa.Boolean(),nullable=False,server_default=sa.text("false")),
        sa.Column("ocr_used",sa.Boolean(),nullable=False,server_default=sa.text("false")),
        sa.Column("vision_used",sa.Boolean(),nullable=False,server_default=sa.text("false")),
        sa.Column("page_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("table_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("image_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("warning_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("quality_score",sa.Float(),nullable=True),
        sa.Column("error_code",sa.String(120),nullable=True),
        sa.Column("language",sa.String(40),nullable=True),
        sa.Column("provenance_json",sa.JSON(),nullable=False,server_default=sa.text("'{}'::json")),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id","document_version_id","parse_run_version",name="uq_document_parse_run_detail_version"))
    op.create_index("ix_document_parse_run_detail_status","document_parse_run_details",["tenant_id","document_version_id","status"])

    op.create_table("canonical_document_nodes",
        sa.Column("structure_node_id",sa.String(36),primary_key=True),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),nullable=False),
        sa.Column("document_version_id",sa.String(36),sa.ForeignKey("document_versions.document_version_id",ondelete="CASCADE"),nullable=False),
        sa.Column("node_type",sa.String(40),nullable=False),
        sa.Column("parent_node_id",sa.String(36),nullable=True),
        sa.Column("sequence",sa.Integer(),nullable=False),
        sa.Column("page_no",sa.Integer(),nullable=True),
        sa.Column("sheet_name",sa.String(255),nullable=True),
        sa.Column("slide_no",sa.Integer(),nullable=True),
        sa.Column("section_path",sa.String(500),nullable=True),
        sa.Column("bbox_json",sa.JSON(),nullable=True),
        sa.Column("original_text",sa.Text(),nullable=True),
        sa.Column("normalized_text",sa.Text(),nullable=True),
        sa.Column("language",sa.String(40),nullable=True),
        sa.Column("source_locator_json",sa.JSON(),nullable=False,server_default=sa.text("'{}'::json")),
        sa.Column("parser_confidence",sa.Float(),nullable=True),
        sa.Column("provenance_json",sa.JSON(),nullable=False,server_default=sa.text("'{}'::json")),
        sa.Column("metadata_json",sa.JSON(),nullable=False,server_default=sa.text("'{}'::json")),
        *_audit_cols(),
        sa.UniqueConstraint("tenant_id","parse_run_id","structure_node_id",name="uq_canonical_node_run"))
    op.create_foreign_key("fk_canonical_parent","canonical_document_nodes","canonical_document_nodes",["parent_node_id"],["structure_node_id"],ondelete="CASCADE")
    op.create_index("ix_canonical_node_locator","canonical_document_nodes",["tenant_id","parse_run_id","page_no","sheet_name","slide_no"])

    op.create_table("source_trace_details",
        sa.Column("source_trace_ref_id",sa.String(36),sa.ForeignKey("source_trace_refs.source_trace_ref_id",ondelete="CASCADE"),primary_key=True),
        sa.Column("document_id",sa.String(36),sa.ForeignKey("documents.document_id",ondelete="CASCADE"),nullable=False),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),nullable=False),
        sa.Column("structure_node_id",sa.String(36),sa.ForeignKey("canonical_document_nodes.structure_node_id",ondelete="CASCADE"),nullable=False),
        sa.Column("sheet_name",sa.String(255),nullable=True),
        sa.Column("slide_no",sa.Integer(),nullable=True),
        sa.Column("section_path",sa.String(500),nullable=True),
        sa.Column("table_id",sa.String(255),nullable=True),
        sa.Column("row_index",sa.Integer(),nullable=True),
        sa.Column("column_index",sa.Integer(),nullable=True),
        sa.Column("original_text_hash",sa.String(128),nullable=False),
        *_audit_cols())
    op.create_index("ix_source_trace_detail_parse_node","source_trace_details",["tenant_id","parse_run_id","structure_node_id"])

    op.create_table("document_parse_quality_results",
        sa.Column("quality_result_id",sa.String(36),primary_key=True),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),nullable=False),
        sa.Column("text_coverage",sa.Float(),nullable=False),sa.Column("page_coverage",sa.Float(),nullable=False),
        sa.Column("table_extraction_quality",sa.Float(),nullable=False),sa.Column("ocr_confidence",sa.Float(),nullable=True),
        sa.Column("layout_quality",sa.Float(),nullable=False),sa.Column("structural_completeness",sa.Float(),nullable=False),
        sa.Column("language_detection_confidence",sa.Float(),nullable=False),sa.Column("quality_status",sa.String(40),nullable=False),
        sa.Column("quality_score",sa.Float(),nullable=False),*_audit_cols(),
        sa.UniqueConstraint("tenant_id","parse_run_id",name="uq_parse_quality_run"))

    op.create_table("document_parse_tasks",
        sa.Column("task_id",sa.String(36),primary_key=True),
        sa.Column("document_version_id",sa.String(36),sa.ForeignKey("document_versions.document_version_id",ondelete="CASCADE"),nullable=False),
        sa.Column("parser_profile_id",sa.String(120),nullable=False),sa.Column("idempotency_key",sa.String(255),nullable=False),
        sa.Column("attempts",sa.Integer(),nullable=False,server_default="0"),sa.Column("error_code",sa.String(120),nullable=True),
        *_audit_cols(),sa.UniqueConstraint("tenant_id","document_version_id","idempotency_key",name="uq_parse_task_idempotency"))
    op.create_index("ix_parse_task_status","document_parse_tasks",["tenant_id","status","created_at"])

    op.create_table("business_fact_candidates",
        sa.Column("fact_id",sa.String(36),primary_key=True),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),nullable=False),
        sa.Column("fact_type",sa.String(160),nullable=False),sa.Column("normalized_value_json",sa.JSON(),nullable=False),
        sa.Column("original_value_json",sa.JSON(),nullable=False),sa.Column("extraction_method",sa.String(100),nullable=False),
        sa.Column("confidence",sa.Float(),nullable=False),sa.Column("validation_status",sa.String(40),nullable=False),
        sa.Column("conflict_status",sa.String(40),nullable=False),*_audit_cols())

    op.create_table("candidate_data_items",
        sa.Column("candidate_data_item_id",sa.String(36),primary_key=True),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),nullable=False),
        sa.Column("raw_name",sa.String(500),nullable=False),sa.Column("normalized_name",sa.String(500),nullable=False),
        sa.Column("description",sa.Text(),nullable=True),sa.Column("value_type",sa.String(100),nullable=True),
        sa.Column("unit",sa.String(100),nullable=True),sa.Column("quantity_metadata_json",sa.JSON(),nullable=False,server_default=sa.text("'{}'::json")),
        sa.Column("system_ref",sa.String(255),nullable=True),sa.Column("confidence",sa.Float(),nullable=False),*_audit_cols())
    op.create_index("ix_candidate_item_parse_name","candidate_data_items",["tenant_id","parse_run_id","normalized_name"])

    op.create_table("candidate_data_flow_nodes",
        sa.Column("candidate_node_id",sa.String(36),primary_key=True),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),nullable=False),
        sa.Column("name",sa.String(500),nullable=False),sa.Column("node_type_candidate",sa.String(120),nullable=True),
        sa.Column("location_candidate",sa.String(255),nullable=True),sa.Column("party_candidate",sa.String(255),nullable=True),
        sa.Column("system_candidate",sa.String(255),nullable=True),sa.Column("confidence",sa.Float(),nullable=False),*_audit_cols())

    op.create_table("candidate_data_flow_edges",
        sa.Column("candidate_edge_id",sa.String(36),primary_key=True),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="CASCADE"),nullable=False),
        sa.Column("source_candidate_node_id",sa.String(36),sa.ForeignKey("candidate_data_flow_nodes.candidate_node_id",ondelete="CASCADE"),nullable=False),
        sa.Column("target_candidate_node_id",sa.String(36),sa.ForeignKey("candidate_data_flow_nodes.candidate_node_id",ondelete="CASCADE"),nullable=False),
        sa.Column("direction",sa.String(80),nullable=True),sa.Column("transfer_type_candidate",sa.String(160),nullable=True),
        sa.Column("data_item_refs_json",sa.JSON(),nullable=False,server_default=sa.text("'[]'::json")),
        sa.Column("confidence",sa.Float(),nullable=False),*_audit_cols())

    op.create_table("cross_document_links",
        sa.Column("cross_document_link_id",sa.String(36),primary_key=True),
        sa.Column("project_id",sa.String(36),sa.ForeignKey("projects.project_id",ondelete="CASCADE"),nullable=False),
        sa.Column("link_type",sa.String(100),nullable=False),sa.Column("left_object_type",sa.String(100),nullable=False),
        sa.Column("left_object_id",sa.String(36),nullable=False),sa.Column("right_object_type",sa.String(100),nullable=False),
        sa.Column("right_object_id",sa.String(36),nullable=False),sa.Column("confidence",sa.Float(),nullable=False),*_audit_cols())

    for table,pk,parent_col,parent_table,parent_pk,constraint in [
        ("business_fact_source_links","business_fact_source_link_id","fact_id","business_fact_candidates","fact_id","uq_fact_source_link"),
        ("candidate_data_item_source_links","candidate_data_item_source_link_id","candidate_data_item_id","candidate_data_items","candidate_data_item_id","uq_candidate_item_source_link"),
        ("candidate_data_flow_node_source_links","candidate_data_flow_node_source_link_id","candidate_node_id","candidate_data_flow_nodes","candidate_node_id",None),
        ("candidate_data_flow_edge_source_links","candidate_data_flow_edge_source_link_id","candidate_edge_id","candidate_data_flow_edges","candidate_edge_id",None),
        ("cross_document_link_sources","cross_document_link_source_id","cross_document_link_id","cross_document_links","cross_document_link_id",None),
    ]:
        cols=[sa.Column(pk,sa.String(36),primary_key=True),
              sa.Column(parent_col,sa.String(36),sa.ForeignKey(f"{parent_table}.{parent_pk}",ondelete="CASCADE"),nullable=False),
              sa.Column("source_trace_ref_id",sa.String(36),sa.ForeignKey("source_trace_refs.source_trace_ref_id",ondelete="CASCADE"),nullable=False),
              *_audit_cols()]
        if constraint: cols.append(sa.UniqueConstraint("tenant_id",parent_col,"source_trace_ref_id",name=constraint))
        op.create_table(table,*cols)

    op.create_table("analysis_snapshot_parse_run_pins",
        sa.Column("pin_id",sa.String(36),primary_key=True),
        sa.Column("analysis_snapshot_id",sa.String(36),sa.ForeignKey("analysis_snapshots.analysis_snapshot_id",ondelete="CASCADE"),nullable=False),
        sa.Column("document_version_id",sa.String(36),sa.ForeignKey("document_versions.document_version_id",ondelete="CASCADE"),nullable=False),
        sa.Column("parse_run_id",sa.String(36),sa.ForeignKey("document_parse_runs.document_parse_run_id",ondelete="RESTRICT"),nullable=False),
        *_audit_cols(),sa.UniqueConstraint("tenant_id","analysis_snapshot_id","document_version_id",name="uq_snapshot_document_parse_pin"))

    op.create_table("document_translation_records",
        sa.Column("translation_record_id",sa.String(36),primary_key=True),
        sa.Column("structure_node_id",sa.String(36),sa.ForeignKey("canonical_document_nodes.structure_node_id",ondelete="CASCADE"),nullable=False),
        sa.Column("source_language",sa.String(40),nullable=False),sa.Column("target_language",sa.String(40),nullable=False),
        sa.Column("translated_text",sa.Text(),nullable=False),sa.Column("translation_model_ref",sa.String(255),nullable=False),
        sa.Column("translation_version",sa.String(80),nullable=False),sa.Column("confidence",sa.Float(),nullable=True),
        sa.Column("created_at_provider",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")),
        *_audit_cols())


def downgrade():
    for t in ["document_translation_records","analysis_snapshot_parse_run_pins","cross_document_link_sources",
              "candidate_data_flow_edge_source_links","candidate_data_flow_node_source_links","candidate_data_item_source_links",
              "business_fact_source_links","cross_document_links","candidate_data_flow_edges","candidate_data_flow_nodes",
              "candidate_data_items","business_fact_candidates","document_parse_tasks","document_parse_quality_results",
              "source_trace_details","canonical_document_nodes","document_parse_run_details","document_version_intelligence"]:
        op.drop_table(t)
