from __future__ import annotations

from dataclasses import asdict
from uuid import UUID
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.document_repositories import PostgresDocumentIntelligenceRepository
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.document_schemas import (
    DocumentAnalysisSummaryDTO,
    DocumentVersionResponseDTO,
    ParseRequestDTO,
    ParseRunResponseDTO,
    StructureNodeResponseDTO,
    TaskAcceptedDTO,
)
from crossborder_compliance.config import get_settings

router=APIRouter(prefix="/api/v1",tags=["document-intelligence"])


def _repo(request:Request):
    ctx=get_repository_context(request)
    sf=build_session_factory(get_settings().database_url)[1]
    return PostgresDocumentIntelligenceRepository(sf,ctx)


def _app_service(request:Request,name:str):
    service=getattr(request.app.state,name,None)
    if service is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail=f"{name} adapter is not configured")
    return service


@router.post("/projects/{project_id}/documents",response_model=DocumentVersionResponseDTO,status_code=201)
async def upload_document(project_id:UUID,request:Request,file:UploadFile=File(...)):
    ctx=get_repository_context(request)
    content=await file.read()
    service=_app_service(request,"document_ingestion_service")
    result=service.ingest(tenant_id=ctx.tenant_id,project_id=project_id,filename=file.filename or "upload.bin",mime_type=file.content_type or "application/octet-stream",content=content)
    return result


@router.post("/documents/{document_id}/versions",response_model=DocumentVersionResponseDTO,status_code=201)
async def upload_document_version(document_id:UUID,request:Request,file:UploadFile=File(...)):
    ctx=get_repository_context(request)
    content=await file.read()
    service=_app_service(request,"document_ingestion_service")
    return service.add_version(tenant_id=ctx.tenant_id,document_id=document_id,filename=file.filename or "upload.bin",mime_type=file.content_type or "application/octet-stream",content=content)


@router.post("/document-versions/{version_id}/parse",response_model=TaskAcceptedDTO,status_code=202)
def request_parse(version_id:UUID,payload:ParseRequestDTO,request:Request):
    service=_app_service(request,"document_parse_service")
    task=service.request_parse(document_version_id=version_id,idempotency_key=payload.idempotency_key,parser_profile_id=payload.parser_profile_id)
    return {"task_id":task["task_id"],"status":task["status"]}


@router.get("/document-versions/{version_id}/parse-runs",response_model=list[ParseRunResponseDTO])
def list_parse_runs(version_id:UUID,request:Request):
    return _repo(request).list_parse_runs(version_id)


@router.get("/parse-runs/{parse_run_id}",response_model=ParseRunResponseDTO)
def get_parse_run(parse_run_id:UUID,request:Request):
    row=_repo(request).get_parse_run(parse_run_id)
    if not row: raise HTTPException(404,"parse run not found")
    return row


@router.get("/parse-runs/{parse_run_id}/structure",response_model=list[StructureNodeResponseDTO])
def get_structure(parse_run_id:UUID,request:Request):
    return _repo(request).list_structure(parse_run_id)


@router.get("/parse-runs/{parse_run_id}/quality")
def get_quality(parse_run_id:UUID,request:Request):
    row=_repo(request).get_quality(parse_run_id)
    if not row: raise HTTPException(404,"quality result not found")
    return row


@router.get("/parse-runs/{parse_run_id}/facts")
def get_facts(parse_run_id:UUID,request:Request):
    return _repo(request).list_facts(parse_run_id)


@router.get("/parse-runs/{parse_run_id}/candidate-data-items")
def get_candidate_items(parse_run_id:UUID,request:Request):
    return _repo(request).list_candidate_items(parse_run_id)


@router.get("/parse-runs/{parse_run_id}/candidate-data-flows")
def get_candidate_flows(parse_run_id:UUID,request:Request):
    return _repo(request).list_candidate_flows(parse_run_id)


@router.get("/projects/{project_id}/document-analysis-summary",response_model=DocumentAnalysisSummaryDTO)
def document_analysis_summary(project_id:UUID,request:Request):
    return asdict(_repo(request).aggregate_project_summary(project_id))
