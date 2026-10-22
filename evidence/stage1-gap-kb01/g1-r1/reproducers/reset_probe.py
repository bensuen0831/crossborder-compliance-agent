import json,pathlib,subprocess,sys,urllib.request
sys.path.insert(0,'/workspace/crossborder-compliance-agent')
from scripts.kb01 import rc1
R=pathlib.Path('/workspace/kb01-g1r1');state=R/'reset-disposable';assert state.exists();cfg=rc1.settings(state);instance=cfg['instance'];locks=json.loads((rc1.ROOT/'scripts/kb01/rc1_services.lock.json').read_text());assert (state/'original-marker.txt').read_text()=='SYNTHETIC_RESET_PROBE_ONLY'
control=instance+'-independent-control';rc1.docker('volume','create','--label','kb01.reset.probe='+instance,control)
for service in ['postgres','redis']:
 name=instance+'-'+service;volume=name+'-data';rc1.docker('volume','create','--label','kb01.rc1.instance='+instance,volume)
 cmd=['run','--detach','--name',name,'--network=none','--label','kb01.rc1.instance='+instance,'--mount','type=volume,src='+volume+',dst='+('/var/lib/postgresql/data' if service=='postgres' else '/data')]
 if service=='postgres':cmd+=['--env','POSTGRES_HOST_AUTH_METHOD=trust']
 if not rc1.owned_container(cfg,name):rc1.docker(*cmd,locks[service]['image'])
before=[]
for service in ['postgres','redis']:
 name=instance+'-'+service;assert rc1.owned_container(cfg,name);before.append(name)
raw=subprocess.run([sys.executable,'scripts/kb01/rc1.py','reset','--state-dir',str(state),'--confirm-reset',instance],cwd=rc1.ROOT,capture_output=True,text=True);assert raw.returncode==0,raw.stderr
for name in before:
 assert rc1.docker('container','inspect',name,check=False).returncode!=0
 assert rc1.docker('volume','inspect',name+'-data',check=False).returncode!=0
assert rc1.docker('volume','inspect',control).returncode==0
retained=list(R.glob('reset-disposable.retained-*'));assert len(retained)==1 and (retained[0]/'original-marker.txt').read_text()=='SYNTHETIC_RESET_PROBE_ONLY'
# Independent live RC1 remains untouched.
for url in ['http://127.0.0.1:15173','http://127.0.0.1:18010/health/live']:
 with urllib.request.urlopen(url) as response:assert response.status==200
rc1.docker('volume','rm',control)
result={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=rc1.ROOT,text=True).strip(),'decision':'PASS','scope':'Actual disposable Docker PG/Redis containers and owned volumes; no application dataset seeded; live UAT database untouched.','exact_owned_containers_removed':2,'exact_owned_volumes_removed':2,'independent_control_volume_preserved_before_explicit_probe_cleanup':True,'synthetic_local_original_file_retained':True,'live_uat_remains_healthy':True,'reset_stdout':raw.stdout.strip()}
(R/'reset-resource-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
