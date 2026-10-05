"""Frozen explicit J envelope DDL; compatible with historical0002 live metadata."""

import sqlalchemy as sa

from alembic import op

revision = "0010_phase1j"
down_revision = "0009_phase1i"
branch_labels = None
depends_on = None

# Deliberately frozen here, not imported from application metadata/models.
TABLES = {
    "OBLIGATION": "compliance_obligation_results",
    "CANDIDATE_PATH": "candidate_compliance_path_results",
    "RISK": "risk_assessment_results",
    "RECOMMENDATION": "compliance_recommendation_results",
    "FINAL_PATH": "final_compliance_path_results",
}
PARENTS = {
    "OBLIGATION": (),
    "CANDIDATE_PATH": ("OBLIGATION",),
    "RISK": ("CANDIDATE_PATH",),
    "RECOMMENDATION": ("CANDIDATE_PATH", "RISK"),
    "FINAL_PATH": ("OBLIGATION", "CANDIDATE_PATH", "RISK", "RECOMMENDATION"),
}
SCOPE = "tenant_id,project_id,analysis_snapshot_id,project_version_id,context_version,subject_type,subject_id"
AUDIT = "tenant_id varchar(36) NOT NULL,record_version integer NOT NULL DEFAULT 1,status varchar(40) NOT NULL DEFAULT 'ACTIVE',created_at timestamptz NOT NULL,updated_at timestamptz NOT NULL"
POLICIES = "'OBLIGATION_POLICY','COMPLIANCE_PATH_POLICY','RISK_POLICY','RECOMMENDATION_POLICY'"


