from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TenantAuditMixin:
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class EffectiveMixin:
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class TenantEntity(Base):
    __tablename__ = "tenants"
    tenant_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class OrganizationEntity(TenantAuditMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_organizations_tenant_name"),)
    organization_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class ProjectEntity(TenantAuditMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_projects_tenant_name"),
        Index("ix_projects_tenant_status", "tenant_id", "status"),
    )
    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.organization_id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "project_versions.project_version_id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_projects_active_version",
        ),
        nullable=True,
    )


class ProjectVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "version_no", name="uq_project_versions_number"),
        CheckConstraint("version_no >= 1", name="ck_project_versions_number"),
    )
    project_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    intake_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class JurisdictionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "jurisdictions"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_jurisdiction_code"),)
    jurisdiction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class JurisdictionRelationEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "jurisdiction_relations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_jurisdiction_id", "target_jurisdiction_id", "relation_type",
            name="uq_jurisdiction_relation"
        ),
    )
    jurisdiction_relation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="CASCADE"), nullable=False
    )
    target_jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False)


class LegalEntityEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "legal_entities"
    __table_args__ = (UniqueConstraint("tenant_id", "legal_name", name="uq_legal_entity_name"),)
    legal_entity_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(250), nullable=False)
    registration_jurisdiction_id: Mapped[str | None] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="SET NULL"), nullable=True
    )


class ProjectPartyEntity(TenantAuditMixin, Base):
    __tablename__ = "project_parties"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "display_name", name="uq_project_party_display"),
    )
    project_party_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    legal_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("legal_entities.legal_entity_id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)


class PartyRoleAssignmentEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "party_role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "project_party_id", "role_code", "jurisdiction_id",
            name="uq_party_role_assignment"
        ),
    )
    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_party_id: Mapped[str] = mapped_column(
        ForeignKey("project_parties.project_party_id", ondelete="CASCADE"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(String(100), nullable=False)
    jurisdiction_id: Mapped[str | None] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="SET NULL"), nullable=True
    )


class ContractEntity(TenantAuditMixin, Base):
    __tablename__ = "contracts"
    contract_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    contract_ref: Mapped[str] = mapped_column(String(200), nullable=False)


class ContractPartyLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "contract_party_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_id", "project_party_id", name="uq_contract_party_link"),
    )
    contract_party_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.contract_id", ondelete="CASCADE"), nullable=False)
    project_party_id: Mapped[str] = mapped_column(
        ForeignKey("project_parties.project_party_id", ondelete="CASCADE"), nullable=False
    )
    relationship_code: Mapped[str] = mapped_column(String(100), nullable=False)


class DocumentEntity(TenantAuditMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "name", name="uq_document_name"),)
    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, default="UNKNOWN", server_default="UNKNOWN")
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "document_versions.document_version_id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_documents_active_version",
        ),
        nullable=True,
    )


class DocumentVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_id", "version_no", name="uq_document_versions_number"),
        UniqueConstraint("tenant_id", "content_hash", name="uq_document_content_hash"),
        CheckConstraint("version_no >= 1", name="ck_document_versions_number"),
    )
    document_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)


class SourceTraceRefEntity(TenantAuditMixin, Base):
    __tablename__ = "source_trace_refs"
    __table_args__ = (
        Index("ix_source_trace_document_locator", "tenant_id", "document_version_id", "page_no"),
    )
    source_trace_ref_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=False
    )
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    table_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bbox_json: Mapped[list | None] = mapped_column(JSON, nullable=True)


class DocumentParseRunEntity(TenantAuditMixin, Base):
    __tablename__ = "document_parse_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_version_id", "parser_version", name="uq_document_parse_version"),
    )
    document_parse_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=False
    )
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    result_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DataItemEntity(TenantAuditMixin, Base):
    __tablename__ = "data_items"
    __table_args__ = (
        Index("ix_data_items_project", "tenant_id", "project_id"),
        UniqueConstraint("tenant_id", "project_id", "name", name="uq_data_item_name"),
    )
    data_item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_type_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.document_version_id", ondelete="SET NULL"), nullable=True
    )
    source_trace_ref_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_trace_refs.source_trace_ref_id", ondelete="SET NULL"), nullable=True
    )


class DataItemGroupEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "name", name="uq_data_item_group_name"),)
    data_item_group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grouping_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataItemGroupMemberEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_group_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_item_group_id", "data_item_id", name="uq_data_item_group_member"),
    )
    data_item_group_member_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data_item_group_id: Mapped[str] = mapped_column(
        ForeignKey("data_item_groups.data_item_group_id", ondelete="CASCADE"), nullable=False
    )
    data_item_id: Mapped[str] = mapped_column(ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False)


class DataFlowNodeEntity(TenantAuditMixin, Base):
    __tablename__ = "data_flow_nodes"
    flow_node_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    node_type: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction_id: Mapped[str | None] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="SET NULL"), nullable=True
    )


