import concurrent.futures,json,subprocess,sys,pathlib
repo='bensuen0831/crossborder-compliance-agent';rid=sys.argv[1];out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
def api(path):return json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/{path}']))
r=api(f'actions/runs/{rid}');j=api(f'actions/runs/{rid}/jobs?per_page=100');a=api(f'actions/runs/{rid}/artifacts?per_page=100')
assert r['head_sha']==json.loads(pathlib.Path('/workspace/m2e-main-control/main-identity.json').read_text())['sha'] and r['event']=='workflow_dispatch' and r['head_branch']=='main'
assert r['status']=='completed' and r['conclusion']=='success' and j['jobs'] and all(x['status']=='completed' and x['conclusion']=='success' for x in j['jobs'])
for n,d in [('run',r),('jobs',j),('artifacts',a)]:(out/(n+'.json')).write_text(json.dumps(d,indent=2)+'\n')
def raw_job(job):
 raw=subprocess.check_output(['gh','api',f'repos/{repo}/actions/jobs/{job["id"]}/logs']).decode('utf-8-sig');(out/f'job-{job["id"]}.log').write_text(raw)
 return '\n'.join(job['name']+'\tlog\t'+line for line in raw.splitlines())
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:logs=list(pool.map(raw_job,j['jobs']))
(out/'jobs.log').write_text('\n'.join(logs)+'\n')
if a['artifacts'] and not (out/'downloaded').exists():subprocess.run(['gh','run','download',rid,'--repo',repo,'--dir',str(out/'downloaded')],check=True)
print(json.dumps({'run_id':r['id'],'workflow':r['name'],'jobs':[(x['name'],x['conclusion']) for x in j['jobs']],'artifacts':len(a['artifacts'])}))
