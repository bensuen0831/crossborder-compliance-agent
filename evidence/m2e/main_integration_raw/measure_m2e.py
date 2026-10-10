import json,re,xml.etree.ElementTree as ET
from pathlib import Path
P=Path('/workspace/m2e-main-control/main-m2e-ci');SHA=json.loads(Path('/workspace/m2e-main-control/main-identity.json').read_text())['sha']
r=json.loads((P/'run.json').read_text());jobs=json.loads((P/'jobs.json').read_text())['jobs']
assert r['head_sha']==SHA and r['head_branch']=='main' and r['event']=='workflow_dispatch' and r['status']=='completed' and r['conclusion']=='success'
assert jobs and all(j['conclusion']=='success' for j in jobs)
log=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',(P/'jobs.log').read_text());lines=log.splitlines();proof={}
for n,line in enumerate(lines):
 if 'git log -1 --format=%H' in line:
  value=lines[n+1].split()[-1];assert value==SHA;proof[line.split('\t')[0]]=value
assert set(proof)=={j['name'] for j in jobs}
def read(name):
 paths=list((P/'downloaded').rglob(name));assert len(paths)==1,(name,paths);return json.loads(paths[0].read_text())
b=read('backend_measured.json');f=read('frontend_measured.json');m=read('migration_validation.json');security=read('security_validation.json')
for d in [b,f,m,security]:assert d['tested_pr_head_sha']==d['runner_checkout_sha']==d['final_sha']==SHA and d['exact_head_verified']
assert b['backend']['pass'] and b['backend']['passed']>=910 and all(b['backend'][x]==0 for x in ['failed','errors','skipped','deselected'])
assert b['runtime_passed']==25 and b['architecture_passed']==b['architecture_total']>=307
assert b['alembic']=='0018_phase1h_multijurisdiction_classification_identity'
assert f['frontend_passed']>=135 and f['retry_count']==0 and f['quality']=='PASS' and set(f['locales'])=={'zh-CN','zh-HK','en-US'}
counts={'phase1kb.spec.ts':6,'m2e.spec.ts':3,'knowledge.spec.ts':36,**{s+'.spec.ts':3 for s in ['m2d','m2c','m2b','m2a','m1']}}
assert f['browser_counts']==counts and sum(counts.values())==60
mc=m['classification'];assert m['pass'] and mc['migration']==b['alembic'] and mc['parent']=='0017_m2e_external_agent_api'
for k in ['fresh','exact0016_to0017_to0018','exact0017_upgrade','schema_equivalence','legacy_row_and_digest_unchanged','safe_downgrade','reupgrade','two_jurisdictions_persist','same_jurisdiction_duplicate_rejected','unsafe_downgrade_transactionally_refused','predicate_unchanged','frozen_0001_0016','unchanged_0017']:assert mc[k],k
assert len(mc['frozen_digests'])==17 and m['integration'] and all(m['integration'].values())
xmls=list((P/'downloaded').rglob('pytest_full.xml'));assert len(xmls)==1;cases=list(ET.parse(xmls[0]).getroot().iter('testcase'));assert len(cases)==b['backend']['passed'] and all(not any(x.tag in ('failure','error','skipped') for x in c) for c in cases)
coverage={}
for prefix in ['test_m2e','test_phase1kb','test_m2b','test_m2c','test_m2d']:
 coverage[prefix]=[c.attrib for c in cases if prefix in c.get('classname','')];assert coverage[prefix]
