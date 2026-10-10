import json,re,sys,xml.etree.ElementTree as ET
from pathlib import Path

p=Path(sys.argv[1]);kind=sys.argv[2]
sha=json.loads(Path('/workspace/m2e-main-control/main-identity.json').read_text())['sha']
run=json.loads((p/'run.json').read_text());jobs=json.loads((p/'jobs.json').read_text())['jobs']
assert run['head_sha']==sha and run['head_branch']=='main' and run['event']=='workflow_dispatch'
assert run['status']=='completed' and run['conclusion']=='success' and jobs and all(j['conclusion']=='success' for j in jobs)
log=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',(p/'jobs.log').read_text())
lines=log.splitlines();checkouts={}
for index,line in enumerate(lines):
    if 'git log -1 --format=%H' in line:
        job=line.split('\t')[0]
        value=lines[index+1].split()[-1]
        assert value==sha,(job,value)
        checkouts[job]=value
assert set(checkouts)=={j['name'] for j in jobs},(checkouts,[j['name'] for j in jobs])
s={'run_id':run['id'],'url':run['html_url'],'workflow':run['name'],'event':run['event'],'conclusion':'success','tested_main_sha':sha,'runner_checkout_sha':sha,'checkout_jobs':checkouts}
def read(name):
    paths=list((p/'downloaded').rglob(name));assert len(paths)==1,(name,paths)
    return json.loads(paths[0].read_text())
if kind=='backend':
    identity=read('ci_run_evidence.json')
    assert identity['runner_checkout_sha']==identity['tested_pr_head_sha']==sha and str(identity['run_id'])==str(run['id'])
    s['identity']=identity
    d=read('pytest_full_summary.json');assert d['pass'] and d['passed']>=910 and all(d[k]==0 for k in ['failed','errors','skipped','deselected']);s['pytest']=d
    xml=ET.parse(next((p/'downloaded').rglob('pytest_full.xml'))).getroot();cases=list(xml.iter('testcase'))
    assert len(cases)==d['passed'] and all(not any(v.tag in ('failure','error','skipped') for v in c) for c in cases)
    s['m2c_test_cases']=[c.attrib for c in cases if 'test_m2c' in c.get('classname','')]
    assert len(s['m2c_test_cases'])==40
    s['m2d_test_cases']=[c.attrib for c in cases if 'test_m2d' in c.get('classname','')]
    assert len(s['m2d_test_cases'])==36
    s['canonical_formal_restart_cases']=[c.attrib for c in cases if 'test_phase1l_b_postgres' in c.get('classname','') and ('process_restart' in c.get('name','') or 'process_crash' in c.get('name',''))]
    assert len(s['canonical_formal_restart_cases'])>=2
    assert not re.search(r'\b[1-9]\d* (?:xfailed|xpassed)\b', log)
    s['architecture']={}
    for name,total in [('architecture_rule_check.json',151),('m2a_architecture_check.json',13),('m2b_architecture_check.json',27)]:
        d=read(name);assert d['pass'] and d['passed']==d['total']==total;s['architecture'][name]={'passed':total,'total':total}
    d=read('runtime_verify.json');assert d['all_mandatory_assertions_pass'] and len(d['assertions'])==25 and all(d['assertions'].values());s['runtime']={'passed':25,'total':25}
    schemas={}
    for f in (p/'downloaded').rglob('phase1?_schema_check.json'):
        d=json.loads(f.read_text());assert d['pass'];schemas[f.name]=d
    assert len(schemas)==9;s['schema_checks']=schemas
    for name in ['phase1k_a_boundary.json','stage1_integrity.json','m2a_ownership.json']:
        d=read(name);assert d.get('pass',d.get('status')=='PASS');s[name]=d
    s['static_subset_disclosure']=[x for x in lines if 'contract-tests' in x and re.search(r'\d+ passed.*\d+ deselected',x)]
else:
    d=read('results.json');stats=d['stats'];expected={'m2d':15,'m2c':12,'m2b':9,'m2a':3,'m1':3,'m0':36}[kind]
    assert stats['expected']==expected and all(stats[k]==0 for k in ['unexpected','skipped','flaky']) and not d['errors']
    files={};titles=[]
    def walk(node,file=None,parent_titles=()):
        file=node.get('file',file)
        context=(*parent_titles,node.get('title',''))
        for spec in node.get('specs',[]):
            for test in spec['tests']:
                assert test['results'] and len(test['results'])==1 and all(v['retry']==0 and v['status']=='passed' for v in test['results'])
                files[file]=files.get(file,0)+1;titles.append(' / '.join((*context,spec['title'])))
        for child in node.get('suites',[]):walk(child,file,context)
    for node in d['suites']:walk(node)
    suites=['m2d','m2c','m2b','m2a','m1'] if kind=='m2d' else ['m2c','m2b','m2a','m1'] if kind=='m2c' else ['m2b','m2a','m1'] if kind=='m2b' else [kind]
    if kind!='m0':
        for name in suites:assert sum(v for k,v in files.items() if k and k.endswith(name+'.spec.ts'))==3
    assert all(any(locale in title for title in titles) for locale in ['zh-CN','zh-HK','en-US'])
    s['browser']={'stats':stats,'files':files,'titles':titles,'retry_count':0}
    unit_summaries=re.findall(r'\bTests\s+(\d+) passed\s*\((\d+)\)',log)
    assert unit_summaries and all(int(passed)==int(total)>=135 for passed,total in unit_summaries)
    s['frontend_passed']=max(int(passed) for passed,total in unit_summaries)
    i18n_lines=[x for x in lines if '"hard_coded_ui_strings"' in x and '"missing_keys"' in x]
    assert i18n_lines
    i18n=json.loads(i18n_lines[-1][i18n_lines[-1].index('{'):])
    assert i18n['status']=='PASS' and i18n['missing_keys']==i18n['hard_coded_ui_strings']==0 and set(i18n['locales'])=={'zh-CN','zh-HK','en-US'}
    s['i18n']=i18n
    notices=[x for x in lines if 'EXACT_HEAD_SUMMARY=' in x]
    if notices:
        notice=json.loads(notices[-1].split('EXACT_HEAD_SUMMARY=',1)[1]);assert notice['tested_sha']==sha
        if 'runner_checkout_sha' in notice:assert notice['runner_checkout_sha']==sha
        s['checkout_notice']=notice
(p/'measured-summary.json').write_text(json.dumps(s,indent=2)+'\n')
print(json.dumps({'kind':kind,'run':run['id'],'checkout_jobs':checkouts,'pytest':s.get('pytest'),'frontend':s.get('frontend_passed'),'browser':s.get('browser',{}).get('stats'),'m2c_tests':len(s.get('m2c_test_cases',[]))}))