class DataFlowEdgeEntity(TenantAuditMixin, Base):
    __tablename__ = "data_flow_edges"
    __table_args__ = (
        CheckConstraint("source_node_id <> target_node_id", name="ck_data_flow_edge_distinct_nodes"),
        Index("ix_data_flow_edges_project", "tenant_id", "project_id"),
    )
    flow_edge_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("data_flow_nodes.flow_node_id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("data_flow_nodes.flow_node_id", ondelete="CASCADE"), nullable=False
    )
    flow_type: Mapped[str] = mapped_column(String(100), nullable=False)
    route_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    declared_cross_border: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class DataItemFlowLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_flow_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_item_id", "flow_edge_id", name="uq_data_item_flow_link"),
    )
    link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data_item_id: Mapped[str] = mapped_column(ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False)
    flow_edge_id: Mapped[str] = mapped_column(
        ForeignKey("data_flow_edges.flow_edge_id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    volume_band: Mapped[str | None] = mapped_column(String(80), nullable=True)


class DataItemProductLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "data_item_product_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_item_id", "product_ref", name="uq_data_item_product_link"),
    )
    data_item_product_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data_item_id: Mapped[str] = mapped_column(ForeignKey("data_items.data_item_id", ondelete="CASCADE"), nullable=False)
    product_ref: Mapped[str] = mapped_column(String(200), nullable=False)


class DataFlowPartyLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "data_flow_party_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "flow_node_id", "project_party_id", "role_code", name="uq_data_flow_party_link"),
    )
    data_flow_party_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    flow_node_id: Mapped[str] = mapped_column(
        ForeignKey("data_flow_nodes.flow_node_id", ondelete="CASCADE"), nullable=False
    )
    project_party_id: Mapped[str] = mapped_column(
        ForeignKey("project_parties.project_party_id", ondelete="CASCADE"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(String(100), nullable=False)


class CompliancePathStepEntity(TenantAuditMixin, Base):
    __tablename__ = "compliance_path_steps"
    compliance_path_step_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)


class PathStepResponsiblePartyEntity(TenantAuditMixin, Base):
    __tablename__ = "path_step_responsible_parties"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "compliance_path_step_id", "project_party_id",
            name="uq_path_step_responsible_party"
        ),
    )
    path_step_responsible_party_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    compliance_path_step_id: Mapped[str] = mapped_column(
        ForeignKey("compliance_path_steps.compliance_path_step_id", ondelete="CASCADE"), nullable=False
    )
    project_party_id: Mapped[str] = mapped_column(
        ForeignKey("project_parties.project_party_id", ondelete="CASCADE"), nullable=False
    )


class ClassificationSchemeEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "classification_schemes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", "record_version", name="uq_classification_scheme_version"),
    )
    scheme_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class ClassificationCategoryEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "classification_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scheme_id", "code", name="uq_classification_category"),
    )
    category_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheme_id: Mapped[str] = mapped_column(
        ForeignKey("classification_schemes.scheme_id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class ClassificationLevelEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "classification_levels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scheme_id", "code", name="uq_classification_level"),
    )
    level_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheme_id: Mapped[str] = mapped_column(
        ForeignKey("classification_schemes.scheme_id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)


class ClassificationResultEntity(TenantAuditMixin, Base):
    __tablename__ = "classification_results"
    __table_args__ = (
        Index("ix_classification_results_subject", "tenant_id", "subject_type", "subject_id"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_classification_confidence"),
    )
    classification_result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    scheme_id: Mapped[str] = mapped_column(
        ForeignKey("classification_schemes.scheme_id", ondelete="RESTRICT"), nullable=False
    )
    scheme_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    level_id: Mapped[str | None] = mapped_column(
        ForeignKey("classification_levels.level_id", ondelete="SET NULL"), nullable=True
    )
    jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="RESTRICT"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
    analysis_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_snapshots.analysis_snapshot_id"), nullable=True)
    formal_provenance_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ClassificationResultCategoryEntity(TenantAuditMixin, Base):
    __tablename__ = "classification_result_categories"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "classification_result_id", "category_id",
            name="uq_classification_result_category"
        ),
    )
    classification_result_category_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    classification_result_id: Mapped[str] = mapped_column(
        ForeignKey("classification_results.classification_result_id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[str] = mapped_column(
        ForeignKey("classification_categories.category_id", ondelete="RESTRICT"), nullable=False
    )


class EvidenceReferenceEntity(TenantAuditMixin, Base):
    __tablename__ = "evidence_references"
    __table_args__ = (
        Index("ix_evidence_source", "tenant_id", "source_ref"),
    )
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    source_trace_ref_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_trace_refs.source_trace_ref_id", ondelete="SET NULL"), nullable=True
    )
    excerpt_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False, default="UNVALIDATED", server_default="UNVALIDATED")


class CitationEntity(TenantAuditMixin, Base):
    __tablename__ = "citations"
    citation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_references.evidence_id", ondelete="CASCADE"), nullable=False
    )
    locator: Mapped[str] = mapped_column(String(500), nullable=False)
    quote_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RegulatoryStructureNodeEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "regulatory_structure_nodes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "regulation_version_ref", "node_path", name="uq_regulatory_structure_node"),
    )
    regulatory_structure_node_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="RESTRICT"), nullable=False
    )
    regulation_version_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False)
    node_path: Mapped[str] = mapped_column(String(500), nullable=False)
    official_source: Mapped[str] = mapped_column(String(500), nullable=False)


