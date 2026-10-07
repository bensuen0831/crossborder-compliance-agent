"""C0 owning formal result envelopes; frozen history and existing authority reused."""
from alembic import op
from sqlalchemy import text
revision='0014_m2c_formal_result_authority'
down_revision='0013_m2b_context_temporal_contract'
branch_labels=None
depends_on=None
J_TABLES={'OBLIGATION':'compliance_obligation_results','CANDIDATE_PATH':'candidate_compliance_path_results','RISK':'risk_assessment_results','RECOMMENDATION':'compliance_recommendation_results','FINAL_PATH':'final_compliance_path_results'}
TABLES={'CROSS_BORDER':'cross_border_assessment_results','DOCUMENT_REQUIREMENT':'regulatory_document_requirement_results'}
SCOPE=('tenant_id','project_id','analysis_snapshot_id','project_version_id','context_version','subject_type','subject_id')
AUDIT="tenant_id varchar(36) NOT NULL,status varchar(40) NOT NULL DEFAULT 'ACTIVE',record_version integer NOT NULL DEFAULT 1,created_at timestamptz NOT NULL,updated_at timestamptz NOT NULL"
POLICIES="'CROSS_BORDER_ASSESSMENT_POLICY','DOCUMENT_REQUIREMENT_POLICY'"

def request_scope(tables):
    cases=' '.join(f"WHEN '{kind}' THEN '{name}'" for kind,name in tables.items())
    op.execute(f"""CREATE OR REPLACE FUNCTION phase1j_request_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target text; valid boolean;
    BEGIN target:=CASE NEW.stage_kind {cases} END;
      IF target IS NULL THEN RAISE EXCEPTION 'unknown formal request authority'; END IF;
      EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I WHERE result_id=$1 AND tenant_id=$2 AND project_id=$3 AND input_fingerprint=$4)',target)
        INTO valid USING NEW.result_id,NEW.tenant_id,NEW.project_id,NEW.input_fingerprint;
      IF NOT valid THEN RAISE EXCEPTION 'formal request reference mismatch'; END IF; RETURN NEW;
    END $$""")
    op.execute('ALTER TABLE decision_request_keys DROP CONSTRAINT IF EXISTS ck_j_request_kind')
    kinds=','.join("'"+k+"'" for k in tables)
    op.execute(f'ALTER TABLE decision_request_keys ADD CONSTRAINT ck_j_request_kind CHECK(stage_kind IN ({kinds}))')

