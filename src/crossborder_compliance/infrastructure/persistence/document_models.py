from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin, utcnow


class DocumentVersionIntelligenceEntity(TenantAuditMixin, Base):
    __tablename__ = "document_version_intelligence"
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), primary_key=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)


class DocumentParseRunDetailEntity(TenantAuditMixin, Base):
    __tablename__ = "document_parse_run_details"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "document_version_id", "parse_run_version",
            name="uq_document_parse_run_detail_version",
        ),
        Index("ix_document_parse_run_detail_status", "tenant_id", "document_version_id", "status"),
    )
    parse_run_id: Mapped[str] = mapped_column(
        ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), primary_key=True
    )
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=False
    )
    parse_run_version: Mapped[int] = mapped_column(Integer, nullable=False)
    parser_profile_id: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    native_parse_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vision_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SourceTraceDetailEntity(TenantAuditMixin, Base):
    __tablename__ = "source_trace_details"
    __table_args__ = (
        Index("ix_source_trace_detail_parse_node", "tenant_id", "parse_run_id", "structure_node_id"),
    )
    source_trace_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_trace_refs.source_trace_ref_id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False
    )
    parse_run_id: Mapped[str] = mapped_column(
        ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), nullable=False
    )
    structure_node_id: Mapped[str] = mapped_column(
        ForeignKey("canonical_document_nodes.structure_node_id", ondelete="CASCADE"), nullable=False
    )
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    table_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_text_hash: Mapped[str] = mapped_column(String(128), nullable=False)


class CanonicalStructureNodeEntity(TenantAuditMixin, Base):
    __tablename__ = "canonical_document_nodes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "parse_run_id", "structure_node_id", name="uq_canonical_node_run"),
        Index("ix_canonical_node_locator", "tenant_id", "parse_run_id", "page_no", "sheet_name", "slide_no"),
    )
    structure_node_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parse_run_id: Mapped[str] = mapped_column(ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=False)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_node_id: Mapped[str | None] = mapped_column(ForeignKey("canonical_document_nodes.structure_node_id", ondelete="CASCADE"), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bbox_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_locator_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    parser_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class DocumentParseQualityEntity(TenantAuditMixin, Base):
    __tablename__ = "document_parse_quality_results"
    __table_args__ = (UniqueConstraint("tenant_id", "parse_run_id", name="uq_parse_quality_run"),)
    quality_result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parse_run_id: Mapped[str] = mapped_column(ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), nullable=False)
    text_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    page_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    table_extraction_quality: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    layout_quality: Mapped[float] = mapped_column(Float, nullable=False)
    structural_completeness: Mapped[float] = mapped_column(Float, nullable=False)
    language_detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)


class DocumentParseTaskEntity(TenantAuditMixin, Base):
    __tablename__ = "document_parse_tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_version_id", "idempotency_key", name="uq_parse_task_idempotency"),
        Index("ix_parse_task_status", "tenant_id", "status", "created_at"),
    )
    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=False)
    parser_profile_id: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)


class BusinessFactCandidateEntity(TenantAuditMixin, Base):
    __tablename__ = "business_fact_candidates"
    fact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parse_run_id: Mapped[str] = mapped_column(ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), nullable=False)
    fact_type: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    original_value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    conflict_status: Mapped[str] = mapped_column(String(40), nullable=False)


