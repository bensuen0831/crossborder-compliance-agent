"""Genuine prior-revision authority created by its original PostgreSQL owners."""
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

SOURCE='4c79243bbfa22108f1005c8e92265e2137012d4d'
ROOT=Path(__file__).resolve().parents[1]

def prior_source(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    archive=subprocess.check_output(['git','archive',SOURCE],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as files:files.extractall(folder,filter='data')
    return folder

def produce_decisions(source_root, *, database_url=None):
    source_root=Path(source_root)
    env={**os.environ,'PYTHONPATH':str(source_root/'src')+os.pathsep+str(source_root)+os.pathsep+str(source_root/'tests')}
    if database_url:env['DATABASE_URL']=database_url
    script='''
import json
from types import SimpleNamespace
from test_phase1j_postgres import fixture,foundation_i,foundation_j,run_pipeline
f=foundation_i.__wrapped__(fixture.__wrapped__(),SimpleNamespace(param={}))
f=foundation_j.__wrapped__(f,SimpleNamespace(param={}))
results,_=run_pipeline(f)
for kind,result in results.items():
    assert f['jrepo'].read_decision(kind,result.result_id)==result
print(json.dumps(dict(tenant=f['tenant'],project=f['project'],snapshot=f['snapshot'],actor=f['jctx'].permission.actor_id,scopes=sorted(f['jctx'].permission.scopes),results={k:str(v.result_id) for k,v in results.items()},engine_version=str(results['FINAL_PATH'].engine_version))))
'''
    process=subprocess.run([sys.executable,'-c',script],cwd=source_root,env=env,capture_output=True,text=True)
    if process.returncode:
        diagnostic=Path(os.getenv('STAGE1_PRIVATE_DIAGNOSTICS','/tmp'))/'stage1-owner-subprocess-error.txt'
        diagnostic.write_text(process.stderr);diagnostic.chmod(0o600)
        raise AssertionError('Prior-source owner subprocess failed; inspect private diagnostic locally')
    return json.loads(process.stdout.splitlines()[-1])
