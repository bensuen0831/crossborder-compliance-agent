from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin


class BusinessFactEntity(TenantAuditMixin, Base):
    __tablename__ = "business_facts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "fact_type", "version", "normalized_key", name="uq_business_fact_version"),
        Index("ix_business_fact_project_type", "tenant_id", "project_id", "fact_type"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_business_fact_confidence"),
    )
    fact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    fact_type: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    original_values_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_document_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    resolution_method: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    conflict_status: Mapped[str] = mapped_column(String(40), nullable=False, default="NONE")
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    structured_provenance_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )


class BusinessFactResolutionEntity(TenantAuditMixin, Base):
    __tablename__ = "business_fact_resolutions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_fact_id", "version", name="uq_business_fact_resolution_candidate_version"),
    )
    resolution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_fact_id: Mapped[str] = mapped_column(ForeignKey("business_fact_candidates.fact_id", ondelete="CASCADE"), nullable=False)
    business_fact_id: Mapped[str | None] = mapped_column(ForeignKey("business_facts.fact_id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reviewer_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class CandidateResolutionEntity(TenantAuditMixin, Base):
    __tablename__ = "candidate_resolutions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_type", "candidate_id", "version", name="uq_candidate_resolution_version"),
        Index("ix_candidate_resolution_formal", "tenant_id", "formal_object_type", "formal_object_id"),
    )
    resolution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    formal_object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    formal_object_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    resolution_reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reviewer_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_type: Mapped[str] = mapped_column(String(80), nullable=False, default="POLICY")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ContextConflictEntity(TenantAuditMixin, Base):
    __tablename__ = "context_conflicts"
    __table_args__ = (
        Index("ix_context_conflict_project_status", "tenant_id", "project_id", "resolution_status"),
    )
    conflict_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    object_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(40), nullable=False, default="OPEN")
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    resolution_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ProductContextCandidateEntity(TenantAuditMixin, Base):
    __tablename__ = "product_context_candidates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "project_id", "dimension_type", "definition_id", "source", "version",
            name="uq_product_context_candidate_version",
        ),
    )
    product_context_candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    dimension_type: Mapped[str] = mapped_column(String(40), nullable=False)
    definition_id: Mapped[str] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ProductContextEntity(TenantAuditMixin, Base):
    __tablename__ = "product_contexts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "version", name="uq_product_context_project_version"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_product_context_confidence"),
    )
    product_context_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    effective_scope_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    resolution_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ProductContextDefinitionLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "product_context_definition_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_context_id", "dimension_type", "definition_id", name="uq_product_context_definition"),
    )
    product_context_definition_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_context_id: Mapped[str] = mapped_column(ForeignKey("product_contexts.product_context_id", ondelete="CASCADE"), nullable=False)
    dimension_type: Mapped[str] = mapped_column(String(40), nullable=False)
    definition_id: Mapped[str] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=False)


