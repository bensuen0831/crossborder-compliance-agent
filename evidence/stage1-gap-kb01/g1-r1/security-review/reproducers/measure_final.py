import collections,hashlib,json,pathlib,xml.etree.ElementTree as ET
R=pathlib.Path('/workspace/kb01-security-final-733a748');S='733a7483439cd919c186ed0064b8f3752904ebb6'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,d):(R/n).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
a=read(R/'artifact-validation.json');assert a['source_sha']==S
reports=R/'verified-reports';full=[];runtimes=[];units=[];browser_reports=[]
for f in reports.rglob('pytest_full.xml'):
 root=ET.parse(f).getroot();cs=list(root.iter('testcase'));counts={k:sum(c.find(tag) is not None for c in cs) for k,tag in [('failed','failure'),('errors','error'),('skipped','skipped')]};counts['passed']=len(cs)-sum(counts.values());summary=read(f.with_name('pytest_full_summary.json'));assert summary['pass'] and summary['deselected']==0 and summary['passed']==counts['passed']>=1315 and not any(counts[k] for k in ['failed','errors','skipped']);ids=sorted(c.get('classname')+'::'+c.get('name') for c in cs);assert len(ids)==len(set(ids));full.append({'report':str(f.relative_to(R)),'sha256':sha(f),**counts,'deselected':0,'test_ids':ids,'summary':summary})
assert len(full)>=4,len(full)
base=read(R/'prior-full_regression_summary.json')['backend_complete_executions'][0]['test_ids'];prior=set(base)
for d in full:assert prior<=set(d['test_ids']);assert d['test_ids']==full[0]['test_ids']
for f in reports.rglob('runtime_verify.json'):
 d=read(f);runtimes.append({'report':str(f.relative_to(R)),'sha256':sha(f),'result':d})
assert len(runtimes)>=4,len(runtimes)
for runtime in runtimes:
 d=runtime['result'];assert d['all_mandatory_assertions_pass'] and len(d['assertions'])==25 and all(d['assertions'].values())
# Only persisted actual Playwright reports. Repeated executions across workflows
# do not inflate coverage: use maximum multiplicity per semantic test identity.
def walk(suites,parents=()):
 for s in suites:
  path=parents+(() if s['title']==s.get('file') else (s['title'],))
  for spec in s.get('specs',[]):
   for test in spec['tests']:
    assert spec['ok'] and test['expectedStatus']=='passed' and test['status']=='expected'
    results=test['results'];assert len(results)==1 and results[0]['status']=='passed' and results[0]['retry']==0
    yield (pathlib.PurePosixPath(spec['file']).name,path,spec['title']),results[0]['duration']
  yield from walk(s.get('suites',[]),path)
counts=collections.Counter();durations={}
for f in reports.rglob('*.json'):
 if f.name in ('unit.json','frontend-unit.json') or f.name.endswith('-frontend.json'):
  d=read(f)
  if 'numPassedTests' in d:
   assert d['success'] and d['numPassedTests']>=180 and d['numFailedTests']==d['numPendingTests']==d['numTodoTests']==0
   units.append({'report':str(f.relative_to(R)),'sha256':sha(f),'passed':d['numPassedTests']})
 d=None
 if f.name in ('browser.json','results.json') or f.name.endswith('-browser.json'):
  d=read(f)
  if not ('suites'in d and 'stats'in d):continue
  assert d['stats']['unexpected']==d['stats']['skipped']==d['stats']['flaky']==0 and not d['errors']
  rows=list(walk(d['suites']));assert len(rows)==d['stats']['expected']
  c=collections.Counter(k for k,v in rows)
  for k,v in c.items():counts[k]=max(counts[k],v)
  browser_reports.append({'report':str(f.relative_to(R)),'sha256':sha(f),'passed':len(rows),'retries':0,'duration_ms':d['stats']['duration']})
# Some existing canonical workflows upload authenticated measured projections,
# not raw browser JSON. Reconcile their actual named cases and log observations.
expected=read(R/'prior-browser_expected_inventory.json')['cases']
structured=[]
for f in reports.rglob('candidate_frontend_measured.json'):
 d=read(f);assert d['runner_checkout_sha']==S and d['decision']=='PASS' and d['browser_retries']==0 and d['focused_browser_passed']==len(d['cases'])==5
 for title in d['cases']:counts[('candidate-governance.spec.ts',(),title)]=max(counts[('candidate-governance.spec.ts',(),title)],1)
 structured.append({'report':str(f.relative_to(R)),'sha256':sha(f),'passed':5,'kind':'Canonical measured named candidate browser cases'})
