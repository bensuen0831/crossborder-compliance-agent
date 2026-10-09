"""Versioned northbound transport over canonical application use cases."""
import asyncio
import json
import re
import time
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError

from crossborder_compliance.application.document_upload import DocumentCapabilityError, DocumentInputsView, DraftDocumentRequest
from crossborder_compliance.application.intake_services import ConfirmProjectIntake, IntakeView
from crossborder_compliance.application.integrations import IntegrationFailure
from crossborder_compliance.application.llm_model_catalog import EligibleModelCatalog
from crossborder_compliance.application.stage1_result import Stage1ComplianceResult
from crossborder_compliance.domain.integrations import ExternalWorkflowAccepted, GatewayError, TokenRequest, TokenView
from crossborder_compliance.infrastructure.external_composition import external_channel, integration_service
from crossborder_compliance.infrastructure.persistence.project_intake import IntakeConflict
from crossborder_compliance.interfaces.api.external_schemas import ExternalProjectCreate, ExternalIntakeUpdate
from crossborder_compliance.interfaces.api.routes.workflow import WorkflowStart, WorkflowView


def safe_failure(exc):
    if isinstance(exc, IntegrationFailure):return exc
    if isinstance(exc, (IntakeConflict, IntegrityError)):return IntegrationFailure('VERSION_CONFLICT',409)
    if isinstance(exc, (LookupError,PermissionError)):return IntegrationFailure('PROJECT_ACCESS_DENIED',404)
    if isinstance(exc, DocumentCapabilityError):return IntegrationFailure('CAPABILITY_NOT_CONFIGURED',503)
    if isinstance(exc,RequestValidationError):return IntegrationFailure('INVALID_INPUT',422)
    if isinstance(exc, ValueError):return IntegrationFailure('INVALID_INPUT',422)
    if isinstance(exc,HTTPException):
        code={401:'UNAUTHORIZED',403:'FORBIDDEN',404:'WORKFLOW_NOT_FOUND',409:'RESULT_NOT_READY',
              413:'DOCUMENT_REJECTED',422:'INVALID_INPUT',503:'CAPABILITY_NOT_CONFIGURED'}.get(exc.status_code,'INVALID_INPUT')
        return IntegrationFailure(code,exc.status_code,retryable=exc.status_code==503)
    if isinstance(exc,TimeoutError):return IntegrationFailure('REQUEST_TIMEOUT',504,retryable=True)
    return IntegrationFailure('CAPABILITY_NOT_CONFIGURED',503,retryable=True)


class ExternalRoute(APIRoute):
    def get_route_handler(self):
        original=super().get_route_handler()
        async def handler(request):
            supplied=request.headers.get('x-correlation-id','')
            trace=supplied if re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',supplied) else uuid4().hex
            request.state.request_id=trace
            service=integration_service(request)
            status=500; error=None
            try:
                policy=service.policy
                length=request.headers.get('content-length')
                if length and (not length.isdigit() or int(length)>policy.request_limit_bytes):
                    raise IntegrationFailure('INVALID_INPUT',413)
                # Bound chunked bodies before multipart/JSON parsing. No raw input
                # is logged/audited; upload has the owning file policy as well.
                total=0; receive=request._receive
                async def bounded_receive():
                    nonlocal total
                    message=await receive()
                    total+=len(message.get('body',b''))
                    if total>policy.request_limit_bytes:raise IntegrationFailure('INVALID_INPUT',413)
                    return message
                request._receive=bounded_receive
                response=await asyncio.wait_for(original(request),timeout=policy.request_timeout_seconds)
                status=response.status_code
            except Exception as exc:
                failure=safe_failure(exc);status=failure.status;error=failure.code
                headers={'Retry-After':str(failure.retry_after)} if failure.retry_after else {}
                if status==401:headers['WWW-Authenticate']='Bearer'
                response=JSONResponse(status_code=status,headers=headers,content=GatewayError(
                    error_code=failure.code,message=failure.code,trace_id=trace,
                    retryable=failure.retryable).model_dump(mode='json'))
            response.headers['X-Correlation-ID']=trace
            response.headers['Cache-Control']='no-store'
            principal=getattr(request.state,'integration_principal',None)
            service.repository.admin_context=getattr(request.state,'integration_admin_context',None)
            await run_in_threadpool(service.repository.audit,principal,request.method+' '+self.path,
                trace,'SUCCESS' if status<400 else 'DENIED',error,
                request.path_params.get('project_id'),request.path_params.get('run_id'),
                request.path_params.get('snapshot_id'),getattr(request.state,'integration_scope',None))
            return response
        return handler


