"""External HTTP vertical slice through existing DOCX/RAG/formal runtime."""
# ruff: noqa: F401,F811 -- canonical PostgreSQL fixture graph
import io
import time
from uuid import UUID,uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from test_m2e_http import http_server,authenticated
from test_m2a_intake import setup
from test_m2a_structured_intake import binding
from test_m2b_document_inputs import policy
from test_phase1l_b_postgres import fixture,foundation_i,foundation_j
from test_phase1f_postgres import metadata

from crossborder_compliance.domain.integrations import IntegrationPolicy
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
from crossborder_compliance.infrastructure.integration_worker import IntegrationDeliveryWorker
from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
from crossborder_compliance.infrastructure.persistence import models as b,context_models as e
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.integrations import admin_router
from crossborder_compliance.interfaces.api.routes.external import router
from crossborder_compliance.interfaces.api.routes.workflow import router as workflow_router

pytestmark=pytest.mark.runtime_smoke


def server(f,tmp_path,review=False):
    binding(f)
    binding(f,code='GENERIC_FIELD',field='business_purpose',value_type='string')
    _,_,_,facts=setup(f)
    # Distinct governed jurisdictions, no country-specific production code.
    from m2e_fixtures import destination_configuration
    destination=destination_configuration(f)
    facts['destination_locations']=[destination]
    facts['data_volume']='3'
    app=FastAPI();app.include_router(admin_router);app.include_router(router);app.include_router(workflow_router)
    app.state.knowledge_session_factory=f['sf']
    app.state.integration_policy=IntegrationPolicy(stream_duration_seconds=1,worker_poll_seconds=.1)
    app.state.document_file_policy=policy()
    app.state.document_object_storage=FileObjectStorageAdapter(str(tmp_path/'binary'))
    if review:
        from functools import partial
        app.state.intake_snapshot_preparer=partial(prepare_snapshot,requirement_confirmation=True)
    context=RepositoryContext.user(UUID(f['tenant']),'integration-administrator',{'integration:manage'})
    app.dependency_overrides[get_repository_context]=lambda:context
    return app,facts


def docx():
    from docx import Document
    doc=Document();doc.add_paragraph('Purpose: Generic');buff=io.BytesIO();doc.save(buff)
    return buff.getvalue()


@pytest.mark.parametrize('foundation_i',[{'no_data':True}],indirect=True)
@pytest.mark.parametrize('review',[False,True])
def test_external_real_docx_rag_async_result_and_review(foundation_j,tmp_path,review):
    f=foundation_j;app,facts=server(f,tmp_path,review)
    worker=IntegrationDeliveryWorker(app)
    with http_server(app) as c:
        auth,identity=authenticated(c)
        def mutation(method,url,payload):
            response=c.request(method,url,headers={**auth,'Idempotency-Key':uuid4().hex},json=payload)
            assert response.status_code<300,response.text
            return response.json()
        intake=mutation('POST','/api/v1/external/projects',{'name':uuid4().hex,'facts':facts})
        project=intake['project_id'];base=f'/api/v1/external/projects/{project}'
        uploaded=c.post(base+'/documents',headers={**auth,'Idempotency-Key':uuid4().hex},data={'expected_version':1},files={
            'file':('requirements.docx',docx(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert uploaded.status_code==201,uploaded.text
        document=uploaded.json()['items'][0]
        parsed=mutation('POST',base+'/documents/'+document['document_version_id']+'/parse',{'expected_version':uploaded.json()['intake_version']})
        assert parsed['items'][0]['parse_status']=='COMPLETED'
        confirmed=mutation('POST',base+'/intake/confirm',{'expected_version':parsed['intake_version']})
        assert confirmed['status']=='CONFIRMED'
        with f['sf']() as s:
            traces=s.scalars(select(b.SourceTraceRefEntity).where(b.SourceTraceRefEntity.document_version_id==document['document_version_id'])).all()
            assert traces
            formal=s.scalars(select(e.BusinessFactEntity).where(e.BusinessFactEntity.project_id==project,e.BusinessFactEntity.tenant_id==f['tenant'])).all()
            assert any(row.fact_type=='GENERIC_FIELD' for row in formal)
        start_url=base+'/snapshots/'+confirmed['analysis_snapshot_id']+'/workflow'
        key=uuid4().hex
        started=c.post(start_url,headers={**auth,'Idempotency-Key':key},json={})
        assert started.status_code==202,started.text
        assert started.json()['workflow_run_id']==confirmed['workflow_run_id']
        assert c.post(start_url,headers={**auth,'Idempotency-Key':key},json={}).json()==started.json()
        worker.start()
        try:
            status=None
            for _ in range(100):
                response=c.get(started.json()['status_url'],headers=auth)
                assert response.status_code==200,response.text
                status=response.json()
                if status['status'] in {'COMPLETED','REVIEW_REQUIRED','FAILED','WARNING'}:break
                time.sleep(.1)
            assert status['status']==('REVIEW_REQUIRED' if review else 'COMPLETED'),status
            result=c.get(started.json()['result_url'],headers=auth)
            assert result.status_code==200,result.text
            value=result.json()
            assert value['analysis_snapshot_id']==confirmed['analysis_snapshot_id']
            if review:
                assert status['review_id'] and value['review_status']
                assert value['final_path'] is None
            else:
                assert value['final_path'] and value['legal_basis_items'] and value['evidence_summary']
                # Canonical UI/internal read: current explicitly authorized Web actor,
                # same exact snapshot and owning structured result, no result fixture.
                ctx=RepositoryContext.user(UUID(f['tenant']),'authorized-web-reader',{
                    'project:read','workflow:read','classification:read','applicability:read','decision:read','read:internal',
                    f'project:{project}:comply',f'project:{project}:classify'})
                app.dependency_overrides[get_repository_context]=lambda:ctx
                direct=c.get('/api/v1/workflows/'+confirmed['workflow_run_id']+'/stage1-result')
                assert direct.status_code==200,direct.text
                assert direct.json()==value
            events=c.get(started.json()['events_url'],headers=auth)
            assert events.status_code==200 and 'data: ' in events.text
            assert 'checkpoint' not in events.text and 'secret_ref' not in events.text
            other,_=authenticated(c)
            assert c.get(started.json()['events_url'],headers=other).status_code==404
            assert c.get(started.json()['result_url'],headers=other).status_code==404
        finally:worker.stop()
