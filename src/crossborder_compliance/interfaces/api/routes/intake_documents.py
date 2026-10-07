"""Multipart upload into the existing Project/Intake/Document identities."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import DBAPIError, IntegrityError

from crossborder_compliance.application.document_upload import DocumentCapabilityError, DocumentInputsView, DocumentUploadPolicyView, DraftDocumentRequest
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.document_input_composition import document_input_service
from crossborder_compliance.infrastructure.persistence.project_intake import IntakeConflict
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router=APIRouter(prefix="/api/v1/projects/{project_id}/intake",tags=["project-document-inputs"])
Context=Annotated[RepositoryContext,Depends(get_repository_context)]


def service(request,context):
    try: return document_input_service(request,sessions(request),context)
    except DocumentCapabilityError as exc: raise HTTPException(503,str(exc)) from exc
    except OSError as exc: raise HTTPException(503,"DOCUMENT_STORAGE_UNAVAILABLE") from exc


def invoke(fn,*args,**kwargs):
    try: return fn(*args,**kwargs)
    except (LookupError,PermissionError) as exc: raise HTTPException(404,"document input not found") from exc
    except DocumentCapabilityError as exc: raise HTTPException(503,str(exc)) from exc
    except OSError as exc: raise HTTPException(503,"DOCUMENT_STORAGE_UNAVAILABLE") from exc
    except (IntakeConflict,IntegrityError) as exc: raise HTTPException(409,"DOCUMENT_INPUT_CONCURRENCY_CONFLICT") from exc
    except DBAPIError as exc:
        if getattr(exc.orig,"sqlstate",None) in {"40001","40P01"}: raise HTTPException(409,"DOCUMENT_INPUT_CONCURRENT_RETRY") from exc
        raise
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc


@router.get("/documents",response_model=DocumentInputsView)
def list_inputs(project_id:UUID,request:Request,context:Context,version:int|None=None):
    return invoke(service(request,context).list_inputs,project_id,version)


@router.get("/documents/policy",response_model=DocumentUploadPolicyView)
def upload_policy(project_id:UUID,request:Request,context:Context):
    app_service=service(request,context)
    invoke(app_service.list_inputs,project_id)
    repo=app_service.repository
    policy=repo.file_policy
    available=policy is not None and repo.storage is not None and (not policy.scan_required or repo.scanner is not None)
    return DocumentUploadPolicyView(project_id=project_id,
        status="AVAILABLE" if available else "CAPABILITY_NOT_CONFIGURED",
        policy_version=policy.version if policy else None, max_size_bytes=policy.max_size_bytes if policy else None,
        allowed_types=policy.allowed_types if policy else (), scan_required=policy.scan_required if policy else None)


@router.post("/documents",response_model=DocumentInputsView,status_code=201)
async def upload(project_id:UUID,request:Request,context:Context,file:UploadFile=File(...),expected_version:int=Form(...,ge=1),idempotency_key:str=Form(...,min_length=1,max_length=128),replace_document_id:UUID|None=Form(None)):
    app_service=service(request,context)
    invoke(app_service.list_inputs,project_id)
    if app_service.repository.file_policy is None or app_service.repository.storage is None:
        raise HTTPException(503,"CAPABILITY_NOT_CONFIGURED: document upload")
    form=await request.form()
    allowed={"file","expected_version","idempotency_key","replace_document_id"}
    if set(form)-allowed or any(len(form.getlist(key))!=1 for key in form):
        raise HTTPException(422,"DOCUMENT_CLIENT_AUTHORITY_FIELD_FORBIDDEN")
    maximum=app_service.repository.file_policy.max_size_bytes
    content=await file.read(maximum+1)
    if len(content)>maximum: raise HTTPException(413,"DOCUMENT_SIZE_POLICY_VIOLATION")
    # Parsing/storage/DB remain off the event loop; no browser identity/policy.
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(invoke,app_service.upload,project_id,
        DraftDocumentRequest(expected_version=expected_version,idempotency_key=idempotency_key),
        filename=file.filename or "",media_type=file.content_type or "application/octet-stream",content=content,replace_document_id=replace_document_id)


@router.post("/documents/{version_id}/parse",response_model=DocumentInputsView)
def parse(project_id:UUID,version_id:UUID,body:DraftDocumentRequest,request:Request,context:Context):
    return invoke(service(request,context).parse,project_id,version_id,body)


@router.post("/documents/{version_id}/unlink",response_model=DocumentInputsView)
def unlink(project_id:UUID,version_id:UUID,body:DraftDocumentRequest,request:Request,context:Context):
    return invoke(service(request,context).unlink,project_id,version_id,body)


@router.post("/supersede",response_model=DocumentInputsView)
def supersede(project_id:UUID,body:DraftDocumentRequest,request:Request,context:Context):
    return invoke(service(request,context).repository.supersede,project_id,body)
