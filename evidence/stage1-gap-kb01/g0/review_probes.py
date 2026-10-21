"""Independent second-pass probes; no product changes or fake legal authority."""
import json,os,pathlib,subprocess
from uuid import UUID,uuid4
import pytest
from sqlalchemy import event,select
from fastapi import FastAPI
from fastapi.testclient import TestClient
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.domain.knowledge_management import CreateTaxonomy,TaxonomyPayload
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import PostgresKnowledgeTaxonomyRepository
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.knowledge_process_sandbox import KnowledgeProcessSandbox
from crossborder_compliance.interfaces.api.routes import knowledge_management,knowledge_document_management,knowledge_uploads,knowledge_batches
from crossborder_compliance.config import get_settings
ROOT=pathlib.Path('/workspace/kb01-g0')
@pytest.fixture
def principals():
 engine,sf=build_session_factory(get_settings().database_url)
 tenants=[uuid4(),uuid4()]
 with sf() as s,s.begin():
  s.add_all([b.TenantEntity(tenant_id=str(t),name='G0 independent synthetic probe') for t in tenants])
 yield engine,sf,tenants
 engine.dispose()
def context(tenant,grants):return RepositoryContext.user(tenant,'server-reviewed-actor',set(grants))
def app(sf,ctx):
 application=FastAPI(); application.state.knowledge_session_factory=sf
 for module in [knowledge_management,knowledge_document_management,knowledge_uploads,knowledge_batches]:application.include_router(module.router)
 if ctx:
  @application.middleware('http')
  async def trusted_host(request,call_next):
   request.state.repository_context=ctx
   return await call_next(request)
 return application
@pytest.mark.parametrize('method,path,payload',[
 ('post','/taxonomy',{'kind':'JURISDICTION_CONFIG','code':'G0-COUNTRY','display_name':'Probe','payload':{'jurisdiction_type':'COUNTRY'},'idempotency_key':'g0-country'}),
 ('post','/taxonomy',{'kind':'REGULATION_CATEGORY','code':'G0-CATEGORY','display_name':'Probe','idempotency_key':'g0-category'}),
 ('post','/taxonomy/{id}/merge',{'target_definition_id':str(uuid4()),'expected_target_record_version':1,'expected_record_version':1,'reason':'G0 probe','idempotency_key':'g0-merge'}),
 ('delete','/documents/{id}',{'expected_record_version':1,'reason':'G0 probe','idempotency_key':'g0-delete'}),
 ('post','/documents/versions/{id}/approve',{'expected_record_version':1,'reason':'G0 probe','idempotency_key':'g0-approve'}),
 ('post','/documents/versions/{id}/publish',{'expected_record_version':1,'reason':'G0 probe','idempotency_key':'g0-publish'}),
 ('post','/upload-sessions/{id}/part-url',{'part_number':1,'content_sha256':'a'*64}),
 ('get','/import-batches/{id}/failures',None),
])
def test_current_coarse_admin_cannot_authorize_kb_actions(principals,method,path,payload):
 _,sf,tenants=principals
 with TestClient(app(sf,context(tenants[0],{'knowledge:admin'}))) as client:
  response=client.request(method,'/api/v1/admin/knowledge-management'+path.replace('{id}',str(uuid4())),**({'json':payload} if payload is not None else {}))
  assert response.status_code==403,response.text

def test_real_existing_cross_tenant_taxonomy_is_concealed(principals):
 _,sf,tenants=principals
 owner=PostgresKnowledgeTaxonomyRepository(sf,context(tenants[0],{'knowledge:taxonomy:write'}))
 made=owner.mutate('CREATE',None,CreateTaxonomy(kind='REGULATION_CATEGORY',code='G0-CROSS',display_name='G0 probe',idempotency_key=str(uuid4())))
 with TestClient(app(sf,context(tenants[1],{'knowledge:taxonomy:read'}))) as client:
  response=client.get('/api/v1/admin/knowledge-management/taxonomy/'+made['definition_id'])
  assert response.status_code==404
  assert client.get('/api/v1/admin/knowledge-management/taxonomy').json()['total']==0

def test_no_trusted_identity_is_unauthenticated_despite_spoof_headers(principals):
 _,sf,tenants=principals
 with TestClient(app(sf,None)) as client:
  response=client.get('/api/v1/admin/knowledge-management/taxonomy',headers={'X-Tenant-ID':str(tenants[0]),'X-Actor-ID':'admin','X-Permissions':'knowledge:taxonomy:read'})
  assert response.status_code==401

def test_taxonomy_list_query_growth_is_measured(principals):
 engine,sf,tenants=principals
 owner=PostgresKnowledgeTaxonomyRepository(sf,context(tenants[0],{'knowledge:taxonomy:write','knowledge:taxonomy:read'}))
 for n in range(4):owner.mutate('CREATE',None,CreateTaxonomy(kind='REGULATION_CATEGORY',code='G0-N'+str(n),display_name='G0 probe',idempotency_key=str(uuid4())))
 counts={}
 for size in [1,4]:
  queries=[]
  def count(*args):queries.append(args[2])
  event.listen(engine,'before_cursor_execute',count)
  try: result=owner.list(page_size=size)
  finally:event.remove(engine,'before_cursor_execute',count)
  assert len(result['items'])==size
  counts[str(size)]=len(queries)
 (ROOT/'query_growth.json').write_text(json.dumps({'source_sha':'39c3581ca455df4e3ce9760ed2deab8905a5f588','list_page_sizes_to_statement_counts':counts},indent=2))
 assert counts['4']>counts['1']

def test_actual_parser_container_has_no_network_credentials_or_host_mount():
 sandbox=KnowledgeProcessSandbox(json.loads((ROOT/'tool-image.json').read_text())['image_id'],ROOT/'sandbox-probes')
 program="import os,json,pathlib,socket; s=socket.socket();s.settimeout(1);print(json.dumps({'uid_nonroot':os.getuid()!=0,'app_database_credential_absent':'DATABASE_URL' not in os.environ,'host_workspace_absent':not pathlib.Path('/workspace/compliance-tools').exists(),'interfaces':open('/proc/net/route').read().count(chr(10))==1,'docker_socket_absent':not pathlib.Path('/var/run/docker.sock').exists()}))"
 result=sandbox.run('/usr/bin/python3.13',['-c',program],{},10)
 assert result['exit_code']==0,result
 checks=json.loads(result['stdout']);assert all(checks.values()),checks
 (ROOT/'sandbox_boundary.json').write_text(json.dumps({'tool_image':result['image_id'],'checks':checks},indent=2))