assert len(coverage['test_m2e'])>=66 and security['pass'] and security['passed_m2e_tests']==len(coverage['test_m2e']) and security['paid_internet_llm']=='NOT EXECUTED'
required=['test_oauth_live_scopes_hashed_credentials_and_no_get_secret','test_token_revalidates_current_authority','test_service_account_same_context_revocable_no_global_authority','test_binding_fail_closed_cross_client_and_tenant','test_admin_idempotency_cas_and_secret_reveal_once','test_atomic_rate_and_quota_are_configured','test_real_http_create_read_update_cas_actor_binding_and_idempotency','test_public_input_rejects_authority_and_sanitizes_validation','test_http_auth_denied_errors_safe_and_no_secret_in_admin_get','test_oauth_failed_attempts_are_durably_rate_limited','test_parallel_rate_counter_and_repository_restart','test_admin_options_bindings_disabled_client_and_scope_audit','test_webhook_edits_governed_callback_and_event_filter','test_interrupted_delivery_new_worker_reclaims_and_old_lease_cannot_finish','test_unknown_workflow_has_safe_stable_error','test_failed_oauth_audit_has_server_bound_identity_without_authenticating','test_expired_service_credential_is_denied_by_real_http','test_actual_signed_delivery_retry_and_bounded_failure','test_external_callback_ssrf_rejected','test_disable_and_rotate_key_cas_idempotency_preserve_delivery_history','test_external_only_openapi_strict_authority_security_errors','test_python_sdk_real_http_auth_intake_cas_no_authority_injection','test_external_real_docx_rag_async_result_and_review','test_parallel_first_startup_and_process_restart_one_checkpoint_authority','test_two_jurisdictions_complete_rule_union_and_distinct_execution_identity','test_configuration_gap_or_conflict_is_atomic','test_unpinned_or_implicit_execution_rejected','test_future_rule_binding_and_scheme_changes_do_not_change_s1','test_legacy_single_jurisdiction_historical_execution','test_database_rejects_competing_same_jurisdiction_result','test_applicability_rejects_cross_jurisdiction_rule_hit','test_formal_stages_execute_and_scope_each_explicit_jurisdiction','test_legacy_rule_hit_serialization_preserves_historical_digest_input','test_fresh_exact0017_equivalence_preserving_rows_downgrade_and_refusal','test_frozen_migrations_and_wip0017_byte_identity','test_empty_and_populated_integration_downgrade_transactional_policy','test_approval_reexecutes_owner_duplicate_identity_and_history','test_request_changes_history_no_resume_and_duplicate_cas','test_fact_choice_creates_successor_keeps_source_and_exact_parse_universe','test_concurrent_reviewers_one_cas_winner','test_approval_process_restart_keeps_canonical_history_and_checkpoint','test_stable_item_has_exact_immutable_snapshot_state_and_provenance']
for name in required:assert any(c.get('name','').split('[',1)[0]==name for c in cases),name
rt=read('runtime_verify.json');assert rt['all_mandatory_assertions_pass'] and len(rt['assertions'])==25 and all(rt['assertions'].values())
arch={}
for name in ['architecture_rule_check_stdout.json','m2a_architecture_check.json','m2b_architecture_check.json','m2c_architecture.json','m2c_projection_architecture.json','m2d_architecture.json','phase1kb_architecture.json','m2e_r1_architecture.json','m2e_architecture.json']:
 a=read(name);assert a['passed']==a['total'];checks=a['checks'];assert all(v is True for v in checks.values()) if isinstance(checks,dict) else all(v['pass'] is True for v in checks);arch[name]=a
assert sum(a['passed'] for a in arch.values())==b['architecture_passed']
parity=read('ui_api_parity.json');vertical=read('external_vertical_validation.json');review=read('external_review_validation.json')
for d in [parity,vertical,review]:assert d['runner_checkout_sha']==SHA
for k in ['same_authorized_canonical_context','all_structured_fields_equal','canonical_input_channel_exercised','intake_adapter_equal','canonical_document_universe_equal','confirmed_input_and_snapshot_equal','model_preferences_equal','result_not_precomputed']:assert parity[k],k
assert parity['presentation_exceptions']==[]
for d in [vertical,review]:
 for k in ['real_http','real_postgresql','no_paid_internet_llm','sse_websocket_parity','reconnect','cross_client_denied','lease_restart']:assert d[k],k
assert vertical['external_successor_snapshot'] and vertical['historical_result_unchanged_after_successor'] and vertical['workflow_status']=='COMPLETED' and review['workflow_status']=='REVIEW_REQUIRED'
unit=re.findall(r'\bTests\s+(\d+) passed\s*\((\d+)\)',log);assert unit and all(int(a)==int(c)>=135 for a,c in unit)
i18n_lines=[x for x in lines if '"hard_coded_ui_strings"' in x and '"missing_keys"' in x];assert i18n_lines;i18n=json.loads(i18n_lines[-1][i18n_lines[-1].index('{'):]);assert i18n['status']=='PASS' and i18n['missing_keys']==i18n['hard_coded_ui_strings']==0 and set(i18n['locales'])=={'zh-CN','zh-HK','en-US'}
assert '24 passed' in log and '36 passed' in log and not re.search(r'\b[1-9]\d* (?:xfailed|xpassed)\b',log)
# Native frontend measurement examines every raw Playwright result before artifact upload.
# Raw matrix files are not uploaded by this existing workflow; logs and native checked measurement retained.
result=dict(run_id=r['id'],url=r['html_url'],workflow=r['name'],tested_main_sha=SHA,runner_checkout_sha=SHA,checkout_jobs=proof,backend=b,frontend=f,runtime=rt,architecture=arch,migration=m,security=security,ui_api_parity=parity,external_vertical=vertical,external_review=review,test_case_coverage=coverage,required_semantic_cases=required,browser_passed=60,browser_retries=0,i18n=i18n,quality='PASS',paid_internet_llm='NOT EXECUTED',browser_evidence_limitation='Native strict measurement and actual job logs; M2E workflow does not upload raw Playwright matrix files; legacy workflows supply independent raw matrices for their scopes.')
(P/'measured-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'run_id':r['id'],'backend':b['backend']['passed'],'architecture':b['architecture_passed'],'frontend':f['frontend_passed'],'browser':60,'retries':0,'checkout_jobs':proof}))
