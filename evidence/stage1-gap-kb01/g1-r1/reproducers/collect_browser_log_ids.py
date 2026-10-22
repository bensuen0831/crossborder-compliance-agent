import hashlib,json,pathlib,re,subprocess
R=pathlib.Path('/workspace/kb01-g1r1');c=json.loads((R/'ci-complete.json').read_text());S=c['source_sha'];records=[]
for run in c['runs']:
 if run['name'] not in ['M2E External Agent API Gateway']:continue
 for j in run['jobs']:
  if j['name']!='canonical-frontend-browser':continue
  raw=subprocess.check_output(['gh','api',f'repos/bensuen0831/crossborder-compliance-agent/actions/jobs/{j["id"]}/logs']);assert hashlib.sha256(raw).hexdigest()==j['log_sha256']
  text=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',raw.decode());lines=[]
  for line in text.splitlines():
   if '✓' in line and re.search(r'(phase1kb|m2e)\.spec\.ts:',line):lines.append(line)
  assert len(lines)==9,(len(lines),j['name']);records.append({'run_id':run['id'],'job_id':j['id'],'runner_checkout_sha':S,'log_sha256':j['log_sha256'],'actual_pass_lines':lines})
assert records
(R/'browser-runtime-log-identities.json').write_text(json.dumps({'source_sha':S,'records':records},indent=2)+'\n');print('Nine missing detailed browser identities independently verified in actual passing runner log')