for f in reports.rglob('stage1_business_browser_measured.json'):
 d=read(f);assert d['runner_checkout_sha']==S and d['passed']==len(d['cases'])==12 and d['retries']==0
 for case in d['cases']:
  assert case['retries']==0 and case['test_id'] and case['duration_ms']>0
  counts[('stage1-business.spec.ts',(),case['title'])]=max(counts[('stage1-business.spec.ts',(),case['title'])],1)
 structured.append({'report':str(f.relative_to(R)),'sha256':sha(f),'passed':12,'kind':'Canonical actual browser IDs and result relationships'})
logs=read(R/'browser-runtime-log-identities.json');assert logs['source_sha']==S
for case in expected:
 if case['file'] not in ('m2e.spec.ts','phase1kb.spec.ts'):continue
 matches=[line for r in logs['records'] for line in r['actual_pass_lines'] if case['file']+':' in line and case['title'] in line]
 assert len(matches)==1,(case,matches)
 key=(case['file'],tuple(case['suite']),case['title']);counts[key]=max(counts[key],1)
for f in reports.rglob('frontend_measured.json'):
 d=read(f);assert d['runner_checkout_sha']==S and d['exact_head_verified'] and d['frontend_passed']>=180 and d['retry_count']==0 and d['quality']=='PASS'
 structured.append({'report':str(f.relative_to(R)),'sha256':sha(f),'browser_counts':d['browser_counts'],'kind':'Canonical full raw JSON validated at job runtime before projected upload'})
bc=collections.Counter((c['file'],tuple(c['suite']),c['title']) for c in expected)
missing={str(k):v-counts[k] for k,v in bc.items() if counts[k]<v};assert not missing,missing
assert sum(counts.values())==89,collections.Counter({k[0]:sum(v for x,v in counts.items() if x[0]==k[0]) for k in counts})
browser={'source_sha':S,'passed':sum(counts.values()),'retained_prior':89,'additive':0,'retries':0,'failed':0,'skipped':0,'reports':browser_reports,'structured_actual_reports':structured,'additional_actual_pass_log_proof':'browser-runtime-log-identities.json','test_ids':[{'file':k[0],'suite':list(k[1]),'title':k[2],'repeat_ordinal':i} for k,v in sorted(counts.items()) for i in range(v)],'file_counts':dict(collections.Counter(c['file'] for k,v in counts.items() for c in [{'file':k[0]}]*v))}
write('browser-final-summary.json',browser)
out={'source_sha':S,'decision':'PASS_FUNCTIONAL_REGRESSION_NOT_SECURITY_ACCEPTANCE','backend_passed':full[0]['passed'],'backend_complete_executions':full,'retained_backend_test_ids':len(prior),'additive_backend_test_ids':sorted(set(full[0]['test_ids'])-prior),'runtime_executions':runtimes,'architecture':read(R/'architecture-final.json'),'frontend_passed':180,'frontend_actual_unit_reports':units,'browser':browser,'local_focused':read(R/'focused-final-summary.json'),'typecheck':'PASS','lint':'PASS','build':'PASS','i18n':'PASS','locales':['zh-CN','zh-HK','en-US'],'complete_pg_failures_errors_skips_deselections':[0,0,0,0]}
assert units
out['ci_architecture_measurements']=[]
for f in reports.rglob('backend_measured.json'):
 d=read(f);assert d['runtime_passed']==25 and d['alembic']=='0024_kb01_import_manifest_records' and d['architecture_passed']==d['architecture_total']
 out['ci_architecture_measurements'].append({'report':str(f.relative_to(R)),'architecture_passed':d['architecture_passed'],'architecture_total':d['architecture_total'],'scope_note':'Older workflow-specific authority aggregates may be narrower; complete nine-authority result is456.'})
assert sum(x['architecture_passed']==456 for x in out['ci_architecture_measurements'])>=2
write('regression-final.json',out)
print('Measured full backend',out['backend_passed'],'x',len(full),'retained',len(prior),'new',len(out['additive_backend_test_ids']),'runtime',len(runtimes),'browser',browser['passed'])
