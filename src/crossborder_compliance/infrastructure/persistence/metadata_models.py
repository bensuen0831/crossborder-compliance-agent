from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String,
    Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import (
    Base, EffectiveMixin, TenantAuditMixin, utcnow
)


LIFECYCLE_VALUES = "'DRAFT','PENDING_REVIEW','APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED'"


class MetadataDefinitionEntity(TenantAuditMixin, Base):
    __tablename__ = "metadata_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "code", name="uq_metadata_definition_kind_code"),
        UniqueConstraint("tenant_id", "kind", "canonical_object_id", name="uq_metadata_definition_canonical_ref"),
        Index("ix_metadata_definition_kind_status", "tenant_id", "kind", "status"),
    )
    definition_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)
    canonical_object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    canonical_object_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parent_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("metadata_definitions.definition_id", ondelete="SET NULL"), nullable=True
    )
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("metadata_versions.version_id", ondelete="SET NULL", use_alter=True, name="fk_metadata_definition_active_version"),
        nullable=True,
    )


class MetadataVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "metadata_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "definition_id", "version_no", name="uq_metadata_version_number"),
        CheckConstraint("version_no >= 1", name="ck_metadata_version_number"),
        CheckConstraint(
            f"lifecycle_status IN ({LIFECYCLE_VALUES})", name="ck_metadata_version_lifecycle"
        ),
        Index("ix_metadata_version_runtime", "tenant_id", "definition_id", "lifecycle_status"),
    )
    version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    definition_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MetadataBindingEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "metadata_bindings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "binding_type", "source_definition_id", "target_definition_id",
            name="uq_metadata_binding"
        ),
        Index("ix_metadata_binding_source", "tenant_id", "source_definition_id", "binding_type"),
    )
    binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    binding_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_definition_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=False
    )
    target_definition_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=False
    )
    scope_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ClassificationSchemeVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "classification_scheme_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scheme_id", "version_no", name="uq_classification_scheme_versions_scheme_no_record"),
        CheckConstraint("version_no >= 1", name="ck_classification_scheme_version_number"),
        CheckConstraint(
            f"lifecycle_status IN ({LIFECYCLE_VALUES})", name="ck_classification_scheme_version_lifecycle"
        ),
        Index("ix_classification_scheme_version_runtime", "tenant_id", "scheme_id", "lifecycle_status"),
    )
    scheme_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheme_id: Mapped[str] = mapped_column(
        ForeignKey("classification_schemes.scheme_id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    applicability_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ClassificationBindingEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "classification_bindings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scheme_version_id", "jurisdiction_id", "industry_ref",
            "scenario_definition_id", name="uq_classification_binding_scope"
        ),
        Index("ix_classification_binding_resolve", "tenant_id", "jurisdiction_id", "priority"),
    )
    classification_binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheme_version_id: Mapped[str] = mapped_column(
        ForeignKey("classification_scheme_versions.scheme_version_id", ondelete="CASCADE"),
        nullable=False
    )
    jurisdiction_id: Mapped[str | None] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="CASCADE"), nullable=True
    )
    industry_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    scenario_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)