def upgrade():
    for kind,name in TABLES.items():
        parents={'obligation_result_id':J_TABLES['OBLIGATION']}
        if kind=='DOCUMENT_REQUIREMENT':parents.update(cross_border_result_id=TABLES['CROSS_BORDER'],final_path_result_id=J_TABLES['FINAL_PATH'])
        extra=','.join(col+' varchar(36)' for col in parents)
        fks=','.join(f"CONSTRAINT fk_c0_{kind.lower()}_{col} FOREIGN KEY({','.join((*SCOPE,col))}) REFERENCES {table}({','.join((*SCOPE,'result_id'))})" for col,table in parents.items())
        op.execute(f"""CREATE TABLE IF NOT EXISTS {name}(result_id varchar(36) PRIMARY KEY,{AUDIT},
          project_id varchar(36) NOT NULL REFERENCES projects(project_id),analysis_snapshot_id varchar(36) NOT NULL REFERENCES analysis_snapshots(analysis_snapshot_id),
          project_version_id varchar(36) NOT NULL REFERENCES project_versions(project_version_id),context_version integer NOT NULL,
          subject_type varchar(40) NOT NULL,subject_id varchar(36) NOT NULL,analysis_as_of_date date NOT NULL,jurisdiction_ids json NOT NULL,
          policy_version_id varchar(36) REFERENCES metadata_versions(version_id),upstream_refs json NOT NULL,pins_json json NOT NULL,provenance_json json NOT NULL,
          input_fingerprint varchar(64) NOT NULL,pins_digest varchar(64) NOT NULL,contract_version varchar(20) NOT NULL,engine_version varchar(60) NOT NULL,
          owner_actor_id varchar(160) NOT NULL,summary_status varchar(60) NOT NULL,request_json json NOT NULL,result_json json NOT NULL,{extra},
          CONSTRAINT uq_c0_{kind.lower()}_scope UNIQUE({','.join((*SCOPE,'result_id'))}),
          CONSTRAINT uq_c0_{kind.lower()}_input UNIQUE(tenant_id,project_id,analysis_snapshot_id,subject_type,subject_id,input_fingerprint),
          CONSTRAINT ck_c0_{kind.lower()}_subject CHECK(subject_type IN ('DATA_ITEM','DATA_FLOW','SCENARIO')),
          CONSTRAINT ck_c0_{kind.lower()}_version CHECK(contract_version='2.0' AND engine_version='FORMAL_RESULT_AUTHORITY_V2'),{fks})""")
        op.execute(f'CREATE TRIGGER tr_c0_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION phase1j_immutable()')
        op.execute(f'CREATE TRIGGER tr_c0_identity BEFORE INSERT ON {name} FOR EACH ROW EXECUTE FUNCTION phase1j_result_scope()')
    request_scope(J_TABLES|TABLES)
    op.execute("""CREATE FUNCTION phase1c0_result_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM analysis_snapshot_context_pins p WHERE p.tenant_id=NEW.tenant_id AND p.project_id=NEW.project_id
        AND p.analysis_snapshot_id=NEW.analysis_snapshot_id AND p.context_resolution_version=NEW.context_version)
      THEN RAISE EXCEPTION 'C0 exact context pin required'; END IF;
      IF NEW.summary_status<>'REVIEW_REQUIRED' AND (NEW.obligation_result_id IS NULL OR NEW.policy_version_id IS NULL)
      THEN RAISE EXCEPTION 'C0 legal result requires formal obligation/policy'; END IF;
      IF TG_TABLE_NAME='regulatory_document_requirement_results' AND NEW.summary_status<>'REVIEW_REQUIRED' THEN
        IF NEW.cross_border_result_id IS NULL OR NEW.final_path_result_id IS NULL THEN RAISE EXCEPTION 'document requirement upstream authority missing'; END IF;
      END IF;
      IF NEW.policy_version_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM analysis_snapshot_registry_pins p JOIN metadata_versions v ON v.version_id=p.version_id
        WHERE p.tenant_id=NEW.tenant_id AND v.tenant_id=NEW.tenant_id AND p.analysis_snapshot_id=NEW.analysis_snapshot_id
        AND p.pin_type LIKE 'PHASE1C0_%_POLICY' AND p.version_id=NEW.policy_version_id)
      THEN RAISE EXCEPTION 'C0 exact policy pin required'; END IF; RETURN NEW;
    END $$""")
    for name in TABLES.values():op.execute(f'CREATE TRIGGER tr_c0_authority BEFORE INSERT ON {name} FOR EACH ROW EXECUTE FUNCTION phase1c0_result_guard()')
    op.execute(f"""CREATE FUNCTION phase1c0_policy_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE k text;
    BEGIN
      IF TG_TABLE_NAME='metadata_definitions' THEN k:=OLD.kind;
      ELSE SELECT kind INTO k FROM metadata_definitions WHERE definition_id=OLD.definition_id AND tenant_id=OLD.tenant_id; END IF;
      IF k IN ({POLICIES}) THEN
        IF TG_TABLE_NAME='metadata_definitions' THEN
          IF TG_OP='DELETE' THEN
            IF EXISTS(SELECT 1 FROM metadata_versions WHERE definition_id=OLD.definition_id AND tenant_id=OLD.tenant_id AND lifecycle_status IN ('APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')) THEN RAISE EXCEPTION 'immutable C0 policy identity'; END IF;
          ELSIF NEW.kind<>OLD.kind OR NEW.code<>OLD.code OR NEW.definition_id<>OLD.definition_id OR NEW.tenant_id<>OLD.tenant_id THEN RAISE EXCEPTION 'immutable C0 policy identity'; END IF;
        ELSIF OLD.lifecycle_status IN ('APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')
          AND (TG_OP='DELETE' OR NEW.payload_json::text<>OLD.payload_json::text OR NEW.definition_id<>OLD.definition_id
          OR NEW.version_no<>OLD.version_no OR NEW.version_id<>OLD.version_id OR NEW.tenant_id<>OLD.tenant_id
          OR NEW.created_by<>OLD.created_by OR NEW.approved_by IS DISTINCT FROM OLD.approved_by OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
          OR NEW.lifecycle_status NOT IN ('APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')
          OR (OLD.published_at IS NOT NULL AND NEW.published_at IS DISTINCT FROM OLD.published_at)
          OR NEW.effective_from IS DISTINCT FROM OLD.effective_from OR NEW.effective_to IS DISTINCT FROM OLD.effective_to)
        THEN RAISE EXCEPTION 'immutable C0 policy payload'; END IF;
      END IF; IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$""")
    for name in ('metadata_definitions','metadata_versions'):
        op.execute(f'CREATE TRIGGER tr_c0_policy BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION phase1c0_policy_guard()')
    op.execute("""CREATE FUNCTION phase1c0_pin_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN IF OLD.pin_type LIKE 'PHASE1C0_%' THEN RAISE EXCEPTION 'immutable C0 snapshot pin'; END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER tr_c0_pin BEFORE UPDATE OR DELETE ON analysis_snapshot_registry_pins FOR EACH ROW EXECUTE FUNCTION phase1c0_pin_guard()')
    op.execute("""CREATE FUNCTION phase1c0_pin_order() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.pin_type LIKE 'PHASE1C0_%' AND EXISTS(SELECT 1 FROM analysis_snapshot_registry_pins p
        WHERE p.tenant_id=NEW.tenant_id AND p.analysis_snapshot_id=NEW.analysis_snapshot_id
        AND p.pin_type IN ('PHASE1J_INITIALIZATION','PHASE1C0_INITIALIZATION'))
      THEN RAISE EXCEPTION 'C0 pin set is sealed; new snapshot required'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER tr_c0_pin_order BEFORE INSERT ON analysis_snapshot_registry_pins FOR EACH ROW EXECUTE FUNCTION phase1c0_pin_order()')
    op.execute("""CREATE FUNCTION phase1c0_template_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE pinned boolean;
    BEGIN
      IF TG_TABLE_NAME='template_versions' THEN
        SELECT EXISTS(SELECT 1 FROM analysis_snapshot_registry_pins p WHERE p.tenant_id=OLD.tenant_id AND p.pin_type='PHASE1C0_TEMPLATE' AND p.version_id=OLD.template_version_id) INTO pinned;
        IF pinned AND (TG_OP='DELETE' OR NEW.template_definition_id<>OLD.template_definition_id OR NEW.template_version_id<>OLD.template_version_id OR NEW.tenant_id<>OLD.tenant_id OR NEW.version_no<>OLD.version_no OR NEW.content_ref IS DISTINCT FROM OLD.content_ref OR NEW.field_schema_json::text<>OLD.field_schema_json::text OR NEW.effective_from IS DISTINCT FROM OLD.effective_from OR NEW.effective_to IS DISTINCT FROM OLD.effective_to) THEN RAISE EXCEPTION 'immutable pinned template version'; END IF;
      ELSE
        SELECT EXISTS(SELECT 1 FROM analysis_snapshot_registry_pins p WHERE p.tenant_id=OLD.tenant_id AND p.pin_type='PHASE1C0_TEMPLATE' AND p.object_id=OLD.template_binding_id) INTO pinned;
        IF pinned AND (TG_OP='DELETE' OR NEW.template_version_id<>OLD.template_version_id OR NEW.binding_type<>OLD.binding_type OR NEW.binding_ref<>OLD.binding_ref OR NEW.tenant_id<>OLD.tenant_id OR NEW.effective_from IS DISTINCT FROM OLD.effective_from OR NEW.effective_to IS DISTINCT FROM OLD.effective_to) THEN RAISE EXCEPTION 'immutable pinned template binding'; END IF;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$""")
    for name in ('template_versions','template_bindings'):
        op.execute(f'CREATE TRIGGER tr_c0_template BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION phase1c0_template_guard()')

def downgrade():
    connection=op.get_bind()
    if any(connection.scalar(text('SELECT EXISTS(SELECT 1 FROM '+t+')')) for t in TABLES.values()) or connection.scalar(text("SELECT EXISTS(SELECT 1 FROM analysis_snapshot_registry_pins WHERE pin_type LIKE 'PHASE1C0_%')")) or connection.scalar(text(f"SELECT EXISTS(SELECT 1 FROM metadata_versions v JOIN metadata_definitions d ON d.definition_id=v.definition_id WHERE d.kind IN ({POLICIES}))")):
        raise RuntimeError('C0 authoritative/configuration data retained; archive/export required')
    for name,trigger in [('metadata_definitions','tr_c0_policy'),('metadata_versions','tr_c0_policy'),('analysis_snapshot_registry_pins','tr_c0_pin'),('analysis_snapshot_registry_pins','tr_c0_pin_order'),('template_versions','tr_c0_template'),('template_bindings','tr_c0_template')]:op.execute(f'DROP TRIGGER {trigger} ON {name}')
    for name in reversed(tuple(TABLES.values())):op.execute('DROP TABLE '+name)
    for function in ('phase1c0_result_guard','phase1c0_policy_guard','phase1c0_pin_guard','phase1c0_pin_order','phase1c0_template_guard'):op.execute(f'DROP FUNCTION {function}()')
    request_scope(J_TABLES)
