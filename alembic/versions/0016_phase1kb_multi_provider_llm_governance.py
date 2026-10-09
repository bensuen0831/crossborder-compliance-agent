"""Freeze configuration inside the existing canonical model deployment version."""

from sqlalchemy import inspect, text

from alembic import op

revision = "0016_phase1kb_multi_provider_llm_governance"
down_revision = "0015_m2d_review_governance"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    provider_columns = {c["name"] for c in inspect(conn).get_columns("model_provider_versions")}
    if "health_status" not in provider_columns:
        op.execute(
            "ALTER TABLE model_provider_versions "
            "ADD COLUMN health_status varchar(40) NOT NULL DEFAULT 'UNKNOWN'"
        )
    if "health_checked_at" not in provider_columns:
        op.execute(
            "ALTER TABLE model_provider_versions "
            "ADD COLUMN health_checked_at timestamp with time zone"
        )
    if "configuration_json" not in {
        c["name"] for c in inspect(conn).get_columns("model_deployments")
    }:
        op.execute(
            "ALTER TABLE model_deployments "
            "ADD COLUMN configuration_json json NOT NULL DEFAULT '{}' "
        )
    # Historical0002 loads live metadata; checkfirst makes both migration paths equivalent.
    op.execute("""UPDATE model_deployments d SET configuration_json = json_build_object(
        'remote_model_name', m.model_id, 'max_output_tokens', coalesce(m.max_output_tokens,1),
        'capabilities', coalesce((SELECT json_agg(c.capability ORDER BY c.capability)
          FROM model_capabilities c WHERE c.model_definition_id=m.model_definition_id
          AND c.tenant_id=m.tenant_id AND c.status='ACTIVE'),'[]'::json),
        'embedding_dimension', (SELECT (c.metadata_json->>'embedding_dimension')::int
          FROM model_capabilities c WHERE c.model_definition_id=m.model_definition_id
          AND c.tenant_id=m.tenant_id AND c.capability='EMBEDDING' AND c.status='ACTIVE' LIMIT 1),
        'operations', coalesce(v.endpoint_config_json->'operations','[]'::json),
        'priority', coalesce((v.endpoint_config_json->>'routing_priority')::int,100),
        'structured_output_format','json_schema')
        FROM model_definitions m, model_provider_versions v
        WHERE d.model_definition_id=m.model_definition_id AND d.tenant_id=m.tenant_id
        AND d.provider_version_id=v.provider_version_id AND d.tenant_id=v.tenant_id
        AND d.configuration_json::jsonb='{}'::jsonb""")
    op.execute("""CREATE OR REPLACE FUNCTION phase1kb_model_configuration_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF OLD.lifecycle_status NOT IN ('DRAFT','PENDING_REVIEW') AND (
          NEW.configuration_json::jsonb IS DISTINCT FROM OLD.configuration_json::jsonb
          OR NEW.provider_version_id IS DISTINCT FROM OLD.provider_version_id
          OR NEW.model_definition_id IS DISTINCT FROM OLD.model_definition_id) THEN
          RAISE EXCEPTION 'immutable model deployment configuration'; END IF;
        RETURN NEW; END $$""")
    op.execute("DROP TRIGGER IF EXISTS phase1kb_model_immutable ON model_deployments")
    op.execute("""CREATE TRIGGER phase1kb_model_immutable BEFORE UPDATE ON model_deployments
        FOR EACH ROW EXECUTE FUNCTION phase1kb_model_configuration_immutable()""")
    op.execute("""CREATE OR REPLACE FUNCTION phase1kb_provider_configuration_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF OLD.lifecycle_status NOT IN ('DRAFT','PENDING_REVIEW') AND (
          NEW.endpoint_config_json::jsonb IS DISTINCT FROM OLD.endpoint_config_json::jsonb
          OR NEW.secret_ref IS DISTINCT FROM OLD.secret_ref
          OR NEW.auth_type IS DISTINCT FROM OLD.auth_type
          OR NEW.deployment_type IS DISTINCT FROM OLD.deployment_type
          OR NEW.trust_level IS DISTINCT FROM OLD.trust_level
          OR NEW.data_boundary IS DISTINCT FROM OLD.data_boundary
          OR NEW.timeout_policy_json::jsonb
            IS DISTINCT FROM OLD.timeout_policy_json::jsonb
          OR NEW.retry_policy_json::jsonb IS DISTINCT FROM OLD.retry_policy_json::jsonb
          OR NEW.provider_id IS DISTINCT FROM OLD.provider_id) THEN
          RAISE EXCEPTION 'immutable provider version configuration'; END IF;
        RETURN NEW; END $$""")
    op.execute("DROP TRIGGER IF EXISTS phase1kb_provider_immutable ON model_provider_versions")
    op.execute("""CREATE TRIGGER phase1kb_provider_immutable
        BEFORE UPDATE ON model_provider_versions
        FOR EACH ROW EXECUTE FUNCTION phase1kb_provider_configuration_immutable()""")
    op.execute("""CREATE OR REPLACE FUNCTION phase1kb_policy_configuration_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF OLD.lifecycle_status NOT IN ('DRAFT','PENDING_REVIEW')
        AND EXISTS(
          SELECT 1 FROM metadata_definitions d WHERE d.definition_id=OLD.definition_id
          AND d.tenant_id=OLD.tenant_id
          AND d.kind IN ('LLM_INVOCATION_POLICY','MODEL_USAGE_POLICY'))
          AND (NEW.payload_json::jsonb IS DISTINCT FROM OLD.payload_json::jsonb
          OR NEW.definition_id IS DISTINCT FROM OLD.definition_id
          OR NEW.version_no IS DISTINCT FROM OLD.version_no
          OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
          OR NEW.effective_to IS DISTINCT FROM OLD.effective_to) THEN
          RAISE EXCEPTION 'immutable LLM policy configuration'; END IF;
        RETURN NEW; END $$""")
    op.execute("DROP TRIGGER IF EXISTS phase1kb_policy_immutable ON metadata_versions")
    op.execute("""CREATE TRIGGER phase1kb_policy_immutable BEFORE UPDATE ON metadata_versions
        FOR EACH ROW EXECUTE FUNCTION phase1kb_policy_configuration_immutable()""")


def downgrade():
    if op.get_bind().scalar(
        text("""SELECT EXISTS(SELECT 1 FROM analysis_snapshot_registry_pins
        WHERE pin_type IN ('LLM_SELECTION','LLM_INVOCATION_POLICY'))
        OR EXISTS(SELECT 1 FROM model_deployments WHERE configuration_json::jsonb <> '{}'::jsonb)
        OR EXISTS(SELECT 1 FROM model_provider_versions WHERE health_checked_at IS NOT NULL)""")
    ):
        raise RuntimeError("Phase1K-B configuration/pins retained: archive/export before downgrade")
    op.execute("DROP TRIGGER IF EXISTS phase1kb_model_immutable ON model_deployments")
    op.execute("DROP FUNCTION phase1kb_model_configuration_immutable()")
    op.execute("DROP TRIGGER IF EXISTS phase1kb_provider_immutable ON model_provider_versions")
    op.execute("DROP FUNCTION phase1kb_provider_configuration_immutable()")
    op.execute("DROP TRIGGER IF EXISTS phase1kb_policy_immutable ON metadata_versions")
    op.execute("DROP FUNCTION phase1kb_policy_configuration_immutable()")
    op.drop_column("model_deployments", "configuration_json")
    op.drop_column("model_provider_versions", "health_checked_at")
    op.drop_column("model_provider_versions", "health_status")