class ClassificationApplicabilityMetadataEntity(TenantAuditMixin, Base):
    __tablename__ = "classification_applicability_metadata"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scheme_version_id", name="uq_classification_applicability_version"),
    )
    classification_applicability_metadata_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheme_version_id: Mapped[str] = mapped_column(
        ForeignKey("classification_scheme_versions.scheme_version_id", ondelete="CASCADE"),
        nullable=False
    )
    applicability_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ModelProviderEntity(TenantAuditMixin, Base):
    __tablename__ = "model_providers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_model_provider_code"),
        Index("ix_model_provider_enabled", "tenant_id", "enabled", "status"),
    )
    provider_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_provider_versions.provider_version_id", ondelete="SET NULL", use_alter=True, name="fk_model_provider_active_version"),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModelProviderVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "model_provider_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_id", "version_no", name="uq_model_provider_version"),
        CheckConstraint("version_no >= 1", name="ck_model_provider_version_number"),
        CheckConstraint(
            f"lifecycle_status IN ({LIFECYCLE_VALUES})", name="ck_model_provider_version_lifecycle"
        ),
    )
    provider_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("model_providers.provider_id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    base_url_ref: Mapped[str | None] = mapped_column(String(400), nullable=True)
    endpoint_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auth_type: Mapped[str] = mapped_column(String(80), nullable=False, default="NONE")
    secret_ref: Mapped[str | None] = mapped_column(String(400), nullable=True)
    deployment_type: Mapped[str] = mapped_column(String(80), nullable=False, default="API")
    trust_level: Mapped[str] = mapped_column(String(80), nullable=False, default="UNSPECIFIED")
    data_boundary: Mapped[str] = mapped_column(String(160), nullable=False, default="UNSPECIFIED")
    timeout_policy_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    retry_policy_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    cost_metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModelDefinitionEntity(TenantAuditMixin, Base):
    __tablename__ = "model_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_id", "model_id", name="uq_model_definition_provider_model"),
        Index("ix_model_definition_enabled", "tenant_id", "enabled", "status"),
    )
    model_definition_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("model_providers.provider_id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_deployment_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_deployments.model_deployment_id", ondelete="SET NULL", use_alter=True, name="fk_model_definition_active_deployment"),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModelDeploymentEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "model_deployments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "model_definition_id", "deployment_ref",
            name="uq_model_deployment_ref"
        ),
        CheckConstraint(
            f"lifecycle_status IN ({LIFECYCLE_VALUES})", name="ck_model_deployment_lifecycle"
        ),
    )
    model_deployment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_definition_id: Mapped[str] = mapped_column(
        ForeignKey("model_definitions.model_definition_id", ondelete="CASCADE"), nullable=False
    )
    provider_version_id: Mapped[str] = mapped_column(
        ForeignKey("model_provider_versions.provider_version_id", ondelete="RESTRICT"), nullable=False
    )
    deployment_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")


class ModelCapabilityEntity(TenantAuditMixin, Base):
    __tablename__ = "model_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "model_definition_id", "capability",
            name="uq_model_capability"
        ),
        Index("ix_model_capability_resolve", "tenant_id", "capability", "status"),
    )
    model_capability_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_definition_id: Mapped[str] = mapped_column(
        ForeignKey("model_definitions.model_definition_id", ondelete="CASCADE"), nullable=False
    )
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ModelRoutingProfileEntity(TenantAuditMixin, Base):
    __tablename__ = "model_routing_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_model_routing_profile_code"),)
    routing_profile_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    required_capabilities_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModelHealthMetadataEntity(TenantAuditMixin, Base):
    __tablename__ = "model_health_metadata"
    __table_args__ = (Index("ix_model_health_latest", "tenant_id", "model_deployment_id", "observed_at"),)
    model_health_metadata_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_deployment_id: Mapped[str] = mapped_column(
        ForeignKey("model_deployments.model_deployment_id", ondelete="CASCADE"), nullable=False
    )
    health_status: Mapped[str] = mapped_column(String(80), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PromptDefinitionEntity(TenantAuditMixin, Base):
    __tablename__ = "prompt_definitions"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_prompt_definition_code"),)
    prompt_definition_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_versions.prompt_version_id", ondelete="SET NULL", use_alter=True, name="fk_prompt_definition_active_version"),
        nullable=True,
    )


class PromptVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "prompt_definition_id", "version_no", name="uq_prompt_version"),
        CheckConstraint("version_no >= 1", name="ck_prompt_version_number"),
        CheckConstraint(f"lifecycle_status IN ({LIFECYCLE_VALUES})", name="ck_prompt_version_lifecycle"),
    )
    prompt_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_definition_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_definitions.prompt_definition_id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    capability_requirement_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class PromptBindingEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "prompt_bindings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "prompt_version_id", "binding_type", "binding_ref",
            name="uq_prompt_binding"
        ),
    )
    prompt_binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_version_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_versions.prompt_version_id", ondelete="CASCADE"), nullable=False
    )
    binding_type: Mapped[str] = mapped_column(String(80), nullable=False)
    binding_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    scenario_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("metadata_definitions.definition_id", ondelete="SET NULL"), nullable=True
    )
    jurisdiction_id: Mapped[str | None] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="SET NULL"), nullable=True
    )
    language_code: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PromptVariableSchemaEntity(TenantAuditMixin, Base):
    __tablename__ = "prompt_variable_schemas"
    __table_args__ = (UniqueConstraint("tenant_id", "prompt_version_id", name="uq_prompt_variable_schema"),)
    prompt_variable_schema_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_version_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_versions.prompt_version_id", ondelete="CASCADE"), nullable=False
    )
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PromptReviewEntity(TenantAuditMixin, Base):
    __tablename__ = "prompt_reviews"
    prompt_review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_version_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_versions.prompt_version_id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromptPublishRecordEntity(TenantAuditMixin, Base):
    __tablename__ = "prompt_publish_records"
    prompt_publish_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_version_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_versions.prompt_version_id", ondelete="RESTRICT"), nullable=False
    )
    published_by: Mapped[str] = mapped_column(String(160), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class RuleDefinitionEntity(TenantAuditMixin, Base):
    __tablename__ = "rule_definitions"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_rule_definition_code"),)
    rule_definition_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.rule_version_id", ondelete="SET NULL", use_alter=True, name="fk_rule_definition_active_version"),
        nullable=True,
    )


class RuleVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "rule_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_definition_id", "version_no", name="uq_rule_version"),
        CheckConstraint("version_no >= 1", name="ck_rule_version_number"),
        CheckConstraint(f"lifecycle_status IN ({LIFECYCLE_VALUES})", name="ck_rule_version_lifecycle"),
    )
    rule_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_definition_id: Mapped[str] = mapped_column(
        ForeignKey("rule_definitions.rule_definition_id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    safe_dsl_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scope_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    runtime_contract_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    governance_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class RuleBindingEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "rule_bindings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_version_id", "binding_type", "binding_ref", name="uq_rule_binding"),
    )
    rule_binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_version_id: Mapped[str] = mapped_column(
        ForeignKey("rule_versions.rule_version_id", ondelete="CASCADE"), nullable=False
    )
    binding_type: Mapped[str] = mapped_column(String(80), nullable=False)
    binding_ref: Mapped[str] = mapped_column(String(200), nullable=False)


class RuleTestCaseEntity(TenantAuditMixin, Base):
    __tablename__ = "rule_test_cases"
    rule_test_case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_version_id: Mapped[str] = mapped_column(
        ForeignKey("rule_versions.rule_version_id", ondelete="CASCADE"), nullable=False
    )
    fact_context_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expected_result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class RulePublishRecordEntity(TenantAuditMixin, Base):
    __tablename__ = "rule_publish_records"
    rule_publish_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_version_id: Mapped[str] = mapped_column(
        ForeignKey("rule_versions.rule_version_id", ondelete="RESTRICT"), nullable=False
    )
    published_by: Mapped[str] = mapped_column(String(160), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TemplateDefinitionEntity(TenantAuditMixin, Base):
    __tablename__ = "template_definitions"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_template_definition_code"),)
    template_definition_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_type: Mapped[str] = mapped_column(String(80), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("template_versions.template_version_id", ondelete="SET NULL", use_alter=True, name="fk_template_definition_active_version"),
        nullable=True,
    )


class TemplateVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "template_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_definition_id", "version_no", name="uq_template_version"),
        CheckConstraint("version_no >= 1", name="ck_template_version_number"),
        CheckConstraint(f"lifecycle_status IN ({LIFECYCLE_VALUES})", name="ck_template_version_lifecycle"),
    )
    template_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_definition_id: Mapped[str] = mapped_column(
        ForeignKey("template_definitions.template_definition_id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    field_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content_ref: Mapped[str | None] = mapped_column(String(400), nullable=True)


class TemplateBindingEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "template_bindings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "template_version_id", "binding_type", "binding_ref",
            name="uq_template_binding"
        ),
    )
    template_binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_version_id: Mapped[str] = mapped_column(
        ForeignKey("template_versions.template_version_id", ondelete="CASCADE"), nullable=False
    )
    binding_type: Mapped[str] = mapped_column(String(80), nullable=False)
    binding_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)


