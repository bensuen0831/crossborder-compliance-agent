"""Actual PostgreSQL upload, canonical parse and snapshot integration."""
# ruff: noqa: F401,F811 -- shared empirical fixture graph
import io
from uuid import UUID,uuid4
from pathlib import Path
from dataclasses import replace

import pytest
from sqlalchemy import select,func
from test_m2a_intake import create,setup
from test_m2a_structured_intake import binding
from test_phase1j_postgres import fixture,foundation_i,foundation_j

from crossborder_compliance.application.document_upload import DocumentFilePolicy,DraftDocumentRequest
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
from crossborder_compliance.infrastructure.persistence import models as b,document_models as d
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.intake_documents import router

pytestmark=pytest.mark.runtime_smoke


def policy():
    return DocumentFilePolicy(version="fixture-reviewed-v1",max_size_bytes=1024*1024,scan_required=False,
        allowed_types=[dict(extension=".txt",media_type="text/plain",signature="text"),
            dict(extension=".docx",media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",signature="docx")])


def host(f,tmp_path):
    app,c,ctx,values=setup(f)
    ctx=RepositoryContext.user(ctx.tenant_id,"author",set(ctx.permission.scopes)|{"document:read","document:upload","document:parse","document:unlink"})
    app.dependency_overrides[get_repository_context]=lambda:ctx
    app.include_router(router); app.state.document_file_policy=policy(); app.state.document_object_storage=FileObjectStorageAdapter(str(tmp_path/'objects'))
    return app,c,ctx,values


def upload(c,record,content=b"Purpose: Generic\n",key=None,name="input.txt",media="text/plain"):
    return c.post(f"/api/v1/projects/{record['project_id']}/intake/documents",
        data={"expected_version":record['version'],"idempotency_key":key or str(uuid4())},files={"file":(name,content,media)})


def test_actual_upload_restore_parse_retry_and_exact_identity(foundation_j,tmp_path):
    f=foundation_j; app,c,ctx,values=host(f,tmp_path); one=create(c,values).json()
    key=str(uuid4()); uploaded=upload(c,one,key=key)
    assert uploaded.status_code==201,uploaded.text
    view=uploaded.json(); doc=view['items'][0]; assert doc['parse_status']=='STORED' and view['intake_version']==2
    assert upload(c,one,key=key).json()==view
    url=f"/api/v1/projects/{one['project_id']}/intake/documents"
    assert c.get(url).json()==view
    record=c.get(f"/api/v1/projects/{one['project_id']}/intake").json()
    payload=dict(expected_version=2,idempotency_key=str(uuid4()))
    parsed=c.post(url+f"/{doc['document_version_id']}/parse",json=payload)
    assert parsed.status_code==200,parsed.text
    assert parsed.json()['items'][0]['parse_status']=='COMPLETED',parsed.text
    assert parsed.json()['items'][0]['quality_status']=='PASS'
    assert c.post(url+f"/{doc['document_version_id']}/parse",json=payload).json()==parsed.json()
    with f['sf']() as s:
        dv=s.get(b.DocumentVersionEntity,doc['document_version_id']); assert dv.content_hash==doc['content_hash']
        audit=s.get(d.DocumentVersionIntelligenceEntity,dv.document_version_id).upload_provenance_json
        assert audit['actor_ref']=='author' and audit['scan_status']=='NOT_REQUESTED'
        assert s.scalar(select(func.count()).select_from(b.DocumentParseRunEntity).where(b.DocumentParseRunEntity.document_version_id==dv.document_version_id))==1
        traces=s.scalars(select(b.SourceTraceRefEntity).where(b.SourceTraceRefEntity.document_version_id==dv.document_version_id)).all(); assert traces
        assert s.scalar(select(func.count()).select_from(d.BusinessFactCandidateEntity).where(d.BusinessFactCandidateEntity.parse_run_id==parsed.json()['items'][0]['parse_run_id']))==1


@pytest.mark.parametrize('case',['tenant','actor','permission','stale','size','type','content','scanner','storage'])
def test_upload_boundary_fail_closed(foundation_j,tmp_path,case):
    f=foundation_j; app,c,ctx,values=host(f,tmp_path); one=create(c,values).json()
    content=b"Purpose: Generic\n"; media='text/plain'; expected=201
    if case=='tenant': app.dependency_overrides[get_repository_context]=lambda:RepositoryContext.user(uuid4(),'author',ctx.permission.scopes); expected=404
    if case=='actor': app.dependency_overrides[get_repository_context]=lambda:RepositoryContext.user(ctx.tenant_id,'other',ctx.permission.scopes); expected=404
    if case=='permission': app.dependency_overrides[get_repository_context]=lambda:RepositoryContext.user(ctx.tenant_id,'author',ctx.permission.scopes-{'document:upload'}); expected=404
    if case=='stale': one['version']=9; expected=409
    if case=='size': content=b'x'*(1024*1024+1); expected=413
    if case=='type': media='application/pdf'; expected=422
    if case=='content': content=b'\x00bad'; expected=422
    if case=='scanner': app.state.document_file_policy=policy().model_copy(update={'scan_required':True}); expected=503
    if case=='storage':
        class Unavailable:
            def put(self,**kwargs): raise OSError('unavailable')
        app.state.document_object_storage=Unavailable(); expected=503
    response=upload(c,one,content,media=media)
    assert response.status_code==expected,response.text
    with f['sf']() as s: assert s.scalar(select(func.count()).select_from(b.DocumentEntity).where(b.DocumentEntity.project_id==one['project_id']))==0
