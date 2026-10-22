import argparse,concurrent.futures,datetime,hashlib,json,pathlib,re,subprocess,zipfile
from zoneinfo import ZoneInfo

ROOT=pathlib.Path('/workspace/kb01-g1r1');REPO='bensuen0831/crossborder-compliance-agent';S='4593a355d0711a9ba955b1624926a2ec71d60430'
EXPECTED={'KB01 Regulatory Knowledge Management','M0 Knowledge & Evidence Preview','M1 Intake Analysis Alpha','M2A Production Intake','M2B Production Document Integration','M2C Formal Result Workspace','M2D Governed Human Review','Phase1KB Multi-provider LLM Governance','M2E External Agent API Gateway','Stage1 R1 Candidate Governance Recovery','Stage1 Full Business E2E Acceptance','phase1a-runtime-smoke'}

def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+REPO+'/'+path]))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--complete',action='store_true');args=parser.parse_args()
 p=api('pulls/29');assert p['head']['sha']==S and p['draft'] and not p['merged'] and p['state']=='open'
 assert api('git/ref/heads/main')['object']['sha']=='060cbb5a20a9f8f70fa88dbefb8b5feb404c460d'
 runs=api('actions/runs?head_sha='+S+'&per_page=100')['workflow_runs'];selected=[]
 for name in EXPECTED:
  matching=[r for r in runs if r['name']==name];assert matching,name
  selected.append(max(matching,key=lambda r:r['id']))
 out={'source_sha':S,'observed_at':datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'runs':[]}
 for r in sorted(selected,key=lambda r:r['name']):
  jobs=api(f'actions/runs/{r["id"]}/jobs?per_page=100');assert jobs['total_count']==len(jobs['jobs'])
  row={'id':r['id'],'name':r['name'],'status':r['status'],'conclusion':r['conclusion'],'attempt':r['run_attempt'],'head_sha':r['head_sha'],'event':r['event'],'url':r['html_url'],'jobs':[]}
  assert row['head_sha']==S
  for j in jobs['jobs']:
   item={'id':j['id'],'name':j['name'],'status':j['status'],'conclusion':j['conclusion'],'url':j['html_url'],'started_at':j['started_at'],'completed_at':j['completed_at'],'steps':[{k:s.get(k) for k in ['name','status','conclusion','started_at','completed_at']} for s in j['steps']]}
   if args.complete:
    assert j['status']=='completed' and j['conclusion']=='success',(r['id'],j['id'],j['conclusion'])
    raw=subprocess.check_output(['gh','api',f'repos/{REPO}/actions/jobs/{j["id"]}/logs']);lines=raw.decode(errors='replace').splitlines();observed=[]
    for i,line in enumerate(lines):
     if 'git log -1 --format=%H' in line:
      for following in lines[i+1:i+5]:
       match=re.search(r'(?:^|\s)([0-9a-f]{40})\s*$',following)
       if match:observed.append(match[1]);break
    assert set(observed)=={S},(r['id'],j['id'],observed)
    item.update(runner_checkout_sha=S,checkout_observations=observed,log_sha256=sha(raw))
    summaries=[]
    for line in lines:
     if re.search(r'\d+ passed',line) and re.search(r' in [0-9.]+s',line):
      counts={label:int(number) for number,label in re.findall(r'(\d+) (passed|failed|skipped|deselected|xfailed|xpassed|errors?)',line)}
      summaries.append(counts)
    item['observed_test_summary_counts']=summaries
   row['jobs'].append(item)
  if args.complete:
   assert r['status']=='completed' and r['conclusion']=='success',(r['id'],r['conclusion'])
   artifacts=api(f'actions/runs/{r["id"]}/artifacts?per_page=100');assert artifacts['total_count']==len(artifacts['artifacts'])
   row['artifacts']=[{k:a.get(k) for k in ['id','name','size_in_bytes','digest','expired','created_at','expires_at']} for a in artifacts['artifacts']]
  out['runs'].append(row)
 out['success_workflows']=sum(r['status']=='completed' and r['conclusion']=='success' for r in out['runs'])
 out['total_workflows']=len(out['runs']);out['verified_job_checkouts']=sum('runner_checkout_sha' in j for r in out['runs'] for j in r['jobs'])
 write(ROOT/('ci-complete.json' if args.complete else 'ci-progress.json'),out)
 print('Latest source',S,'workflows',out['success_workflows'],'/',out['total_workflows'],'checkouts',out['verified_job_checkouts'])
 for r in out['runs']:
  if r['conclusion'] not in (None,'success'):print('Non-success',r['id'],r['name'],r['conclusion'])

if __name__=='__main__':main()
