import collections,hashlib,json,pathlib,re,subprocess
R=pathlib.Path('/workspace/kb01-security-final-733a748');O=R/'handover';E=O/'evidence/stage1-gap-kb01/g1-r1/security-review';ROOT=pathlib.Path('/workspace/crossborder-compliance-agent');S='733a7483439cd919c186ed0064b8f3752904ebb6'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
index=read(E/'evidence_digests.json');assert index['tested_product_sha']==S
actual={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.name!='evidence_digests.json'};assert actual==index['files'];assert len(actual)==index['file_count']
for p in O.rglob('*.json'):read(p)
secrets=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:postgresql|redis)://[^\s"<>]+:[^\s"<>]+@)')
for p in O.rglob('*'):
 if p.is_file():assert not secrets.search(p.read_bytes()),p
ci=read(E/'ci-complete.json');assert ci['success_workflows']==ci['total_workflows']==12 and ci['verified_job_checkouts']==22
assert all(j['runner_checkout_sha']==S and j['conclusion']=='success' for r in ci['runs'] for j in r['jobs'])
reg=read(E/'regression-final.json');assert reg['backend_passed']==1336 and reg['browser']['passed']==89 and reg['browser']['retries']==0
for x in reg['backend_complete_executions']:assert x['failed']==x['errors']==x['skipped']==x['deselected']==0
ledger=read(E/'security_findings_disposition.json');assert len(ledger['rows'])==135 and len(ledger['new_findings'])==1 and ledger['risk_acceptance'] is None
assert sum(x['technical_status']=='REMOVED_FROM_NEW_IMAGE' for x in ledger['rows'])==5
assert all(x['reviewer_decision']=='PENDING' and x['reviewer_approval_record'] is None for x in ledger['rows'])
assert ledger['new_local_counts']=={'HIGH':130,'CRITICAL':1} and len(ledger['new_head_ci_images'])==7
master=read(E/'master_reconciliation.json');assert master['section_count']==42 and master['repository_master']['line_count']==1000 and master['master_overall_gate'].startswith('BLOCKED')
assert collections.Counter(x['conclusion'] for x in master['all_sections'])=={'已符合':17,'部分符合':13,'不屬本階段':9,'證據不足':3}
source=read(E/'source-identity-final.json');assert source['source_sha']==S
for path,digest in source['source_files'].items():
 raw=subprocess.check_output(['git','show',S+':'+path],cwd=ROOT);assert hashlib.sha256(raw).hexdigest()==digest,path
 # Working product is frozen; evidence branch only changes docs/evidence outside these source paths.
 assert sha(ROOT/path)==digest,path
for p in O.rglob('*'):
 if p.is_file():assert not any(x.endswith('.private.json') or x.endswith('.env') for x in p.parts),p
out={'decision':'PASS_REVIEW_MATERIAL_INTEGRITY_ONLY','source_sha':S,'files_verified':len(actual),'json_files_verified':len(list(O.rglob('*.json'))),'source_files_verified':len(source['source_files']),'formal_review':'PENDING','master_original':'INPUT_REQUIRED','f1':'BLOCKED_EXTERNAL_EVIDENCE_PENDING','secrets_pattern_scan':'NO_MATCH_IN_SELECTED_SAFE_HANDOVER','limitations':'Pattern scan is an engineering safeguard; not formal security approval.'}
(R/'handover-validation.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
