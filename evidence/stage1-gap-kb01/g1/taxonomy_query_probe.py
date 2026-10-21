import json,pathlib,time,statistics,hashlib
from uuid import uuid4
from sqlalchemy import event
from test_kb01_taxonomy_postgres import env,create,publish
R=pathlib.Path('/workspace/kb01-g1');S='39c3581ca455df4e3ce9760ed2deab8905a5f588';data=[]
for lifecycle in ['DRAFT','ACTIVE']:
 f=env.__wrapped__();sf,tenant,context,service=f;owner=service().repository;engine=sf.kw['bind']
 for n in range(100):
  c=create(service())
  if lifecycle=='ACTIVE':publish(f,c)
 for count in [1,4,25,100]:
  samples=[]
  for rep in range(3):
   statements=[]
   def capture(conn,cursor,statement,params,ctx,executemany):statements.append(statement)
   event.listen(engine,'before_cursor_execute',capture);start=time.perf_counter()
   try:result=owner.list(page_size=count)
   finally:elapsed=time.perf_counter()-start;event.remove(engine,'before_cursor_execute',capture)
   assert result['total']==100 and len(result['items'])==count
   assert all(x['lifecycle']==lifecycle for x in result['items'])
   expected=2+(3 if lifecycle=='DRAFT' else 4)*count;assert len(statements)==expected,(lifecycle,count,len(statements))
   samples.append({'query_count':len(statements),'elapsed_seconds':round(elapsed,6)})
  data.append({'lifecycle':lifecycle,'page_size':count,'samples':samples,'query_count':samples[0]['query_count'],'median_seconds':round(statistics.median(x['elapsed_seconds'] for x in samples),6)})
 engine.dispose()
(R/'taxonomy_measurements.json').write_text(json.dumps({'product_head':S,'method':'Real PostgreSQL;100 canonical rows per isolated synthetic tenant; ACTIVE rows independently submit/review/publish via existing owners;3 reads per page size; no product changes','measurements':data,'formula':'2 + 3*DRAFT_rows + 4*rows_with_active_version','maximum_page_size':100,'bounded_query_count_upper_observed':402,'latency_extrapolation':'Illustrative serialized network round trips only;402 queries at5ms/20ms RTT add approximately2.01s/8.04s. Not a measured remote latency or formal SLA.'},indent=2))
print(json.dumps(data,indent=2))