class CandidateDataItemEntity(TenantAuditMixin, Base):
    __tablename__ = "candidate_data_items"
    __table_args__ = (Index("ix_candidate_item_parse_name", "tenant_id", "parse_run_id", "normalized_name"),)
    candidate_data_item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parse_run_id: Mapped[str] = mapped_column(ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), nullable=False)
    raw_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity_metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    system_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class CandidateDataFlowNodeEntity(TenantAuditMixin, Base):
    __tablename__ = "candidate_data_flow_nodes"
    candidate_node_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parse_run_id: Mapped[str] = mapped_column(ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    node_type_candidate: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_candidate: Mapped[str | None] = mapped_column(String(255), nullable=True)
    party_candidate: Mapped[str | None] = mapped_column(String(255), nullable=True)
    system_candidate: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class CandidateDataFlowEdgeEntity(TenantAuditMixin, Base):
    __tablename__ = "candidate_data_flow_edges"
    candidate_edge_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parse_run_id: Mapped[str] = mapped_column(ForeignKey("document_parse_runs.document_parse_run_id", ondelete="CASCADE"), nullable=False)
    source_candidate_node_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_flow_nodes.candidate_node_id", ondelete="CASCADE"), nullable=False)
    target_candidate_node_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_flow_nodes.candidate_node_id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transfer_type_candidate: Mapped[str | None] = mapped_column(String(160), nullable=True)
    data_item_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class CrossDocumentLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "cross_document_links"
    cross_document_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(100), nullable=False)
    left_object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    left_object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    right_object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    right_object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class _SourceLinkMixin:
    source_trace_ref_id: Mapped[str] = mapped_column(ForeignKey("source_trace_refs.source_trace_ref_id", ondelete="CASCADE"), nullable=False)


class BusinessFactSourceLinkEntity(_SourceLinkMixin, TenantAuditMixin, Base):
    __tablename__ = "business_fact_source_links"
    __table_args__ = (UniqueConstraint("tenant_id", "fact_id", "source_trace_ref_id", name="uq_fact_source_link"),)
    business_fact_source_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("business_fact_candidates.fact_id", ondelete="CASCADE"), nullable=False)


class CandidateDataItemSourceLinkEntity(_SourceLinkMixin, TenantAuditMixin, Base):
    __tablename__ = "candidate_data_item_source_links"
    __table_args__ = (UniqueConstraint("tenant_id", "candidate_data_item_id", "source_trace_ref_id", name="uq_candidate_item_source_link"),)
    candidate_data_item_source_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_data_item_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_items.candidate_data_item_id", ondelete="CASCADE"), nullable=False)


class CandidateDataFlowNodeSourceLinkEntity(_SourceLinkMixin, TenantAuditMixin, Base):
    __tablename__ = "candidate_data_flow_node_source_links"
    candidate_data_flow_node_source_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_node_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_flow_nodes.candidate_node_id", ondelete="CASCADE"), nullable=False)


class CandidateDataFlowEdgeSourceLinkEntity(_SourceLinkMixin, TenantAuditMixin, Base):
    __tablename__ = "candidate_data_flow_edge_source_links"
    candidate_data_flow_edge_source_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_edge_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_flow_edges.candidate_edge_id", ondelete="CASCADE"), nullable=False)


class CrossDocumentLinkSourceEntity(_SourceLinkMixin, TenantAuditMixin, Base):
    __tablename__ = "cross_document_link_sources"
    cross_document_link_source_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cross_document_link_id: Mapped[str] = mapped_column(ForeignKey("cross_document_links.cross_document_link_id", ondelete="CASCADE"), nullable=False)


class AnalysisSnapshotParseRunPinEntity(TenantAuditMixin, Base):
    __tablename__ = "analysis_snapshot_parse_run_pins"
    __table_args__ = (
        UniqueConstraint("tenant_id", "analysis_snapshot_id", "document_version_id", name="uq_snapshot_document_parse_pin"),
    )
    pin_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_snapshot_id: Mapped[str] = mapped_column(ForeignKey("analysis_snapshots.analysis_snapshot_id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=False)
    parse_run_id: Mapped[str] = mapped_column(ForeignKey("document_parse_runs.document_parse_run_id", ondelete="RESTRICT"), nullable=False)


class DocumentTranslationRecordEntity(TenantAuditMixin, Base):
    __tablename__ = "document_translation_records"
    translation_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    structure_node_id: Mapped[str] = mapped_column(ForeignKey("canonical_document_nodes.structure_node_id", ondelete="CASCADE"), nullable=False)
    source_language: Mapped[str] = mapped_column(String(40), nullable=False)
    target_language: Mapped[str] = mapped_column(String(40), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    translation_model_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    translation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at_provider: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