router=APIRouter(prefix='/api/v1/external',tags=['external-v1'],route_class=ExternalRoute)


def principal(request:Request,authorization:Annotated[str|None,Header()]=None):
    if not authorization or not authorization.startswith('Bearer '):raise IntegrationFailure('UNAUTHORIZED',401)
    service=integration_service(request)
    p=service.authenticate(authorization[7:])
    request.state.integration_principal=p
    request.state.integration_bearer=authorization[7:]
    cls='read' if request.method=='GET' else 'upload' if request.url.path.endswith('/documents') else 'start' if request.url.path.endswith('/workflow') else 'write'
    service.repository.consume(p,cls)
    return p


Principal=Annotated[object,Depends(principal)]
Key=Annotated[str,Header(alias='Idempotency-Key',min_length=1,max_length=128)]


def channel(request,p):return external_channel(request,p)


@router.post('/oauth/token',response_model=TokenView)
async def token(request:Request,grant_type:str=Form(...),client_id:UUID=Form(...),client_secret:str=Form(...),scope:str|None=Form(None)):
    form=await request.form()
    if set(form)-{'grant_type','client_id','client_secret','scope'} or any(len(form.getlist(k))!=1 for k in form):
        raise IntegrationFailure('INVALID_INPUT',422)
    return await run_in_threadpool(integration_service(request).token,TokenRequest(
        grant_type=grant_type,client_id=client_id,client_secret=client_secret,scope=scope))


@router.post('/projects',response_model=IntakeView,status_code=201)
def create(body:ExternalProjectCreate,request:Request,p:Principal,key:Key):
    return channel(request,p).create(body,key)


@router.get('/projects/{project_id}/intake',response_model=IntakeView)
def read_intake(project_id:UUID,request:Request,p:Principal,version:int|None=None):
    return channel(request,p).read_intake(project_id,version)


@router.put('/projects/{project_id}/intake',response_model=IntakeView)
def update(project_id:UUID,body:ExternalIntakeUpdate,request:Request,p:Principal,key:Key):
    return channel(request,p).update(project_id,body,key)


@router.post('/projects/{project_id}/intake/confirm',response_model=IntakeView)
def confirm(project_id:UUID,body:ConfirmProjectIntake,request:Request,p:Principal,key:Key):
    return channel(request,p).confirm(project_id,body,key)


@router.get('/projects/{project_id}/documents',response_model=DocumentInputsView)
def documents(project_id:UUID,request:Request,p:Principal):
    return channel(request,p).documents(project_id)


@router.post('/projects/{project_id}/documents',response_model=DocumentInputsView,status_code=201)
async def upload(project_id:UUID,request:Request,p:Principal,key:Key,file:UploadFile=File(...),expected_version:int=Form(...,ge=1)):
    form=await request.form()
    if set(form)-{'file','expected_version'} or any(len(form.getlist(k))!=1 for k in form):
        raise IntegrationFailure('INVALID_INPUT',422)
    service=channel(request,p)
    from crossborder_compliance.domain.integrations import IntegrationScope
    ctx=service._context(IntegrationScope.DOCUMENT_UPLOAD,project_id)
    repo=service.canonical.documents(ctx).repository
    if repo.file_policy is None or repo.storage is None:raise IntegrationFailure('CAPABILITY_NOT_CONFIGURED',503)
    maximum=repo.file_policy.max_size_bytes
    content=await file.read(maximum+1)
    if len(content)>maximum:raise IntegrationFailure('DOCUMENT_REJECTED',413)
    return await run_in_threadpool(service.upload,project_id,
        DraftDocumentRequest(expected_version=expected_version,idempotency_key=key),
        file.filename or '',file.content_type or '',content)