class RuleHitEntity(TenantAuditMixin, Base):
    __tablename__ = "rule_hits"
    rule_hit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_version_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    formal_provenance_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class LegalBasisItemEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "legal_basis_items"
    __table_args__ = (
        Index("ix_legal_basis_jurisdiction", "tenant_id", "jurisdiction_id"),
    )
    legal_basis_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="RESTRICT"), nullable=False
    )
    regulatory_structure_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("regulatory_structure_nodes.regulatory_structure_node_id", ondelete="SET NULL"), nullable=True
    )
    legal_basis_summary: Mapped[str] = mapped_column(Text, nullable=False)
    applicability_reason: Mapped[str] = mapped_column(Text, nullable=False)
    official_source: Mapped[str] = mapped_column(String(500), nullable=False)
    citation_locator: Mapped[str] = mapped_column(String(500), nullable=False)


class LegalBasisRuleHitLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "legal_basis_rule_hit_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "legal_basis_id", "rule_hit_id", name="uq_legal_basis_rule_hit"),
    )
    legal_basis_rule_hit_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    legal_basis_id: Mapped[str] = mapped_column(
        ForeignKey("legal_basis_items.legal_basis_id", ondelete="CASCADE"), nullable=False
    )
    rule_hit_id: Mapped[str] = mapped_column(ForeignKey("rule_hits.rule_hit_id", ondelete="CASCADE"), nullable=False)


class LegalBasisEvidenceLinkEntity(TenantAuditMixin, Base):
    __tablename__ = "legal_basis_evidence_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "legal_basis_id", "evidence_id", name="uq_legal_basis_evidence"),
    )
    legal_basis_evidence_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    legal_basis_id: Mapped[str] = mapped_column(
        ForeignKey("legal_basis_items.legal_basis_id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_references.evidence_id", ondelete="CASCADE"), nullable=False
    )


class AnalysisSnapshotEntity(Base):
    __tablename__ = "analysis_snapshots"
    analysis_snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_version: Mapped[str] = mapped_column(String(50), nullable=False)
    analysis_as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class WorkflowRunEntity(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (Index("ix_workflow_runs_tenant_status", "tenant_id", "status"),)
    workflow_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    analysis_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_snapshots.analysis_snapshot_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    graph_definition_version: Mapped[str] = mapped_column(String(50), nullable=False)
    langgraph_runtime_version: Mapped[str] = mapped_column(String(50), nullable=False)
    checkpointer_version: Mapped[str] = mapped_column(String(50), nullable=False)
    state_schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class WorkflowNodeRunEntity(Base):
    __tablename__ = "workflow_node_runs"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "node_code", "attempt_no", name="uq_workflow_node_attempt"),
    )
    workflow_node_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    node_code: Mapped[str] = mapped_column(String(120), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AnalysisStageResultEntity(TenantAuditMixin, Base):
    __tablename__ = "analysis_stage_results"
    __table_args__ = (
        UniqueConstraint("tenant_id", "workflow_run_id", "stage_code", name="uq_analysis_stage_result"),
    )
    analysis_stage_result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"), nullable=False
    )
    stage_code: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class ReviewTaskEntity(Base):
    __tablename__ = "review_tasks"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_review_idempotency"),)
    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    decision_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewDecisionEntity(TenantAuditMixin, Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "review_id", "decision_id", name="uq_review_decision"),
    )
    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("review_tasks.review_id", ondelete="CASCADE"), nullable=False)
    decision_code: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(200), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkflowEventEntity(Base):
    __tablename__ = "workflow_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    node_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditEventEntity(Base):
    __tablename__ = "audit_events"
    audit_event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workflow_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    analysis_snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ExecutionIdempotencyEntity(Base):
    __tablename__ = "execution_idempotency_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scope", "idempotency_key", name="uq_execution_idempotency"),
    )
    execution_idempotency_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    result_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ApiIdempotencyEntity(Base):
    __tablename__ = "api_idempotency_records"
    __table_args__ = (UniqueConstraint("api_client_id", "idempotency_key", name="uq_api_idempotency"),)
    api_idempotency_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    api_client_id: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChannelContextEntity(TenantAuditMixin, Base):
    __tablename__ = "channel_contexts"
    channel_context_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel_type: Mapped[str] = mapped_column(String(40), nullable=False)
    channel_instance_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_id: Mapped[str] = mapped_column(String(200), nullable=False)
    locale: Mapped[str | None] = mapped_column(String(40), nullable=True)


class InteractionSessionEntity(TenantAuditMixin, Base):
    __tablename__ = "interaction_sessions"
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel_context_id: Mapped[str] = mapped_column(
        ForeignKey("channel_contexts.channel_context_id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationThreadEntity(TenantAuditMixin, Base):
    __tablename__ = "conversation_threads"
    conversation_thread_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interaction_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ConversationMessageEntity(TenantAuditMixin, Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ix_conversation_messages_thread_time", "tenant_id", "conversation_thread_id", "created_at"),
    )
    message_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_thread_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_threads.conversation_thread_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    analysis_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
