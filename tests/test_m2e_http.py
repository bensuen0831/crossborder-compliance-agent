"""Real TCP HTTP, real PostgreSQL, canonical use cases (no gateway mocks)."""
import socket
import threading
import time
from contextlib import contextmanager
from datetime import date
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from test_phase1c_model_registry import _sf,_seed_tenant

from crossborder_compliance.domain.integrations import IntegrationPolicy
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.integrations import admin_router
from crossborder_compliance.interfaces.api.routes.external import router

pytestmark=pytest.mark.runtime_smoke


@contextmanager
def http_server(app):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='critical',access_log=False))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.02)
    assert server.started
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=10) as client:yield client
    finally:
        server.should_exit=True;thread.join(timeout=10)
        assert not thread.is_alive()


@pytest.fixture
def gateway():
    tenant=uuid4();sf=_sf();_seed_tenant(sf,tenant)
    app=FastAPI();app.include_router(admin_router);app.include_router(router)
    app.state.knowledge_session_factory=sf
    app.state.integration_policy=IntegrationPolicy(stream_duration_seconds=1)
    ctx=RepositoryContext.user(tenant,'administrator',{'integration:manage'})
    app.dependency_overrides[get_repository_context]=lambda:ctx
    with http_server(app) as client:yield app,client,tenant


def credential(client):
    r=client.post('/api/v1/admin/integration-clients',headers={'Idempotency-Key':uuid4().hex},json={
        'display_name':'HTTP ERP','allowed_scopes':['project:create','project:read','intake:write','compliance:read','compliance:analyze','document:upload','model:select','webhook:manage']})
    assert r.status_code==201,r.text
    return r.json()


def authenticated(client):
    c=credential(client)
    t=client.post('/api/v1/external/oauth/token',data={'client_id':c['client']['client_id'],'client_secret':c['credential'],'grant_type':'client_credentials'})
    assert t.status_code==200,t.text
    return {'Authorization':'Bearer '+t.json()['access_token']},c


def test_real_http_create_read_update_cas_actor_binding_and_idempotency(gateway):
    app,c,tenant=gateway
    auth,identity=authenticated(c)
    key=uuid4().hex
    payload={'name':uuid4().hex,'facts':{'analysis_as_of_date':date.today().isoformat()}}
    headers={**auth,'Idempotency-Key':key,'X-Correlation-ID':'external-http-test'}
    one=c.post('/api/v1/external/projects',headers=headers,json=payload)
    assert one.status_code==201,one.text
    assert one.headers['X-Correlation-ID']=='external-http-test'
    assert one.json()['intake']['provenance']['actor_ref']=='integration:'+identity['client']['client_id']
    assert c.post('/api/v1/external/projects',headers=headers,json=payload).json()==one.json()
    different=c.post('/api/v1/external/projects',headers=headers,json={**payload,'name':'different'})
    assert different.status_code==409,different.text
    project=one.json()['project_id'];url=f'/api/v1/external/projects/{project}/intake'
    assert c.get(url,headers=auth).json()==one.json()
    body={'expected_version':1,'facts':{**payload['facts'],'business_purpose':'Changed'}}
    two=c.put(url,headers={**auth,'Idempotency-Key':uuid4().hex},json=body)
    assert two.status_code==200 and two.json()['version']==2,two.text
    stale=c.put(url,headers={**auth,'Idempotency-Key':uuid4().hex},json=body)
    assert stale.status_code==409,stale.text
    other,_=authenticated(c)
    denied=c.get(url,headers=other)
    assert denied.status_code==404 and denied.json()['error_code']=='PROJECT_ACCESS_DENIED'


@pytest.mark.parametrize('field',['tenant_id','actor_id','permission','formal_risk','workflow_state','provider_credentials'])
def test_public_input_rejects_authority_and_sanitizes_validation(gateway,field):
    _,c,_=gateway;auth,_=authenticated(c)
    r=c.post('/api/v1/external/projects',headers={**auth,'Idempotency-Key':uuid4().hex},json={
        'name':'invalid','facts':{'analysis_as_of_date':'2026-10-09',field:'sensitive-no-echo'}})
    assert r.status_code==422 and r.json()['error_code']=='INVALID_INPUT'
    assert 'sensitive-no-echo' not in r.text and 'input' not in r.json()['details']


def test_http_auth_denied_errors_safe_and_no_secret_in_admin_get(gateway):
    _,c,_=gateway
    identity=credential(c)
    views=c.get('/api/v1/admin/integration-clients')
    assert identity['credential'] not in views.text and 'credential_hash' not in views.text
    bad=c.post('/api/v1/external/oauth/token',data={'client_id':identity['client']['client_id'],
        'client_secret':'bad-secret-not-logged','grant_type':'client_credentials'})
    assert bad.status_code==401 and 'bad-secret' not in bad.text
    assert c.get('/api/v1/external/projects/'+str(uuid4())+'/intake').status_code==401
    unknown=c.get('/api/v1/external/projects/'+str(uuid4())+'/intake',headers={'Authorization':'Bearer arbitrary'})
    assert unknown.status_code==401 and set(unknown.json())=={'error_code','message','details','trace_id','retryable'}