class ProductScopeResolutionEntity(TenantAuditMixin, Base):
    __tablename__ = "product_scope_resolutions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "version", name="uq_product_scope_resolution_version"),
    )
    product_scope_resolution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    selected_product_scope_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    detected_product_context_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    effective_product_scope_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    conflict_id: Mapped[str | None] = mapped_column(ForeignKey("context_conflicts.conflict_id", ondelete="SET NULL"), nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ScenarioContextEntity(TenantAuditMixin, Base):
    __tablename__ = "scenario_contexts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "scenario_definition_id", "version", name="uq_scenario_context_version"),
    )
    scenario_context_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    scenario_definition_id: Mapped[str | None] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ScenarioResolutionEntity(TenantAuditMixin, Base):
    __tablename__ = "scenario_resolutions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "project_id", "scenario_definition_id", "source", "version",
            name="uq_scenario_resolution_version",
        ),
    )
    scenario_resolution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    scenario_definition_id: Mapped[str] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class SystemContextEntity(TenantAuditMixin, Base):
    __tablename__ = "system_contexts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "display_name", "version", name="uq_system_context_version"),
    )
    system_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)
    system_type_ref: Mapped[str | None] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True)
    product_context_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    party_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    location_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DeviceContextEntity(TenantAuditMixin, Base):
    __tablename__ = "device_contexts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "display_name", "version", name="uq_device_context_version"),
    )
    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)
    device_type_ref: Mapped[str | None] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True)
    system_id: Mapped[str | None] = mapped_column(ForeignKey("system_contexts.system_id", ondelete="SET NULL"), nullable=True)
    product_context_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class SystemRelationEntity(TenantAuditMixin, Base):
    __tablename__ = "system_relations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system_id", "target_system_id", "relation_type", name="uq_system_relation"),
    )
    system_relation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_system_id: Mapped[str] = mapped_column(ForeignKey("system_contexts.system_id", ondelete="CASCADE"), nullable=False)
    target_system_id: Mapped[str] = mapped_column(ForeignKey("system_contexts.system_id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(120), nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class PartyCandidateEntity(TenantAuditMixin, Base):
    __tablename__ = "party_candidates"
    party_candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)
    role_definition_id: Mapped[str | None] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class PartyResolutionEntity(TenantAuditMixin, Base):
    __tablename__ = "party_resolutions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "party_candidate_id", "version", name="uq_party_resolution_version"),
    )
    party_resolution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    party_candidate_id: Mapped[str] = mapped_column(ForeignKey("party_candidates.party_candidate_id", ondelete="CASCADE"), nullable=False)
    project_party_id: Mapped[str | None] = mapped_column(ForeignKey("project_parties.project_party_id", ondelete="SET NULL"), nullable=True)
    legal_entity_id: Mapped[str | None] = mapped_column(ForeignKey("legal_entities.legal_entity_id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DataItemResolutionDetailEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_resolution_details"
    __table_args__ = (UniqueConstraint("tenant_id", "data_item_id", "version", name="uq_data_item_detail_version"),)
    detail_version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    data_item_id: Mapped[str] = mapped_column(ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    format: Mapped[str | None] = mapped_column(String(160), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(120), nullable=True)
    frequency_quantity_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    system_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    device_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DataItemCandidateLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_candidate_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_item_id", "data_inventory_version", "candidate_data_item_id", name="uq_data_item_candidate_link"),
    )
    data_item_candidate_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data_item_id: Mapped[str] = mapped_column(ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False)
    candidate_data_item_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_items.candidate_data_item_id", ondelete="CASCADE"), nullable=False)

    data_inventory_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DataItemSourceTraceLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_source_trace_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_item_id", "data_inventory_version", "source_trace_ref_id", name="uq_data_item_source_trace_link"),
    )
    data_item_source_trace_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data_item_id: Mapped[str] = mapped_column(ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False)
    source_trace_ref_id: Mapped[str] = mapped_column(ForeignKey("source_trace_refs.source_trace_ref_id", ondelete="RESTRICT"), nullable=False)

    data_inventory_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DataItemDeduplicationResultEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_deduplication_results"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "left_candidate_id", "right_candidate_id", "version", name="uq_data_item_dedup_version"),
    )
    deduplication_result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    left_candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_items.candidate_data_item_id", ondelete="CASCADE"), nullable=False)
    right_candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_data_items.candidate_data_item_id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    deterministic_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    reviewer_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DataItemProductLinkDetailEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_product_link_details"
    __table_args__ = (UniqueConstraint("tenant_id", "data_item_product_link_id", "data_inventory_version", name="uq_data_item_product_detail_version"),)
    detail_version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    data_item_product_link_id: Mapped[str] = mapped_column(ForeignKey("data_item_product_links.data_item_product_link_id", ondelete="CASCADE"), nullable=False)
    data_inventory_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_domain_definition_id: Mapped[str | None] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True)
    product_definition_id: Mapped[str | None] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class JurisdictionContextEntity(TenantAuditMixin, Base):
    __tablename__ = "jurisdiction_contexts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "context_type", "jurisdiction_id", "version", name="uq_jurisdiction_context_version"),
    )
    jurisdiction_context_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    jurisdiction_id: Mapped[str | None] = mapped_column(ForeignKey("jurisdictions.jurisdiction_id", ondelete="RESTRICT"), nullable=True)
    context_type: Mapped[str] = mapped_column(String(80), nullable=False)
    location_precision: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class JurisdictionResolutionEntity(TenantAuditMixin, Base):
    __tablename__ = "jurisdiction_resolutions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "input_value", "version", name="uq_jurisdiction_resolution_version"),
    )
    jurisdiction_resolution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    input_value: Mapped[str] = mapped_column(String(250), nullable=False)
    jurisdiction_context_id: Mapped[str | None] = mapped_column(ForeignKey("jurisdiction_contexts.jurisdiction_context_id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DataFlowNodeDetailEntity(TenantAuditMixin, Base):
    __tablename__ = "data_flow_node_details"
    flow_node_id: Mapped[str] = mapped_column(ForeignKey("data_flow_nodes.flow_node_id", ondelete="CASCADE"), primary_key=True)
    system_id: Mapped[str | None] = mapped_column(ForeignKey("system_contexts.system_id", ondelete="SET NULL"), nullable=True)
    party_id: Mapped[str | None] = mapped_column(ForeignKey("project_parties.project_party_id", ondelete="SET NULL"), nullable=True)
    jurisdiction_context_id: Mapped[str | None] = mapped_column(ForeignKey("jurisdiction_contexts.jurisdiction_context_id", ondelete="SET NULL"), nullable=True)
    storage_or_processing_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DataFlowEdgeDetailEntity(TenantAuditMixin, Base):
    __tablename__ = "data_flow_edge_details"
    flow_edge_id: Mapped[str] = mapped_column(ForeignKey("data_flow_edges.flow_edge_id", ondelete="CASCADE"), primary_key=True)
    transfer_type_definition_id: Mapped[str | None] = mapped_column(ForeignKey("metadata_definitions.definition_id", ondelete="RESTRICT"), nullable=True)
    direction: Mapped[str] = mapped_column(String(80), nullable=False)
    protocol_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    frequency_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DataItemFlowLinkDetailEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_flow_link_details"
    data_inventory_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("data_item_flow_links.link_id", ondelete="CASCADE"), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class ContextResolutionRunEntity(TenantAuditMixin, Base):
    __tablename__ = "context_resolution_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "version", name="uq_context_resolution_run_version"),
        Index("ix_context_resolution_run_project", "tenant_id", "project_id", "status"),
    )
    context_resolution_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_inventory_version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_flow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    statistics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    unresolved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    review_required_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnalysisSnapshotContextPinEntity(TenantAuditMixin, Base):
    __tablename__ = "analysis_snapshot_context_pins"
    __table_args__ = (
        UniqueConstraint("tenant_id", "analysis_snapshot_id", "project_id", name="uq_analysis_snapshot_context_pin"),
    )
    analysis_snapshot_context_pin_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_snapshot_id: Mapped[str] = mapped_column(ForeignKey("analysis_snapshots.analysis_snapshot_id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    context_resolution_run_id: Mapped[str] = mapped_column(ForeignKey("context_resolution_runs.context_resolution_run_id", ondelete="RESTRICT"), nullable=False)
    context_resolution_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_inventory_version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_flow_version: Mapped[int] = mapped_column(Integer, nullable=False)
