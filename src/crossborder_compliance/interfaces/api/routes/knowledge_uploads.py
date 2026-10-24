"""Authenticated transport adaptation; no parsing, publication or compliance decisions."""

from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Request

from crossborder_compliance.application.knowledge_uploads import KnowledgeUploadService
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.domain.knowledge_upload import (
    AttachKnowledgeUpload,
    KnowledgeUploadMutation,
    KnowledgeUploadPartReceipt,
    KnowledgeUploadPartRequest,
    StartKnowledgeUpload,
)
from crossborder_compliance.infrastructure.knowledge_binary_storage import S3KnowledgeBinaryStore
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementCapabilityError,
)
from crossborder_compliance.infrastructure.persistence.knowledge_uploads import (
    PostgresKnowledgeUploads,
)
from crossborder_compliance.interfaces.api.knowledge_upload_schemas import (
    KnowledgeSignedPart,
    KnowledgeUploadPolicyView,
    KnowledgeUploadView,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])


def service(request, context):
    storage = getattr(request.app.state, "knowledge_binary_store", None)
    if storage is None:
        settings = get_settings()
        if settings.object_storage_secret_key == "change-me":
            raise KnowledgeManagementCapabilityError("KNOWLEDGE_BINARY_STORAGE_NOT_CONFIGURED")
        storage = S3KnowledgeBinaryStore(
            endpoint_url=settings.object_storage_endpoint,
            bucket=settings.object_storage_bucket,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
        )
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return KnowledgeUploadService(PostgresKnowledgeUploads(factory, context), storage)


def call(request, context, operation, *args):
    def execute():
        grant = {
            "start": "upload:create",
            "detail": "upload:read",
            "part_url": "upload:write",
            "acknowledge": "upload:write",
            "complete": "upload:complete",
            "cancel": "upload:cancel",
            "retry_scan": "upload:retry",
            "attach": "upload:attach",
        }[operation]
        require_management_permission(context, grant)
        if operation == "attach" or (
            operation == "start" and args[0].knowledge_version_id is not None
        ):
            require_management_permission(context, "document:write")
        if operation in {"detail", "retry_scan", "attach"}:
            factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(
                request
            )
            return getattr(PostgresKnowledgeUploads(factory, context), operation)(*args)
        owner = service(request, context)
        return getattr(owner, operation)(*args)

    try:
        return invoke(execute)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, {"code": "KNOWLEDGE_BINARY_STORAGE_UNAVAILABLE"}) from exc


@router.post("/upload-sessions", status_code=201, response_model=KnowledgeUploadView)
def create(body: StartKnowledgeUpload, request: Request, context: Context):
    return call(request, context, "start", body)


@router.get("/upload-sessions/{identity}", response_model=KnowledgeUploadView)
def detail(identity: UUID, request: Request, context: Context):
    return call(request, context, "detail", identity)


@router.post("/upload-sessions/{identity}/part-url", response_model=KnowledgeSignedPart)
def part_url(identity: UUID, body: KnowledgeUploadPartRequest, request: Request, context: Context):
    return call(request, context, "part_url", identity, body)


@router.post("/upload-sessions/{identity}/parts", response_model=KnowledgeUploadView)
def acknowledge(
    identity: UUID, body: KnowledgeUploadPartReceipt, request: Request, context: Context
):
    return call(request, context, "acknowledge", identity, body)


@router.post("/upload-sessions/{identity}/complete", response_model=KnowledgeUploadView)
def complete(identity: UUID, body: KnowledgeUploadMutation, request: Request, context: Context):
    return call(request, context, "complete", identity, body)


@router.post("/upload-sessions/{identity}/cancel", response_model=KnowledgeUploadView)
def cancel(identity: UUID, body: KnowledgeUploadMutation, request: Request, context: Context):
    return call(request, context, "cancel", identity, body)


@router.post("/upload-sessions/{identity}/retry", response_model=KnowledgeUploadView)
def retry(identity: UUID, body: KnowledgeUploadMutation, request: Request, context: Context):
    return call(request, context, "retry_scan", identity, body)


@router.post("/upload-sessions/{identity}/attach", response_model=KnowledgeUploadView)
def attach(identity: UUID, body: AttachKnowledgeUpload, request: Request, context: Context):
    return call(
        request,
        context,
        "attach",
        identity,
        body.knowledge_version_id,
        body.expected_record_version,
        body.idempotency_key,
    )


@router.get("/upload-policy", response_model=KnowledgeUploadPolicyView)
def upload_policy(request: Request, context: Context):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return invoke(PostgresKnowledgeUploads(factory, context).policy_view)
