import json,pathlib,statistics,subprocess,hashlib
from test_kb01_taxonomy_postgres import env,create,publish
from test_kb01_taxonomy_batch_postgres import reference_reader,measured
R=pathlib.Path('/workspace/kb01-g1r1');reference=reference_reader.__wrapped__();out=[]
for lifecycle in ['DRAFT','ACTIVE','MIXED']:
 f=env.__wrapped__();sf,tenant,context,service=f
 for n in range(100):
  row=create(service())
  if lifecycle=='ACTIVE' or (lifecycle=='MIXED' and n%2):publish(f,row)
 old=reference(sf,context());new=service().repository;engine=sf.kw['bind']
 for size in [1,4,25,100]:
  before=[];after=[];identity=None
  for _ in range(3):
   a,b=measured(engine,lambda:old.list(page_size=size));c,d=measured(engine,lambda:new.list(page_size=size))
   assert a==c and d['sql_statements']==5
   before.append(b);after.append(d);identity=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()
  out.append({'lifecycle':lifecycle,'page_size':size,'before_samples':before,'after_samples':after,'before_median_seconds':statistics.median(x['elapsed_seconds'] for x in before),'after_median_seconds':statistics.median(x['elapsed_seconds'] for x in after),'before_sql':before[0]['sql_statements'],'after_sql':after[0]['sql_statements'],'complete_json_sha256':identity,'json_parity':True})
 engine.dispose()
x={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'reference_source':'39c3581ca455df4e3ce9760ed2deab8905a5f588','method':'Real PostgreSQL; canonical independent-author/reviewer/publisher fixtures; paired old/new same engine/data; three reads each; no mocked SQL count','samples':out,'g1_prior_other_session_active100_median_seconds':2.536919,'g1_prior_measurement_not_a_same_session_speed_ratio':True}
(R/'paired-performance-final.json').write_text(json.dumps(x,indent=2))
for row in out:
 if row['page_size']==100:print(row['lifecycle'],row['before_sql'],row['after_sql'],round(row['before_median_seconds'],6),round(row['after_median_seconds'],6))
