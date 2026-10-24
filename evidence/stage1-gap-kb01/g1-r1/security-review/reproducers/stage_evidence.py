import hashlib,json,pathlib,shutil,subprocess
R=pathlib.Path('/workspace/kb01-security-final-733a748');O=R/'handover';W=pathlib.Path('/workspace/kb01-final-review-evidence');S='733a7483439cd919c186ed0064b8f3752904ebb6'
def git(*args):return subprocess.check_output(['git',*args],cwd=W)
assert git('rev-parse','HEAD').decode().strip()==S
assert not git('status','--porcelain=v1').strip()
index=json.loads((O/'evidence/stage1-gap-kb01/g1-r1/security-review/evidence_digests.json').read_text())
for p in sorted(O.rglob('*')):
 if p.is_file():
  dst=W/p.relative_to(O);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
paths=sorted(str(p.relative_to(O)) for p in O.rglob('*') if p.is_file())
# Add only selected safe docs/evidence; explicitly handle exact safe paths ignored by old generic rules.
ignored=[]
for path in paths:
 assert path.startswith(('docs/','evidence/'))
 if subprocess.run(['git','check-ignore','-q','--',path],cwd=W).returncode==0:
  ignored.append(path);subprocess.run(['git','add','-f','--',path],cwd=W,check=True)
 else:subprocess.run(['git','add','--',path],cwd=W,check=True)
for path,digest in index['files'].items():assert hashlib.sha256(git('show',':'+path)).hexdigest()==digest,path
staged=git('diff','--cached','--name-only').decode().splitlines();assert staged and all(p.startswith(('docs/','evidence/')) for p in staged)
subprocess.run(['git','diff','--cached','--check'],cwd=W,check=True)
result={'product_head':S,'evidence_branch':git('branch','--show-current').decode().strip(),'staged_paths':staged,'all_manifest_git_index_blobs_verified':len(index['files']),'exact_safe_ignored_paths_explicitly_added':ignored,'source_changes':False}
(R/'evidence-staging-validation.json').write_text(json.dumps(result,indent=2)+'\n');print('Staged evidence only',len(staged),'paths; verified Git index',len(index['files']),'hashes; exact ignored paths',ignored)
