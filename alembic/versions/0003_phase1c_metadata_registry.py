"""Phase 1C metadata / registry / admin foundation.

Revision ID: 0003_phase1c
Revises: 0002_phase1b

Domain/config schema only. LangGraph checkpoint internals remain runtime-owned.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_phase1c"
down_revision = "0002_phase1b"
branch_labels = None
depends_on = None

LIFECYCLE = "lifecycle_status IN ('DRAFT','PENDING_REVIEW','APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')"


def _audit_cols():
    return [
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _effective_cols():
    return [
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
    ]


def _create(name, *cols, constraints=(), indexes=()):
    op.create_table(name, *cols, *_audit_cols(), *constraints)
    op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])
    for index_name, columns in indexes:
        op.create_index(index_name, name, list(columns))


def upgrade() -> None:
    _create(
        "metadata_definitions",
        sa.Column("definition_id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("code", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(250), nullable=False),
        sa.Column("canonical_object_type", sa.String(80), nullable=True),
        sa.Column("canonical_object_id", sa.String(36), nullable=True),
        sa.Column("parent_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="SET NULL"), nullable=True),
        sa.Column("active_version_id", sa.String(36), nullable=True),
        constraints=(
            sa.UniqueConstraint("tenant_id","kind","code",name="uq_metadata_definition_kind_code"),
            sa.UniqueConstraint("tenant_id","kind","canonical_object_id",name="uq_metadata_definition_canonical_ref"),
        ),
        indexes=(("ix_metadata_definition_kind_status",("tenant_id","kind","status")),),
    )
    _create(
        "metadata_versions",
        sa.Column("version_id", sa.String(36), primary_key=True),
        sa.Column("definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("approved_by", sa.String(160), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","definition_id","version_no",name="uq_metadata_version_number"),
            sa.CheckConstraint("version_no >= 1",name="ck_metadata_version_number"),
            sa.CheckConstraint(LIFECYCLE,name="ck_metadata_version_lifecycle"),
        ),
        indexes=(("ix_metadata_version_runtime",("tenant_id","definition_id","lifecycle_status")),),
    )
    op.create_foreign_key(
        "fk_metadata_definition_active_version","metadata_definitions","metadata_versions",
        ["active_version_id"],["version_id"],ondelete="SET NULL"
    )
    _create(
        "metadata_bindings",
        sa.Column("binding_id", sa.String(36), primary_key=True),
        sa.Column("binding_type", sa.String(100), nullable=False),
        sa.Column("source_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        *_effective_cols(),
        constraints=(sa.UniqueConstraint("tenant_id","binding_type","source_definition_id","target_definition_id",name="uq_metadata_binding"),),
        indexes=(("ix_metadata_binding_source",("tenant_id","source_definition_id","binding_type")),),
    )

    _create(
        "classification_scheme_versions",
        sa.Column("scheme_version_id", sa.String(36), primary_key=True),
        sa.Column("scheme_id", sa.String(36), sa.ForeignKey("classification_schemes.scheme_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("applicability_json", sa.JSON(), nullable=False),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","scheme_id","version_no",name="uq_classification_scheme_version_record"),
            sa.CheckConstraint("version_no >= 1",name="ck_classification_scheme_version_number"),
            sa.CheckConstraint(LIFECYCLE,name="ck_classification_scheme_version_lifecycle"),
        ),
        indexes=(("ix_classification_scheme_version_runtime",("tenant_id","scheme_id","lifecycle_status")),),
    )
    _create(
        "classification_bindings",
        sa.Column("classification_binding_id", sa.String(36), primary_key=True),
        sa.Column("scheme_version_id", sa.String(36), sa.ForeignKey("classification_scheme_versions.scheme_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("jurisdiction_id", sa.String(36), sa.ForeignKey("jurisdictions.jurisdiction_id", ondelete="CASCADE"), nullable=True),
        sa.Column("industry_ref", sa.String(160), nullable=True),
        sa.Column("scenario_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="CASCADE"), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        *_effective_cols(),
        constraints=(sa.UniqueConstraint("tenant_id","scheme_version_id","jurisdiction_id","industry_ref","scenario_definition_id",name="uq_classification_binding_scope"),),
        indexes=(("ix_classification_binding_resolve",("tenant_id","jurisdiction_id","priority")),),
    )
    _create(
        "classification_applicability_metadata",
        sa.Column("classification_applicability_metadata_id", sa.String(36), primary_key=True),
        sa.Column("scheme_version_id", sa.String(36), sa.ForeignKey("classification_scheme_versions.scheme_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("applicability_json", sa.JSON(), nullable=False),
        constraints=(sa.UniqueConstraint("tenant_id","scheme_version_id",name="uq_classification_applicability_version"),),
    )

    _create(
        "model_providers",
        sa.Column("provider_id", sa.String(36), primary_key=True),
        sa.Column("provider_type", sa.String(40), nullable=False),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active_version_id", sa.String(36), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        constraints=(sa.UniqueConstraint("tenant_id","code",name="uq_model_provider_code"),),
        indexes=(("ix_model_provider_enabled",("tenant_id","enabled","status")),),
    )
    _create(
        "model_provider_versions",
        sa.Column("provider_version_id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("model_providers.provider_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("base_url_ref", sa.String(400), nullable=True),
        sa.Column("endpoint_config_json", sa.JSON(), nullable=False),
        sa.Column("auth_type", sa.String(80), nullable=False, server_default="NONE"),
        sa.Column("secret_ref", sa.String(400), nullable=True),
        sa.Column("deployment_type", sa.String(80), nullable=False, server_default="API"),
        sa.Column("trust_level", sa.String(80), nullable=False, server_default="UNSPECIFIED"),
        sa.Column("data_boundary", sa.String(160), nullable=False, server_default="UNSPECIFIED"),
        sa.Column("timeout_policy_json", sa.JSON(), nullable=False),
        sa.Column("retry_policy_json", sa.JSON(), nullable=False),
        sa.Column("cost_metadata_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","provider_id","version_no",name="uq_model_provider_version"),
            sa.CheckConstraint("version_no >= 1",name="ck_model_provider_version_number"),
            sa.CheckConstraint(LIFECYCLE,name="ck_model_provider_version_lifecycle"),
        ),
    )
    op.create_foreign_key(
        "fk_model_provider_active_version","model_providers","model_provider_versions",
        ["active_version_id"],["provider_version_id"],ondelete="SET NULL"
    )
    _create(
        "model_definitions",
        sa.Column("model_definition_id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("model_providers.provider_id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("active_deployment_id", sa.String(36), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        constraints=(sa.UniqueConstraint("tenant_id","provider_id","model_id",name="uq_model_definition_provider_model"),),
        indexes=(("ix_model_definition_enabled",("tenant_id","enabled","status")),),
    )
    _create(
        "model_deployments",
        sa.Column("model_deployment_id", sa.String(36), primary_key=True),
        sa.Column("model_definition_id", sa.String(36), sa.ForeignKey("model_definitions.model_definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_version_id", sa.String(36), sa.ForeignKey("model_provider_versions.provider_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("deployment_ref", sa.String(240), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","model_definition_id","deployment_ref",name="uq_model_deployment_ref"),
            sa.CheckConstraint(LIFECYCLE,name="ck_model_deployment_lifecycle"),
        ),
    )
    op.create_foreign_key(
        "fk_model_definition_active_deployment","model_definitions","model_deployments",
        ["active_deployment_id"],["model_deployment_id"],ondelete="SET NULL"
    )
    _create(
        "model_capabilities",
        sa.Column("model_capability_id", sa.String(36), primary_key=True),
        sa.Column("model_definition_id", sa.String(36), sa.ForeignKey("model_definitions.model_definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        constraints=(sa.UniqueConstraint("tenant_id","model_definition_id","capability",name="uq_model_capability"),),
        indexes=(("ix_model_capability_resolve",("tenant_id","capability","status")),),
    )
    _create(
        "model_routing_profiles",
        sa.Column("routing_profile_id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("required_capabilities_json", sa.JSON(), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        constraints=(sa.UniqueConstraint("tenant_id","code",name="uq_model_routing_profile_code"),),
    )
    _create(
        "model_health_metadata",
        sa.Column("model_health_metadata_id", sa.String(36), primary_key=True),
        sa.Column("model_deployment_id", sa.String(36), sa.ForeignKey("model_deployments.model_deployment_id", ondelete="CASCADE"), nullable=False),
        sa.Column("health_status", sa.String(80), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        indexes=(("ix_model_health_latest",("tenant_id","model_deployment_id","observed_at")),),
    )

    _create(
        "prompt_definitions",
        sa.Column("prompt_definition_id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active_version_id", sa.String(36), nullable=True),
        constraints=(sa.UniqueConstraint("tenant_id","code",name="uq_prompt_definition_code"),),
    )
    _create(
        "prompt_versions",
        sa.Column("prompt_version_id", sa.String(36), primary_key=True),
        sa.Column("prompt_definition_id", sa.String(36), sa.ForeignKey("prompt_definitions.prompt_definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("capability_requirement_json", sa.JSON(), nullable=False),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","prompt_definition_id","version_no",name="uq_prompt_version"),
            sa.CheckConstraint("version_no >= 1",name="ck_prompt_version_number"),
            sa.CheckConstraint(LIFECYCLE,name="ck_prompt_version_lifecycle"),
        ),
    )
    op.create_foreign_key("fk_prompt_definition_active_version","prompt_definitions","prompt_versions",["active_version_id"],["prompt_version_id"],ondelete="SET NULL")
    _create(
        "prompt_bindings",
        sa.Column("prompt_binding_id", sa.String(36), primary_key=True),
        sa.Column("prompt_version_id", sa.String(36), sa.ForeignKey("prompt_versions.prompt_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("binding_type", sa.String(80), nullable=False),
        sa.Column("binding_ref", sa.String(200), nullable=False),
        sa.Column("scenario_definition_id", sa.String(36), sa.ForeignKey("metadata_definitions.definition_id", ondelete="SET NULL"), nullable=True),
        sa.Column("jurisdiction_id", sa.String(36), sa.ForeignKey("jurisdictions.jurisdiction_id", ondelete="SET NULL"), nullable=True),
        sa.Column("language_code", sa.String(40), nullable=True),
        *_effective_cols(),
        constraints=(sa.UniqueConstraint("tenant_id","prompt_version_id","binding_type","binding_ref",name="uq_prompt_binding"),),
    )
    _create(
        "prompt_variable_schemas",
        sa.Column("prompt_variable_schema_id", sa.String(36), primary_key=True),
        sa.Column("prompt_version_id", sa.String(36), sa.ForeignKey("prompt_versions.prompt_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        constraints=(sa.UniqueConstraint("tenant_id","prompt_version_id",name="uq_prompt_variable_schema"),),
    )
    _create(
        "prompt_reviews",
        sa.Column("prompt_review_id", sa.String(36), primary_key=True),
        sa.Column("prompt_version_id", sa.String(36), sa.ForeignKey("prompt_versions.prompt_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(160), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    _create(
        "prompt_publish_records",
        sa.Column("prompt_publish_record_id", sa.String(36), primary_key=True),
        sa.Column("prompt_version_id", sa.String(36), sa.ForeignKey("prompt_versions.prompt_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_by", sa.String(160), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )

    _create(
        "rule_definitions",
        sa.Column("rule_definition_id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active_version_id", sa.String(36), nullable=True),
        constraints=(sa.UniqueConstraint("tenant_id","code",name="uq_rule_definition_code"),),
    )
    _create(
        "rule_versions",
        sa.Column("rule_version_id", sa.String(36), primary_key=True),
        sa.Column("rule_definition_id", sa.String(36), sa.ForeignKey("rule_definitions.rule_definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("safe_dsl_json", sa.JSON(), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","rule_definition_id","version_no",name="uq_rule_version"),
            sa.CheckConstraint("version_no >= 1",name="ck_rule_version_number"),
            sa.CheckConstraint(LIFECYCLE,name="ck_rule_version_lifecycle"),
        ),
    )
    op.create_foreign_key("fk_rule_definition_active_version","rule_definitions","rule_versions",["active_version_id"],["rule_version_id"],ondelete="SET NULL")
    _create(
        "rule_bindings",
        sa.Column("rule_binding_id", sa.String(36), primary_key=True),
        sa.Column("rule_version_id", sa.String(36), sa.ForeignKey("rule_versions.rule_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("binding_type", sa.String(80), nullable=False),
        sa.Column("binding_ref", sa.String(200), nullable=False),
        *_effective_cols(),
        constraints=(sa.UniqueConstraint("tenant_id","rule_version_id","binding_type","binding_ref",name="uq_rule_binding"),),
    )
    _create(
        "rule_test_cases",
        sa.Column("rule_test_case_id", sa.String(36), primary_key=True),
        sa.Column("rule_version_id", sa.String(36), sa.ForeignKey("rule_versions.rule_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_context_json", sa.JSON(), nullable=False),
        sa.Column("expected_result_json", sa.JSON(), nullable=False),
    )
    _create(
        "rule_publish_records",
        sa.Column("rule_publish_record_id", sa.String(36), primary_key=True),
        sa.Column("rule_version_id", sa.String(36), sa.ForeignKey("rule_versions.rule_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_by", sa.String(160), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )

    _create(
        "template_definitions",
        sa.Column("template_definition_id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("template_type", sa.String(80), nullable=False),
        sa.Column("active_version_id", sa.String(36), nullable=True),
        constraints=(sa.UniqueConstraint("tenant_id","code",name="uq_template_definition_code"),),
    )
    _create(
        "template_versions",
        sa.Column("template_version_id", sa.String(36), primary_key=True),
        sa.Column("template_definition_id", sa.String(36), sa.ForeignKey("template_definitions.template_definition_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("field_schema_json", sa.JSON(), nullable=False),
        sa.Column("content_ref", sa.String(400), nullable=True),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","template_definition_id","version_no",name="uq_template_version"),
            sa.CheckConstraint("version_no >= 1",name="ck_template_version_number"),
            sa.CheckConstraint(LIFECYCLE,name="ck_template_version_lifecycle"),
        ),
    )
    op.create_foreign_key("fk_template_definition_active_version","template_definitions","template_versions",["active_version_id"],["template_version_id"],ondelete="SET NULL")
    _create(
        "template_bindings",
        sa.Column("template_binding_id", sa.String(36), primary_key=True),
        sa.Column("template_version_id", sa.String(36), sa.ForeignKey("template_versions.template_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("binding_type", sa.String(80), nullable=False),
        sa.Column("binding_ref", sa.String(200), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        *_effective_cols(),
        constraints=(sa.UniqueConstraint("tenant_id","template_version_id","binding_type","binding_ref",name="uq_template_binding"),),
    )
    _create(
        "template_field_schemas",
        sa.Column("template_field_schema_id", sa.String(36), primary_key=True),
        sa.Column("template_version_id", sa.String(36), sa.ForeignKey("template_versions.template_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        constraints=(sa.UniqueConstraint("tenant_id","template_version_id",name="uq_template_field_schema"),),
    )
    _create(
        "template_reviews",
        sa.Column("template_review_id", sa.String(36), primary_key=True),
        sa.Column("template_version_id", sa.String(36), sa.ForeignKey("template_versions.template_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(160), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
    )
    _create(
        "template_publish_records",
        sa.Column("template_publish_record_id", sa.String(36), primary_key=True),
        sa.Column("template_version_id", sa.String(36), sa.ForeignKey("template_versions.template_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_by", sa.String(160), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )

    _create(
        "knowledge_collections",
        sa.Column("knowledge_collection_id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active_version_id", sa.String(36), nullable=True),
        constraints=(sa.UniqueConstraint("tenant_id","code",name="uq_knowledge_collection_code"),),
    )
    _create(
        "knowledge_collection_versions",
        sa.Column("knowledge_collection_version_id", sa.String(36), primary_key=True),
        sa.Column("knowledge_collection_id", sa.String(36), sa.ForeignKey("knowledge_collections.knowledge_collection_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        *_effective_cols(),
        constraints=(
            sa.UniqueConstraint("tenant_id","knowledge_collection_id","version_no",name="uq_knowledge_collection_version"),
            sa.CheckConstraint("version_no >= 1",name="ck_knowledge_collection_version_number"),
            sa.CheckConstraint(LIFECYCLE,name="ck_knowledge_collection_version_lifecycle"),
        ),
    )
    op.create_foreign_key("fk_knowledge_collection_active_version","knowledge_collections","knowledge_collection_versions",["active_version_id"],["knowledge_collection_version_id"],ondelete="SET NULL")
    _create(
        "knowledge_bindings",
        sa.Column("knowledge_binding_id", sa.String(36), primary_key=True),
        sa.Column("knowledge_collection_version_id", sa.String(36), sa.ForeignKey("knowledge_collection_versions.knowledge_collection_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_type", sa.String(80), nullable=False),
        sa.Column("scope_ref", sa.String(200), nullable=True),
        *_effective_cols(),
        constraints=(sa.UniqueConstraint("tenant_id","knowledge_collection_version_id","scope_type","scope_ref",name="uq_knowledge_binding"),),
    )
    _create(
        "knowledge_scope_metadata",
        sa.Column("knowledge_scope_metadata_id", sa.String(36), primary_key=True),
        sa.Column("knowledge_binding_id", sa.String(36), sa.ForeignKey("knowledge_bindings.knowledge_binding_id", ondelete="CASCADE"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    _create(
        "knowledge_source_definitions",
        sa.Column("knowledge_source_definition_id", sa.String(36), primary_key=True),
        sa.Column("knowledge_collection_id", sa.String(36), sa.ForeignKey("knowledge_collections.knowledge_collection_id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(160), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        constraints=(sa.UniqueConstraint("tenant_id","knowledge_collection_id","code",name="uq_knowledge_source_definition"),),
    )

    _create(
        "admin_change_sets",
        sa.Column("change_set_id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("summary", sa.Text(), nullable=True),
    )
    _create(
        "admin_review_tasks",
        sa.Column("review_task_id", sa.String(36), primary_key=True),
        sa.Column("change_set_id", sa.String(36), sa.ForeignKey("admin_change_sets.change_set_id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(160), nullable=True),
        sa.Column("review_status", sa.String(40), nullable=False, server_default="PENDING"),
        sa.Column("decision_comment", sa.Text(), nullable=True),
    )
    _create(
        "admin_publish_records",
        sa.Column("publish_record_id", sa.String(36), primary_key=True),
        sa.Column("object_kind", sa.String(80), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("published_by", sa.String(160), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create(
        "registry_sync_events",
        sa.Column("registry_sync_event_id", sa.String(36), primary_key=True),
        sa.Column("object_kind", sa.String(80), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        constraints=(sa.UniqueConstraint("tenant_id","object_kind","object_id","version_id","event_version",name="uq_registry_sync_event_idempotency"),),
        indexes=(("ix_registry_sync_pending",("status","created_at")),),
    )
    _create(
        "analysis_snapshot_registry_pins",
        sa.Column("pin_id", sa.String(36), primary_key=True),
        sa.Column("analysis_snapshot_id", sa.String(36), sa.ForeignKey("analysis_snapshots.analysis_snapshot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("pin_type", sa.String(80), nullable=False),
        sa.Column("logical_key", sa.String(200), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        constraints=(sa.UniqueConstraint("tenant_id","analysis_snapshot_id","pin_type","logical_key",name="uq_analysis_snapshot_registry_pin"),),
        indexes=(("ix_snapshot_registry_pin",("tenant_id","analysis_snapshot_id")),),
    )


def downgrade() -> None:
    for constraint, table in [
        ("fk_knowledge_collection_active_version","knowledge_collections"),
        ("fk_template_definition_active_version","template_definitions"),
        ("fk_rule_definition_active_version","rule_definitions"),
        ("fk_prompt_definition_active_version","prompt_definitions"),
        ("fk_model_definition_active_deployment","model_definitions"),
        ("fk_model_provider_active_version","model_providers"),
        ("fk_metadata_definition_active_version","metadata_definitions"),
    ]:
        op.drop_constraint(constraint, table, type_="foreignkey")

    for table in [
        "analysis_snapshot_registry_pins","registry_sync_events","admin_publish_records",
        "admin_review_tasks","admin_change_sets","knowledge_source_definitions",
        "knowledge_scope_metadata","knowledge_bindings","knowledge_collection_versions",
        "knowledge_collections","template_publish_records","template_reviews",
        "template_field_schemas","template_bindings","template_versions","template_definitions",
        "rule_publish_records","rule_test_cases","rule_bindings","rule_versions","rule_definitions",
        "prompt_publish_records","prompt_reviews","prompt_variable_schemas","prompt_bindings",
        "prompt_versions","prompt_definitions","model_health_metadata","model_routing_profiles",
        "model_capabilities","model_deployments","model_definitions","model_provider_versions",
        "model_providers","classification_applicability_metadata","classification_bindings",
        "classification_scheme_versions","metadata_bindings","metadata_versions","metadata_definitions",
    ]:
        op.drop_table(table)
