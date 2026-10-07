"""Fresh/exact verified0011/legacy0012 PostgreSQL temporal migration paths."""
import json
import os
import subprocess
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_phase1h_migrations import migrate
from test_m2a_migrations import catalog
from test_phase1j_migrations import seed_scope
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence import context_models as e, models as b

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
BASE = 'da2d420602d9c71991bcae4ffd3d33c9b3497d25'
HEAD = '0013_m2b_context_temporal_contract'


def complete_catalog(url):
    result = catalog(url)
    with create_engine(url).connect() as conn:
        result['m2b_functions'] = conn.execute(text("SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' AND proname LIKE 'm2b_%' ORDER BY proname")).all()
    return result


def test_fresh_exact_0011_equivalence_empty_down_up_and_retention(tmp_path):
    source = tmp_path / 'verified0011'; source.mkdir()
    archive = tmp_path / 'source.tar'
    with archive.open('wb') as out:
        subprocess.run(['git','archive','--format=tar',BASE],cwd=ROOT,stdout=out,check=True)
    with tarfile.open(archive) as tar: tar.extractall(source, filter='data')
    baseurl = make_url(get_settings().database_url)
    admin = create_engine(baseurl.set(database='postgres'), isolation_level='AUTOCOMMIT')
    names = ['m2b_migration_'+uuid4().hex for _ in range(2)]
    urls = [baseurl.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = dict(base_sha=BASE, from_revision='0011_m2a_intake', head=HEAD)
    try:
        with admin.connect() as conn:
            for n in names: conn.execute(text('CREATE DATABASE "'+n+'"'))
        fresh = migrate(ROOT,urls[0],'upgrade','head'); assert fresh.returncode == 0, fresh.stderr
        frozen = migrate(source,urls[1],'upgrade','head'); assert frozen.returncode == 0, frozen.stderr
        with create_engine(urls[1]).connect() as conn:
            assert conn.scalar(text('SELECT version_num FROM alembic_version')) == '0011_m2a_intake'
        up = migrate(ROOT,urls[1],'upgrade','head'); assert up.returncode == 0, up.stderr
        assert complete_catalog(urls[0]) == complete_catalog(urls[1])
        evidence.update(fresh=True, exact_0011_upgrade=True, schema_equivalence=True)
        for url in urls:
            down = migrate(ROOT,url,'downgrade','0011_m2a_intake'); assert down.returncode == 0, down.stderr
            up = migrate(ROOT,url,'upgrade','head'); assert up.returncode == 0, up.stderr
        assert complete_catalog(urls[0]) == complete_catalog(urls[1])
        evidence['empty_downgrade_reupgrade'] = True
        engine,sf,ids = seed_scope(urls[0]); tenant,project,_,_,_ = ids
        item = str(uuid4())
        with sf() as s,s.begin():
            s.add(b.DataItemEntity(data_item_id=item,tenant_id=tenant,project_id=project,name='Retained')); s.flush()
            s.add(e.DataItemResolutionDetailEntity(data_item_id=item,tenant_id=tenant,version=1,display_name='Retained',confidence=1,validation_status='VALIDATED'))
        before = complete_catalog(urls[0])
        refusal = migrate(ROOT,urls[0],'downgrade','0011_m2a_intake')
        assert refusal.returncode != 0 and 'archive/export' in refusal.stderr
        with engine.connect() as conn: assert conn.scalar(text('SELECT version_num FROM alembic_version')) == HEAD
        assert complete_catalog(urls[0]) == before
        evidence['authoritative_data_transactional_refusal'] = True
        engine.dispose()
        output = Path(os.getenv('EVIDENCE_DIR',str(ROOT/'artifacts/m2b'))); output.mkdir(parents=True,exist_ok=True)
        (output/'m2b_migration_dual_path.json').write_text(json.dumps(evidence,indent=2)+'\n')
    finally:
        with admin.connect() as conn:
            for n in names:
                conn.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n'),{'n':n})
                conn.execute(text('DROP DATABASE IF EXISTS "'+n+'"'))
        admin.dispose()



def test_exact_legacy_0012_preserves_real_detail_and_quarantines_unproven_links(tmp_path):
    source=tmp_path/'legacy0012'; source.mkdir(); archive=tmp_path/'source.tar'
    with archive.open('wb') as out: subprocess.run(['git','archive','--format=tar','d78c310137415c6b06c8b0f7e945b4ed65820ab3'],cwd=ROOT,stdout=out,check=True)
    with tarfile.open(archive) as tar: tar.extractall(source,filter='data')
    baseurl=make_url(get_settings().database_url); name='m2b_legacy_'+uuid4().hex
    url=baseurl.set(database=name).render_as_string(hide_password=False)
    admin=create_engine(baseurl.set(database='postgres'),isolation_level='AUTOCOMMIT')
    try:
        with admin.connect() as conn: conn.execute(text('CREATE DATABASE "'+name+'"'))
        old=migrate(source,url,'upgrade','head'); assert old.returncode==0,old.stderr
        env={**os.environ,'DATABASE_URL':url,'PYTHONPATH':str(source/'src')+os.pathsep+str(source/'tests')+os.pathsep+str(source)}
        seed=subprocess.run([__import__('sys').executable,str(ROOT/'tests/m2b_legacy_seed.py')],cwd=source,env=env,capture_output=True,text=True)
        assert seed.returncode==0,seed.stderr
        measured=json.loads(seed.stdout.strip().splitlines()[-1])
        upgraded=migrate(ROOT,url,'upgrade','head'); assert upgraded.returncode==0,upgraded.stderr
        with create_engine(url).connect() as conn:
            assert [list(x) for x in conn.execute(text('SELECT data_item_id,version,display_name FROM data_item_resolution_details ORDER BY data_item_id'))]==measured['details']
            for table in ('data_item_candidate_links','data_item_source_trace_links'):
                rows=conn.execute(text('SELECT data_item_id,data_inventory_version FROM '+table)).all()
                assert rows and any(v==1 for _,v in rows)
                assert all(v is None if item==measured['unknown_item'] else v==1 for item,v in rows)
            assert conn.scalar(text('SELECT version_num FROM alembic_version'))==HEAD
    finally:
        with admin.connect() as conn:
            conn.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n'),{'n':name})
            conn.execute(text('DROP DATABASE IF EXISTS "'+name+'"'))
        admin.dispose()
