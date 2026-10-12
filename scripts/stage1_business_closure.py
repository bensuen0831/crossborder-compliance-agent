"""Fail-closed exact-head acceptance aggregation, with concrete test IDs."""
import argparse,hashlib,json,os,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
REQUIRED=('test_blank_project_document_flow_and_four_formal_outcomes','test_independent_web_external_oauth_blank_project_businesses','test_blank_project_query_gap_real_http_second_retrieval_cannot_broaden_scope','test_multi_model_disagreement_is_candidate_only_and_user_selects_input','test_new_successor_requires_new_authorization_and_preserves_completed_result','test_blank_document_project_same_snapshot_review_reexecutes_owner','test_typescript_sdk')
def sha():
    actual=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    assert actual==os.environ['EXPECTED_PR_HEAD'],'CHECKOUT_IDENTITY_MISMATCH'
    return actual

def backend(path,source):
    root=ET.parse(path).getroot();cases=root.findall('.//testcase');assert cases
    assert not root.findall('.//failure') and not root.findall('.//error') and not root.findall('.//skipped')
    names=[t.get('name','') for t in cases]
    for required in REQUIRED:assert any(required in n for n in names),required
    assert len([n for n in names if n.startswith(REQUIRED[0])])==4
    assert len([n for n in names if n.startswith(REQUIRED[1])])==4
    assert len([n for n in names if n.startswith(REQUIRED[4])])==3
    return dict(runner_checkout_sha=source,tested_source_sha=source,passed=len(cases),failed=0,errors=0,skipped=0,deselected=0,test_ids=[t.get('classname','')+'::'+t.get('name','') for t in cases],junit_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def browser(path,source):
    data=json.loads(path.read_text());cases=[]
    def walk(suites):
        for suite in suites:
            for spec in suite.get('specs',[]):
                for test in spec['tests']:
                    results=test['results'];assert len(results)==1 and results[0]['status']=='passed' and results[0]['retry']==0
                    import base64
                    attachments=[a for a in results[0].get('attachments',[]) if a['name']=='measured-business']
                    assert len(attachments)==1
                    attachment=attachments[0]
                    measured=json.loads(base64.b64decode(attachment['body']) if 'body' in attachment else Path(attachment['path']).read_bytes())
                    assert measured['retries']==0 and len(measured['normalized_formal_sha256'])==64
                    cases.append(dict(title=spec['title'],test_id=spec['id'],duration_ms=results[0]['duration'],**measured))
            walk(suite.get('suites',[]))
    assert not data.get('errors');walk(data['suites']);assert len(cases)==12
    assert data['stats']['expected']==12 and not any(data['stats'][k] for k in ('unexpected','skipped','flaky'))
    for outcome in ('DIRECT','CONDITIONAL','LOCALIZATION','REVIEW'):
        for locale in ('zh-CN','zh-HK','en-US'):assert len([c for c in cases if f'{outcome} business journey {locale}' in c['title']])==1
    for outcome in ('DIRECT','CONDITIONAL','LOCALIZATION','REVIEW'):
        assert len({c['normalized_formal_sha256'] for c in cases if c['outcome']==outcome})==1,'LOCALE_FORMAL_SEMANTICS_CHANGED'
    return dict(runner_checkout_sha=source,tested_source_sha=source,passed=12,retries=0,cases=cases,report_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
def main():
    parser=argparse.ArgumentParser();parser.add_argument('gate',choices=('backend','browser','aggregate'));parser.add_argument('--input',type=Path);parser.add_argument('--regression',type=Path);parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args();source=sha()
    if args.gate=='aggregate':
        records=[json.loads(p.read_text()) for p in args.directory.rglob('stage1_business_*_measured.json')]
        assert len(records)==2 and {r['gate'] for r in records}=={'backend','browser'}
        assert all(r['runner_checkout_sha']==r['tested_source_sha']==source and r['decision']=='PASS' for r in records)
        value=dict(gate='aggregate',runner_checkout_sha=source,tested_source_sha=source,decision='PASS',records=records,acceptance_kind='L1_SYNTHETIC_GOVERNED_TECHNICAL_BUSINESS_E2E',full_regression='REQUIRES_SEPARATE_REPOSITORY_MANDATORY_WORKFLOWS',paid_internet_llm='NOT EXECUTED',real_regulatory_knowledge='NOT EXECUTED',production_business_uat='NOT EXECUTED',stage2_started=False)
    else:
        value=(backend if args.gate=='backend' else browser)(args.input,source);value.update(gate=args.gate,decision='PASS')
        if args.gate=='backend':
            assert args.regression is not None
            tree=ET.parse(args.regression).getroot();cases=tree.findall('.//testcase')
            assert cases and not any(tree.findall('.//'+tag) for tag in ('failure','error','skipped'))
            classes={t.get('classname','') for t in cases}
            for required in ('test_stage1_candidate_governance_http','test_stage1_candidate_governance_domain','test_stage1_support_historical','test_stage1_decision_versions','test_stage1_decision_compatibility_migrations','test_phase1kb_endpoint_security','test_m2e_http'):
                assert any(required in c for c in classes),required
            value['owning_regressions']=dict(passed=len(cases),failed=0,errors=0,skipped=0,deselected=0,test_ids=[t.get('classname','')+'::'+t.get('name','') for t in cases],junit_sha256=hashlib.sha256(args.regression.read_bytes()).hexdigest())
    args.directory.mkdir(parents=True,exist_ok=True);out=args.directory/f'stage1_business_{args.gate}_measured.json';out.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
if __name__=='__main__':main()
