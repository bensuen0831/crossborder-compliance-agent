import json,subprocess,hashlib,os
from pathlib import Path
from alembic.script import ScriptDirectory
R=Path('/workspace/crossborder-compliance-agent');P=Path('/workspace/m2e-main-control');os.chdir(R)
def git(*a):return subprocess.check_output(['git',*a],text=True).strip()
i=json.loads((P/'main-identity.json').read_text());sha=i['sha'];base=i['base'];head=i['source_head']
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==sha
assert git('rev-parse',sha+'^{tree}')==git('rev-parse',head+'^{tree}')
assert not git('status','--porcelain')
subprocess.run(['git','merge-base','--is-ancestor',head,sha],check=True)
assert git('show','-s','--format=%P',sha).split()==[base,head]
s=ScriptDirectory('alembic');assert s.get_heads()==['0018_phase1h_multijurisdiction_classification_identity']
assert s.get_revision(s.get_heads()[0]).down_revision=='0017_m2e_external_agent_api'
assert s.get_revision('0017_m2e_external_agent_api').down_revision=='0016_phase1kb_multi_provider_llm_governance'
frozen={}
for path in git('ls-tree','-r','--name-only',base,'--','alembic/versions').splitlines():
 old=subprocess.check_output(['git','show',base+':'+path]);assert (R/path).read_bytes()==old;frozen[path]=hashlib.sha256(old).hexdigest()
assert len(frozen)==16
out=P/'local-source';out.mkdir(exist_ok=True);architecture={}
for name in ['architecture_rule_check.py','m2a_architecture_check.py','m2b_architecture_check.py','m2c_architecture_check.py','m2c_projection_architecture.py','m2d_architecture_check.py','phase1kb_architecture_check.py','m2e_r1_architecture_check.py','m2e_architecture_check.py']:
 raw=subprocess.check_output(['python','scripts/'+name],text=True);(out/(name+'.json')).write_text(raw);d=json.loads(raw);assert d['passed']==d['total'];checks=d['checks'];assert all(v is True for v in checks.values()) if isinstance(checks,dict) else all(v['pass'] is True for v in checks);architecture[name]=d['passed']
assert sum(architecture.values())>=307
subprocess.run(['git','diff','--check'],check=True)
diff=subprocess.run(['git','diff','--check',base,sha],text=True,capture_output=True);(out/'baseline-diff-check.txt').write_text(diff.stdout+diff.stderr)
summary={'tested_main_sha':sha,'merge_parents':[base,head],'source_head_ancestor':True,'source_tree_equals_tested_pr':True,'tracked_and_untracked_clean_at_validation':True,'single_alembic_head':s.get_heads()[0],'migration_lineage':['0016_phase1kb_multi_provider_llm_governance','0017_m2e_external_agent_api',s.get_heads()[0]],'frozen_0001_0016_byte_identity':True,'frozen_digests':frozen,'architecture':architecture,'total':sum(architecture.values()),'working_tree_diff_check':True,'baseline_diff_check_exit':diff.returncode,'baseline_diff_check_output':diff.stdout+diff.stderr}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