class TemplateFieldSchemaEntity(TenantAuditMixin, Base):
    __tablename__ = "template_field_schemas"
    __table_args__ = (UniqueConstraint("tenant_id", "template_version_id", name="uq_template_field_schema"),)
    template_field_schema_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_version_id: Mapped[str] = mapped_column(
        ForeignKey("template_versions.template_version_id", ondelete="CASCADE"), nullable=False
    )
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class TemplateReviewEntity(TenantAuditMixin, Base):
    __tablename__ = "template_reviews"
    template_review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_version_id: Mapped[str] = mapped_column(
        ForeignKey("template_versions.template_version_id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)


class TemplatePublishRecordEntity(TenantAuditMixin, Base):
    __tablename__ = "template_publish_records"
    template_publish_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_version_id: Mapped[str] = mapped_column(
        ForeignKey("template_versions.template_version_id", ondelete="RESTRICT"), nullable=False
    )
    published_by: Mapped[str] = mapped_column(String(160), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class KnowledgeCollectionEntity(TenantAuditMixin, Base):
    __tablename__ = "knowledge_collections"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_knowledge_collection_code"),)
    knowledge_collection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_collection_versions.knowledge_collection_version_id", ondelete="SET NULL", use_alter=True, name="fk_knowledge_collection_active_version"),
        nullable=True,
    )


class KnowledgeCollectionVersionEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "knowledge_collection_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "knowledge_collection_id", "version_no",
            name="uq_knowledge_collection_version"
        ),
        CheckConstraint("version_no >= 1", name="ck_knowledge_collection_version_number"),
        CheckConstraint(
            f"lifecycle_status IN ({LIFECYCLE_VALUES})",
            name="ck_knowledge_collection_version_lifecycle"
        ),
    )
    knowledge_collection_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_collection_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_collections.knowledge_collection_id", ondelete="CASCADE"),
        nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class KnowledgeBindingEntity(TenantAuditMixin, EffectiveMixin, Base):
    __tablename__ = "knowledge_bindings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "knowledge_collection_version_id", "scope_type", "scope_ref",
            name="uq_knowledge_binding"
        ),
    )
    knowledge_binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_collection_version_id: Mapped[str] = mapped_column(
        ForeignKey(
            "knowledge_collection_versions.knowledge_collection_version_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    knowledge_version_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_document_versions.knowledge_version_id"))
    binding_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    dimensions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    permission_scopes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING", server_default="PENDING")


class KnowledgeScopeMetadataEntity(TenantAuditMixin, Base):
    __tablename__ = "knowledge_scope_metadata"
    knowledge_scope_metadata_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_binding_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_bindings.knowledge_binding_id", ondelete="CASCADE"), nullable=False
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class KnowledgeSourceDefinitionEntity(TenantAuditMixin, Base):
    __tablename__ = "knowledge_source_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "knowledge_collection_id", "code",
            name="uq_knowledge_source_definition"
        ),
    )
    knowledge_source_definition_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_collection_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_collections.knowledge_collection_id", ondelete="CASCADE"),
        nullable=False
    )
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class AdminChangeSetEntity(TenantAuditMixin, Base):
    __tablename__ = "admin_change_sets"
    change_set_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class AdminReviewTaskEntity(TenantAuditMixin, Base):
    __tablename__ = "admin_review_tasks"
    review_task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    change_set_id: Mapped[str] = mapped_column(
        ForeignKey("admin_change_sets.change_set_id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class AdminPublishRecordEntity(TenantAuditMixin, Base):
    __tablename__ = "admin_publish_records"
    publish_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    object_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    published_by: Mapped[str] = mapped_column(String(160), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class RegistrySyncEventEntity(TenantAuditMixin, Base):
    __tablename__ = "registry_sync_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "object_kind", "object_id", "version_id", "event_version",
            name="uq_registry_sync_event_idempotency"
        ),
        Index("ix_registry_sync_pending", "status", "created_at"),
    )
    registry_sync_event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    object_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnalysisSnapshotRegistryPinEntity(TenantAuditMixin, Base):
    __tablename__ = "analysis_snapshot_registry_pins"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "analysis_snapshot_id", "pin_type", "logical_key",
            name="uq_analysis_snapshot_registry_pin"
        ),
        Index("ix_snapshot_registry_pin", "tenant_id", "analysis_snapshot_id"),
    )
    pin_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_snapshots.analysis_snapshot_id", ondelete="CASCADE"), nullable=False
    )
    pin_type: Mapped[str] = mapped_column(String(80), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(200), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)

from crossborder_compliance.infrastructure.persistence import knowledge_models as _knowledge_models  # noqa: E402,F401
from crossborder_compliance.infrastructure.persistence import retrieval_models as _retrieval_models  # noqa: E402,F401