def upgrade():
    for kind, name in TABLES.items():
        extra = ""
        for parent in PARENTS[kind]:
            col = parent.lower() + "_result_id"
            extra += f",{col} varchar(36) NOT NULL,CONSTRAINT fk_j_{kind.lower()}_{parent.lower()} FOREIGN KEY({SCOPE},{col}) REFERENCES {TABLES[parent]}({SCOPE},result_id)"
        op.execute(f"""CREATE TABLE IF NOT EXISTS {name} (
            result_id varchar(36) PRIMARY KEY,{AUDIT},project_id varchar(36) NOT NULL REFERENCES projects(project_id),
            analysis_snapshot_id varchar(36) NOT NULL REFERENCES analysis_snapshots(analysis_snapshot_id),
            project_version_id varchar(36) NOT NULL REFERENCES project_versions(project_version_id),context_version integer NOT NULL,
            subject_type varchar(40) NOT NULL,subject_id varchar(36) NOT NULL,analysis_as_of_date date NOT NULL,
            jurisdiction_ids json NOT NULL,policy_version_id varchar(36) REFERENCES metadata_versions(version_id),
            upstream_refs json NOT NULL,pins_json json NOT NULL,provenance_json json NOT NULL,
            input_fingerprint varchar(64) NOT NULL,pins_digest varchar(64) NOT NULL,contract_version varchar(20) NOT NULL,
            engine_version varchar(60) NOT NULL,owner_actor_id varchar(160) NOT NULL,summary_status varchar(60) NOT NULL,
            request_json json NOT NULL,result_json json NOT NULL,
            CONSTRAINT uq_j_{kind.lower()}_scope UNIQUE({SCOPE},result_id),
            CONSTRAINT uq_j_{kind.lower()}_input UNIQUE(tenant_id,project_id,analysis_snapshot_id,subject_type,subject_id,input_fingerprint),
            CONSTRAINT ck_j_{kind.lower()}_subject CHECK(subject_type IN ('DATA_ITEM','DATA_FLOW','SCENARIO')),
            CONSTRAINT ck_j_{kind.lower()}_version CHECK(contract_version='2.0' AND engine_version='FORMAL_DECISION_V2'){extra})""")
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{name}_tenant_id ON {name}(tenant_id)")
    op.execute(
        f"CREATE TABLE IF NOT EXISTS obligation_applicability_links(link_id varchar(36) PRIMARY KEY,{AUDIT},obligation_result_id varchar(36) NOT NULL REFERENCES compliance_obligation_results(result_id),applicability_result_id varchar(36) NOT NULL REFERENCES regulation_applicability_results(applicability_result_id),CONSTRAINT uq_j_applicability_link UNIQUE(tenant_id,obligation_result_id,applicability_result_id))"
    )
    op.execute(
        f"CREATE TABLE IF NOT EXISTS decision_request_keys(request_key_id varchar(36) PRIMARY KEY,{AUDIT},project_id varchar(36) NOT NULL REFERENCES projects(project_id),stage_kind varchar(40) NOT NULL,idempotency_key varchar(160) NOT NULL,input_fingerprint varchar(64) NOT NULL,result_id varchar(36) NOT NULL,CONSTRAINT uq_j_request_key UNIQUE(tenant_id,project_id,stage_kind,idempotency_key),CONSTRAINT ck_j_request_kind CHECK(stage_kind IN ('OBLIGATION','CANDIDATE_PATH','RISK','RECOMMENDATION','FINAL_PATH')))"
    )
    for name in ("obligation_applicability_links", "decision_request_keys"):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{name}_tenant_id ON {name}(tenant_id)")
    op.execute(
        """CREATE FUNCTION phase1j_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable Phase1J authority; archive/export required'; END $$"""
    )
    op.execute("""CREATE FUNCTION phase1j_result_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM analysis_snapshots s JOIN project_versions v ON v.project_version_id=s.project_version_id
        WHERE s.analysis_snapshot_id=NEW.analysis_snapshot_id AND s.tenant_id=NEW.tenant_id
        AND v.tenant_id=NEW.tenant_id AND v.project_id=NEW.project_id AND v.project_version_id=NEW.project_version_id)
      THEN RAISE EXCEPTION 'Phase1J snapshot scope mismatch'; END IF;
      IF NEW.result_json->>'tenant_id' IS DISTINCT FROM NEW.tenant_id OR NEW.result_json->>'project_id' IS DISTINCT FROM NEW.project_id
        OR NEW.result_json->>'analysis_snapshot_id' IS DISTINCT FROM NEW.analysis_snapshot_id OR NEW.result_json->>'result_id' IS DISTINCT FROM NEW.result_id
        OR NEW.result_json->>'input_digest' IS DISTINCT FROM NEW.input_fingerprint OR NEW.result_json->>'pins_digest' IS DISTINCT FROM NEW.pins_digest
      THEN RAISE EXCEPTION 'Phase1J payload identity mismatch'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE FUNCTION phase1j_applicability_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM compliance_obligation_results j JOIN regulation_applicability_results i
        ON i.applicability_result_id=NEW.applicability_result_id WHERE j.result_id=NEW.obligation_result_id
        AND j.tenant_id=NEW.tenant_id AND i.tenant_id=NEW.tenant_id AND i.project_id=j.project_id
        AND i.analysis_snapshot_id=j.analysis_snapshot_id AND i.subject_type=j.subject_type AND i.subject_id=j.subject_id)
      THEN RAISE EXCEPTION 'Phase1J applicability scope mismatch'; END IF;
      RETURN NEW;
    END $$""")
    cases = " ".join(f"WHEN '{kind}' THEN '{name}'" for kind, name in TABLES.items())
    op.execute(f"""CREATE FUNCTION phase1j_request_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target text; valid boolean;
    BEGIN target := CASE NEW.stage_kind {cases} END;
      EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I WHERE result_id=$1 AND tenant_id=$2 AND project_id=$3 AND input_fingerprint=$4)',target)
        INTO valid USING NEW.result_id,NEW.tenant_id,NEW.project_id,NEW.input_fingerprint;
      IF NOT valid THEN RAISE EXCEPTION 'Phase1J request reference mismatch'; END IF; RETURN NEW;
    END $$""")
    for name in (*TABLES.values(), "obligation_applicability_links", "decision_request_keys"):
        op.execute(
            f"CREATE TRIGGER tr_j_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION phase1j_immutable()"
        )
    for name in TABLES.values():
        op.execute(
            f"CREATE TRIGGER tr_j_scope BEFORE INSERT ON {name} FOR EACH ROW EXECUTE FUNCTION phase1j_result_scope()"
        )
    op.execute(
        "CREATE TRIGGER tr_j_app_scope BEFORE INSERT ON obligation_applicability_links FOR EACH ROW EXECUTE FUNCTION phase1j_applicability_scope()"
    )
    op.execute(
        "CREATE TRIGGER tr_j_request_scope BEFORE INSERT ON decision_request_keys FOR EACH ROW EXECUTE FUNCTION phase1j_request_scope()"
    )
    op.execute(f"""CREATE FUNCTION phase1j_policy_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE k text;
    BEGIN
      IF TG_TABLE_NAME='metadata_definitions' THEN k:=OLD.kind;
      ELSE SELECT kind INTO k FROM metadata_definitions WHERE definition_id=OLD.definition_id AND tenant_id=OLD.tenant_id; END IF;
      IF k IN ({POLICIES}) THEN
        IF TG_TABLE_NAME='metadata_definitions' THEN
          IF TG_OP='DELETE' THEN
            IF EXISTS(SELECT 1 FROM metadata_versions WHERE definition_id=OLD.definition_id AND tenant_id=OLD.tenant_id AND lifecycle_status IN ('APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')) THEN RAISE EXCEPTION 'immutable Phase1J policy identity'; END IF;
          ELSIF NEW.kind<>OLD.kind OR NEW.code<>OLD.code OR NEW.definition_id<>OLD.definition_id OR NEW.tenant_id<>OLD.tenant_id THEN RAISE EXCEPTION 'immutable Phase1J policy identity'; END IF;
        ELSIF OLD.lifecycle_status IN ('APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')
          AND (TG_OP='DELETE' OR NEW.payload_json::text<>OLD.payload_json::text OR NEW.definition_id<>OLD.definition_id
          OR NEW.version_no<>OLD.version_no OR NEW.version_id<>OLD.version_id OR NEW.tenant_id<>OLD.tenant_id
          OR NEW.created_by<>OLD.created_by OR NEW.approved_by IS DISTINCT FROM OLD.approved_by OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
          OR NEW.lifecycle_status NOT IN ('APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')
          OR (OLD.published_at IS NOT NULL AND NEW.published_at IS DISTINCT FROM OLD.published_at)
          OR NEW.effective_from IS DISTINCT FROM OLD.effective_from OR NEW.effective_to IS DISTINCT FROM OLD.effective_to)
        THEN RAISE EXCEPTION 'immutable Phase1J policy payload'; END IF;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$""")
    for name in ("metadata_definitions", "metadata_versions"):
        op.execute(
            f"CREATE TRIGGER tr_j_policy_guard BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION phase1j_policy_guard()"
        )
    op.execute("""CREATE FUNCTION phase1j_pin_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN IF OLD.pin_type LIKE 'PHASE1J_%' THEN RAISE EXCEPTION 'immutable Phase1J snapshot pin'; END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
    op.execute(
        "CREATE TRIGGER tr_j_pin_guard BEFORE UPDATE OR DELETE ON analysis_snapshot_registry_pins FOR EACH ROW EXECUTE FUNCTION phase1j_pin_guard()"
    )


def downgrade():
    conn = op.get_bind()
    for table in TABLES.values():
        if conn.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Phase1J authority retained; archive/export required")
    if conn.execute(
        sa.text(
            f"SELECT EXISTS(SELECT 1 FROM metadata_definitions WHERE kind IN ({POLICIES})) OR EXISTS(SELECT 1 FROM analysis_snapshot_registry_pins WHERE pin_type LIKE 'PHASE1J_%')"
        )
    ).scalar():
        raise RuntimeError("Phase1J policies/pins retained; explicit archive/export required")
    for table in ("metadata_definitions", "metadata_versions"):
        op.execute(f"DROP TRIGGER tr_j_policy_guard ON {table}")
    op.execute("DROP TRIGGER tr_j_pin_guard ON analysis_snapshot_registry_pins")
    for table in (
        "decision_request_keys",
        "obligation_applicability_links",
        *reversed(tuple(TABLES.values())),
    ):
        op.drop_table(table)
    for name in (
        "phase1j_immutable",
        "phase1j_result_scope",
        "phase1j_applicability_scope",
        "phase1j_request_scope",
        "phase1j_policy_guard",
        "phase1j_pin_guard",
    ):
        op.execute(f"DROP FUNCTION {name}()")
