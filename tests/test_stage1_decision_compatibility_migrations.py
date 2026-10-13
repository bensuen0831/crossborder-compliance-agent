"""Only five CHECK changes; genuine V2 preservation and V2_1 downgrade refusal."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from stage1_legacy_history import SOURCE,prior_source,produce_decisions
from test_m2b_migrations import complete_catalog
from test_phase1h_migrations import migrate
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.decision_models import TABLES

pytestmark=pytest.mark.runtime_smoke
ROOT=Path(__file__).resolve().parents[1]
HEAD='0020_stage1_formal_decision_engine_compatibility'
PARENT='0019_stage1_candidate_governance'

def fingerprint(url,record):
    engine=create_engine(url)
    try:
        with engine.connect() as c:
            return {kind:hashlib.sha256(json.dumps(dict(c.execute(text(f'SELECT * FROM {TABLES[kind]} WHERE result_id=:id'),{'id':ident}).mappings().one()),sort_keys=True,default=str).encode()).hexdigest()
                for kind,ident in record['results'].items()}
    finally:engine.dispose()

def test_frozen_0001_0019_and_exact_single_head():
    script=ScriptDirectory.from_config(Config(str(ROOT/'alembic.ini')))
    assert script.get_heads()==[HEAD]
    assert script.get_revision(HEAD).down_revision==PARENT
    for path in (ROOT/'alembic/versions').glob('*.py'):
        if path.name[:4].isdigit() and int(path.name[:4])<=19:
            assert path.read_bytes()==subprocess.check_output(['git','show',SOURCE+':'+str(path.relative_to(ROOT))],cwd=ROOT)

def test_fresh_exact0019_equivalence_preservation_downgrade_and_reupgrade(tmp_path):
    base=make_url(get_settings().database_url)
    admin=create_engine(base.set(database='postgres'),isolation_level='AUTOCOMMIT')
    names=['compat20_'+uuid4().hex for _ in range(2)]
    urls=[base.set(database=name).render_as_string(hide_password=False) for name in names]
    measured={'migration_head':HEAD,'parent':PARENT,'knowledge_fixture_kind':'SYNTHETIC_GOVERNED_TEST_DATA'}
    try:
        with admin.connect() as c:
            for name in names:c.execute(text('CREATE DATABASE "'+name+'"'))
        assert migrate(ROOT,urls[0],'upgrade',HEAD).returncode==0
        original=prior_source(tmp_path/'frozen0019')
        assert migrate(original,urls[1],'upgrade','head').returncode==0
        legacy=produce_decisions(original,database_url=urls[1]);assert legacy['engine_version']=='FORMAL_DECISION_V2'
        before=fingerprint(urls[1],legacy)
        assert migrate(ROOT,urls[1],'upgrade',HEAD).returncode==0
        assert fingerprint(urls[1],legacy)==before
        assert complete_catalog(urls[0])==complete_catalog(urls[1])
        for url in urls:
            assert migrate(ROOT,url,'downgrade',PARENT).returncode==0
            assert migrate(ROOT,url,'upgrade',HEAD).returncode==0
        assert fingerprint(urls[1],legacy)==before
        current=produce_decisions(ROOT,database_url=urls[1]);assert current['engine_version']=='FORMAL_DECISION_V2_1'
        saved=fingerprint(urls[1],current);schema=complete_catalog(urls[1])
        refusal=migrate(ROOT,urls[1],'downgrade',PARENT)
        assert refusal.returncode and 'STAGE1_FORMAL_DECISION_COMPATIBILITY_DOWNGRADE_REFUSED' in refusal.stderr
        assert complete_catalog(urls[1])==schema
        assert fingerprint(urls[1],legacy)==before and fingerprint(urls[1],current)==saved
        measured.update(fresh=True,exact0019_upgrade=True,schema_equivalence=True,legacy_rows_preserved=True,
            empty_and_legacy_safe_downgrade=True,reupgrade=True,current_rows_downgrade_refused=True,
            no_data_rewritten=True,legacy_row_digests=before,current_row_digests=saved)
        out=Path(os.getenv('EVIDENCE_DIR','artifacts/stage1-r2'));out.mkdir(parents=True,exist_ok=True)
        (out/'decision_compatibility_migration_measured.json').write_text(json.dumps(measured,indent=2)+'\n')
    finally:
        with admin.connect() as c:
            for name in names:
                c.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name'),{'name':name})
                c.execute(text('DROP DATABASE IF EXISTS "'+name+'"'))
        admin.dispose()
