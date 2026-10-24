import hashlib,json,pathlib,subprocess,types
from types import SimpleNamespace
ROOT=pathlib.Path('/workspace/crossborder-compliance-agent');R=pathlib.Path('/workspace/kb01-security-final-733a748');state=R/'cached-proof-counterexample';state.mkdir(exist_ok=True,mode=0o700)
old_proof=json.loads(pathlib.Path('/workspace/kb01-g1r1/new-tool-image.json').read_text());(state/'tool-image.json').write_text(json.dumps(old_proof));actual=hashlib.sha256((ROOT/'scripts/kb01/Containerfile').read_bytes()).hexdigest();assert old_proof['containerfile_sha256']!=actual
class MutationBarrier(Exception):pass

def execute(source,label):
 mod=types.ModuleType('rc1_boundary_'+label);mod.__file__=str(ROOT/'scripts/kb01/rc1.py');exec(compile(source,mod.__file__,'exec'),mod.__dict__);mod.ROOT=ROOT
 cfg=mod.settings(pathlib.Path('/workspace/kb01-rc1'));mod.health=lambda:{'backend':{'status':0},'frontend':{'status':0}};mod.containers=lambda *a:None
 def barrier(root,env,name,cmd):
  assert name=='migration';raise MutationBarrier('Source/provenance validation accepted; stop before any migration/workers')
 mod.run=barrier
 try:mod.start(state,cfg,SimpleNamespace(tool_evidence=None))
 except MutationBarrier:return {'source_variant':label,'cached_mismatched_source_accepted':True,'stopped_before_mutation':True}
 except RuntimeError as e:
  assert str(e)=='RC1_TOOL_SOURCE_MISMATCH';return {'source_variant':label,'cached_mismatched_source_accepted':False,'stable_error':str(e),'stopped_before_mutation':True}
 raise AssertionError('No mutation barrier or rejection')
old_source=subprocess.check_output(['git','show','b9f22415d3f40cf87a6957b93bb6301b602a3733:scripts/kb01/rc1.py'],cwd=ROOT,text=True);results=[execute(old_source,'trusted_B9_before')]
if '--after' in __import__('sys').argv:results.append(execute((ROOT/'scripts/kb01/rc1.py').read_text(),'working_fixed_after'))
out={'source_after':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_before':'b9f22415d3f40cf87a6957b93bb6301b602a3733','original_proof_image':old_proof['image_id'],'cached_containerfile_sha256':old_proof['containerfile_sha256'],'current_containerfile_sha256':actual,'method':'Execute exact trusted committed old start and current start; only health/owned-container startup are stubbed; real readonly PG connect and Redis ping retained; sentinel stops before migration or worker mutation. Not a production pass fixture.','results':results};(R/'cached-source-counterexample.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