@router.post('/projects/{project_id}/documents/{version_id}/parse',response_model=DocumentInputsView)
def parse(project_id:UUID,version_id:UUID,body:ConfirmProjectIntake,request:Request,p:Principal,key:Key):
    return channel(request,p).document_action(project_id,version_id,DraftDocumentRequest(expected_version=body.expected_version,idempotency_key=key),'parse')


@router.delete('/projects/{project_id}/documents/{version_id}',response_model=DocumentInputsView)
def unlink(project_id:UUID,version_id:UUID,body:ConfirmProjectIntake,request:Request,p:Principal,key:Key):
    return channel(request,p).document_action(project_id,version_id,DraftDocumentRequest(expected_version=body.expected_version,idempotency_key=key),'unlink')


@router.get('/projects/{project_id}/eligible-models',response_model=EligibleModelCatalog)
def eligible_models(project_id:UUID,request:Request,p:Principal):
    return channel(request,p).eligible_models(project_id)


@router.post('/projects/{project_id}/snapshots/{snapshot_id}/workflow',response_model=ExternalWorkflowAccepted,status_code=202)
def start(project_id:UUID,snapshot_id:UUID,body:WorkflowStart,request:Request,p:Principal,key:Key):
    return channel(request,p).start(project_id,snapshot_id,key)


@router.get('/workflows/{run_id}',response_model=WorkflowView)
def status(run_id:UUID,request:Request,p:Principal):return channel(request,p).status(run_id)


@router.get('/workflows/{run_id}/stage1-result',response_model=Stage1ComplianceResult)
def result(run_id:UUID,request:Request,p:Principal):return channel(request,p).result(run_id)


@router.get('/workflows/{run_id}/events',responses={200:{'content':{'text/event-stream':{}}}})
async def events(run_id:UUID,request:Request,p:Principal,last_event_id:Annotated[UUID|None,Header()]=None):
    service=channel(request,p)
    await run_in_threadpool(service.events,run_id,last_event_id)
    async def stream():
        cursor=last_event_id;start=time.monotonic();policy=service.integration.policy
        while time.monotonic()-start<policy.stream_duration_seconds:
            if await request.is_disconnected():return
            try:
                # Live credential and binding revalidation, including token TTL.
                await run_in_threadpool(service.integration.authenticate,request.state.integration_bearer)
                values=await run_in_threadpool(service.events,run_id,cursor)
            except IntegrationFailure:return
            for value in values:
                cursor=value.event_id
                yield f'id: {value.event_id}\nevent: {value.event_code}\ndata: {value.model_dump_json()}\n\n'
            yield ': heartbeat\n\n'
            await asyncio.sleep(policy.event_poll_seconds)
    return StreamingResponse(stream(),media_type='text/event-stream')


@router.websocket('/ws/workflows/{run_id}')
async def websocket_events(websocket:WebSocket,run_id:UUID):
    # Server integrations supply Authorization header; no bearer in URL/log/history.
    auth=websocket.headers.get('authorization','')
    if not auth.startswith('Bearer '):await websocket.close(code=4401);return
    request=SimpleWebsocketRequest(websocket)
    try:
        service=integration_service(request);p=await run_in_threadpool(service.authenticate,auth[7:])
        await run_in_threadpool(service.repository.consume,p,'read')
        ch=external_channel(request,p)
        await run_in_threadpool(ch.events,run_id)
    except Exception:await websocket.close(code=4403);return
    await websocket.accept()
    cursor=None;began=time.monotonic()
    try:
        while time.monotonic()-began<service.policy.stream_duration_seconds:
            await run_in_threadpool(service.authenticate,auth[7:])
            for value in await run_in_threadpool(ch.events,run_id,cursor):
                cursor=value.event_id
                await websocket.send_json(value.model_dump(mode='json'))
            await asyncio.sleep(service.policy.event_poll_seconds)
    except Exception:pass
    finally:
        try:await websocket.close(code=1000)
        except Exception:pass


class SimpleWebsocketRequest:
    def __init__(self,ws):
        self.app=ws.app
        from types import SimpleNamespace
        self.state=SimpleNamespace(request_id=uuid4().hex)
