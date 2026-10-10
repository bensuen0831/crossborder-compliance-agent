import pathlib,json,re,xml.etree.ElementTree as ET
P=pathlib.Path('/workspace/m2e-main-control/main-phase1kb-ci');SHA=json.loads(pathlib.Path('/workspace/m2e-main-control/main-identity.json').read_text())['sha']
r=json.loads((P/'run.json').read_text());jobs=json.loads((P/'jobs.json').read_text())['jobs'];assert r['head_sha']==SHA and r['head_branch']=='main' and r['event']=='workflow_dispatch' and r['status']=='completed' and r['conclusion']=='success';assert all(j['conclusion']=='success' for j in jobs)
log=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',(P/'jobs.log').read_text());lines=log.splitlines();proof={}
for n,line in enumerate(lines):
 if 'git log -1 --format=%H' in line:
  value=lines[n+1].split()[-1];assert value==SHA;proof[line.split('\t')[0]]=value
assert set(proof)=={j['name'] for j in jobs}
def read(name):
 paths=list((P/'downloaded').rglob(name));assert len(paths)==1,(name,paths);return json.loads(paths[0].read_text())
b=read('backend_measured.json');f=read('frontend_measured.json')
for d in [b,f]:assert d['tested_pr_head_sha']==d['runner_checkout_sha']==d['final_sha']==SHA and d['exact_head_verified']
assert b['backend']['pass'] and b['backend']['passed']>=910 and all(b['backend'][x]==0 for x in ['failed','errors','skipped','deselected']);assert b['runtime_passed']==25 and b['architecture_passed']==b['architecture_total']>=269
assert f['frontend_passed']>=135 and f['retry_count']==0 and f['quality']=='PASS' and set(f['locales'])=={'zh-CN','zh-HK','en-US'}
assert f['browser_counts']=={'phase1kb.spec.ts':6,'knowledge.spec.ts':36,**{s+'.spec.ts':3 for s in ['m2d','m2c','m2b','m2a','m1']}}
assert sum(f['browser_counts'].values())>=57
m=b['migration'];assert m['head']=='0018_phase1h_multijurisdiction_classification_identity' and m['from_revision']=='0015_m2d_review_governance' and b['alembic']=='0018_phase1h_multijurisdiction_classification_identity';assert all(m[k] for k in ['fresh','exact0015_upgrade','schema_equivalence','frozen_migrations_unchanged','empty_downgrade_reupgrade','authoritative_pins_transactional_refusal'])
xmlpaths=list((P/'downloaded').rglob('pytest_full.xml'));assert len(xmlpaths)==1;cases=list(ET.parse(xmlpaths[0]).getroot().iter('testcase'));assert len(cases)==b['backend']['passed'];assert all(not any(x.tag in ('failure','error','skipped') for x in c) for c in cases)
coverage={}
for prefix in ['test_phase1kb','test_m2b','test_m2d']:
 coverage[prefix]=[c.attrib for c in cases if prefix in c.get('classname','')];assert coverage[prefix]
for preset in ['OPENAI_GPT','DEEPSEEK','QWEN','GLM','OTHER_OPENAI_COMPATIBLE']:
 assert any(c.get('name')=='test_presets_real_http_same_protocol_no_business_branch['+preset+']' for c in cases)
required=['test_selection_through_real_two_provider_http_and_durable_audit','test_encrypted_not_plaintext_reference_scope_and_restart','test_confirmation_freezes_exact_models_policies_prompt_and_preferences','test_real_binary_llm_candidates_genuine_trace_resolution_and_restart','test_real_http_query_expansion_same_scope_and_no_model_memory_evidence','test_stable_item_has_exact_immutable_snapshot_state_and_provenance','test_approval_reexecutes_owner_duplicate_identity_and_history','test_request_changes_history_no_resume_and_duplicate_cas','test_fact_choice_creates_successor_keeps_source_and_exact_parse_universe','test_concurrent_reviewers_one_cas_winner','test_approval_process_restart_keeps_canonical_history_and_checkpoint','test_historical_snapshot_model_and_prompt_do_not_use_new_versions','test_review_successor_preserves_original_model_frame','test_single_current_revocation_denied_without_other_provider_fallback','test_multiple_provider_instances_multiple_models_same_remote_name','test_legal_purpose_not_in_contract_or_multi_vote','test_current_authorization_and_cross_tenant_fail_closed','test_published_model_configuration_is_immutable']
for name in required:assert any(c.get('name','').split('[',1)[0]==name for c in cases),name
runtime=read('runtime_verify.json');assert runtime['all_mandatory_assertions_pass'] and len(runtime['assertions'])==25 and all(runtime['assertions'].values())
architecture={}
for name in ['architecture_rule_check_stdout.json','m2a_architecture_check.json','m2b_architecture_check.json','m2c_architecture.json','m2c_projection_architecture.json','m2d_architecture.json','phase1kb_architecture.json']:
 a=read(name);assert a['passed']==a['total'];checks=a['checks'];assert all(v is True for v in checks.values()) if isinstance(checks,dict) else all(v['pass'] is True for v in checks);architecture[name]=a
assert sum(a['passed'] for a in architecture.values())>=269
for job in jobs:
 if job['name']=='canonical-frontend-browser':
  for name in ['Canonical generated contracts, full frontend regression and quality','Admin/user three-locale smoke and M2-D/C/B/A/M1 regressions, zero retries','Original M0 insufficient-evidence fixture and 36-test matrix, zero retries','Exact-head frontend/browser measurement, no credentials archived']:
   assert any(x['name']==name and x['conclusion']=='success' for x in job['steps']),name
unit=re.findall(r'\bTests\s+(\d+) passed\s*\((\d+)\)',log);assert unit and all(int(a)==int(c)>=135 for a,c in unit)
assert '21 passed' in log and '36 passed' in log
result=dict(run_id=r['id'],url=r['html_url'],workflow=r['name'],tested_main_sha=SHA,runner_checkout_sha=SHA,checkout_jobs=proof,backend=b,frontend=f,runtime=runtime,architecture=architecture,migration=m,test_case_coverage=coverage,required_semantic_cases=required,provider_protocol_acceptance='PASS',paid_internet_endpoints='NOT_EXECUTED',m2b_temporal='PASS',m2d_review='PASS',browser_passed=sum(f['browser_counts'].values()),browser_retries=0)
(P/'measured-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(run_id=r['id'],backend=b['backend']['passed'],architecture=b['architecture_passed'],frontend=f['frontend_passed'],browser=sum(f['browser_counts'].values()),retries=0,checkout_jobs=proof)))
