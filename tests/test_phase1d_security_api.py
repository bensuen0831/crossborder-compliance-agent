from __future__ import annotations
from uuid import UUID, uuid4
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from crossborder_compliance.application.document_services import (
    DocumentIngestionService, DocumentValidationError, normalize_filename
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.routes.documents import router

class Repo:
    def __init__(self): self.calls=[]
    def create_document_version(self,**kwargs):
        self.calls.append(kwargs); return {"document_id":str(uuid4()),"document_version_id":str(uuid4()),"version_no":1,**kwargs}
    def add_document_version(self,*,document_id,**kwargs):
        self.calls.append(kwargs); return {"document_id":str(document_id),"document_version_id":str(uuid4()),"version_no":2,**kwargs}

class Store:
    def __init__(self): self.keys=[]
    def put(self,*,object_key,content,content_type): self.keys.append(object_key); return "mem://"+object_key
    def get(self,storage_ref): return b""

class Scan:
    def __init__(self,ok=True): self.ok=ok; self.calls=0
    def scan(self,*,content,filename): self.calls+=1; return self.ok

class IngestService:
    def ingest(self,*,tenant_id,project_id,filename,mime_type,content):
        return {"document_id":str(uuid4()),"document_version_id":str(uuid4()),"version_no":1,"filename":filename,"mime_type":mime_type,"size_bytes":len(content),"content_hash":"a"*64,"storage_ref":"mem://safe"}
    def add_version(self,*,tenant_id,document_id,filename,mime_type,content):
        return {"document_id":str(document_id),"document_version_id":str(uuid4()),"version_no":2,"filename":filename,"mime_type":mime_type,"size_bytes":len(content),"content_hash":"b"*64,"storage_ref":"mem://safe"}

class ParseService:
    def request_parse(self,*,document_version_id,idempotency_key,parser_profile_id):
        return {"task_id":str(uuid4()),"status":"ACCEPTED","enqueue_required":True}

def test_upload_validation_path_mime_size_malware_and_tenant_object_key():
    tenant,project=uuid4(),uuid4(); repo=Repo();store=Store();scan=Scan()
    svc=DocumentIngestionService(repo,store,scan,max_size_bytes=10)
    assert normalize_filename("../../folder/secret.txt")=="secret.txt"
    result=svc.ingest(tenant_id=tenant,project_id=project,filename="../../folder/secret.txt",mime_type="text/plain",content=b"abc")
    assert result["filename"]=="secret.txt"
    assert store.keys and store.keys[0].startswith(f"tenant/{tenant}/project/{project}/documents/")
    assert ".." not in store.keys[0].split("/")
    with pytest.raises(DocumentValidationError):
        svc.ingest(tenant_id=tenant,project_id=project,filename="bad.pdf",mime_type="text/plain",content=b"x")
    with pytest.raises(DocumentValidationError):
        svc.ingest(tenant_id=tenant,project_id=project,filename="large.txt",mime_type="text/plain",content=b"x"*11)
    blocked=DocumentIngestionService(repo,store,Scan(False))
    with pytest.raises(DocumentValidationError):
        blocked.ingest(tenant_id=tenant,project_id=project,filename="safe.txt",mime_type="text/plain",content=b"x")

def test_document_api_requires_trusted_context_and_returns_202_for_async_parse():
    app=FastAPI(); app.include_router(router)
    client=TestClient(app)
    r=client.post(f"/api/v1/projects/{uuid4()}/documents",files={"file":("generic.txt",b"abc","text/plain")})
    assert r.status_code==401

    tenant=uuid4()
    app2=FastAPI()
    @app2.middleware("http")
    async def trusted(request:Request,call_next):
        request.state.repository_context=RepositoryContext.user(tenant,"trusted-user")
        return await call_next(request)
    app2.state.document_ingestion_service=IngestService()
    app2.state.document_parse_service=ParseService()
    app2.include_router(router)
    c=TestClient(app2)
    p=uuid4()
    up=c.post(f"/api/v1/projects/{p}/documents",files={"file":("generic.txt",b"abc","text/plain")})
    assert up.status_code==201 and up.json()["mime_type"]=="text/plain"
    vid=up.json()["document_version_id"]
    pr=c.post(f"/api/v1/document-versions/{vid}/parse",json={"idempotency_key":"k1","parser_profile_id":"default"})
    assert pr.status_code==202 and pr.json()["status"]=="ACCEPTED" and pr.json()["task_id"]
