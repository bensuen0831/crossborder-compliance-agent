"""Document management channel; the knowledge lifecycle and content owner are reused."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from crossborder_compliance.application.knowledge_document_management import (
    KnowledgeDocumentManagementService,
)
from crossborder_compliance.domain.knowledge_management import (
    CreateManagedKnowledgeDocument,
    CreateManagedKnowledgeVersion,
    EditManagedKnowledgeVersion,
    MutateTaxonomy,
)
from crossborder_compliance.infrastructure.persistence.knowledge_document_management import (
    PostgresKnowledgeDocumentManagement,
)
from crossborder_compliance.interfaces.api.knowledge_management_schemas import (
    KnowledgeDocumentPreview,
    ManagedKnowledgeDocumentDeletion,
    ManagedKnowledgeDocumentDetail,
    ManagedKnowledgeDocumentImpact,
    ManagedKnowledgeDocumentPage,
    ManagedKnowledgeVersionMutation,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])


def service(request, context):
    return KnowledgeDocumentManagementService(
        PostgresKnowledgeDocumentManagement(sessions(request), context), context
    )


@router.get("/documents", response_model=ManagedKnowledgeDocumentPage)
def document_list(
    request: Request,
    context: Context,
    query: str = Query(default="", max_length=250),
    label_id: UUID | None = None,
    lifecycle: Literal[
        "DRAFT",
        "INGESTED",
        "VALIDATED",
        "PENDING_REVIEW",
        "APPROVED",
        "ACTIVE",
        "SUPERSEDED",
        "EXPIRED",
        "ARCHIVED",
    ]
    | None = None,
    language: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    sort: Literal["updated_desc", "title_asc", "created_desc"] = "updated_desc",
):
    return invoke(
        service(request, context).list,
        query=query,
        label_id=label_id,
        lifecycle=lifecycle,
        language=language,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.post("/documents", status_code=201, response_model=ManagedKnowledgeVersionMutation)
def document_create(body: CreateManagedKnowledgeDocument, request: Request, context: Context):
    return invoke(service(request, context).mutate, "CREATE", None, body)


@router.get("/documents/{document_id}", response_model=ManagedKnowledgeDocumentDetail)
def document_detail(document_id: UUID, request: Request, context: Context):
    return invoke(service(request, context).detail, document_id)


@router.get("/documents/{document_id}/impact", response_model=ManagedKnowledgeDocumentImpact)
def document_impact(document_id: UUID, request: Request, context: Context):
    return invoke(service(request, context).impact, document_id)


@router.post(
    "/documents/{document_id}/versions",
    status_code=201,
    response_model=ManagedKnowledgeVersionMutation,
)
def document_new_version(
    document_id: UUID, body: CreateManagedKnowledgeVersion, request: Request, context: Context
):
    return invoke(service(request, context).mutate, "NEW_VERSION", document_id, body)


@router.patch("/documents/versions/{version_id}", response_model=ManagedKnowledgeVersionMutation)
def document_edit(
    version_id: UUID, body: EditManagedKnowledgeVersion, request: Request, context: Context
):
    return invoke(service(request, context).mutate, "EDIT_DRAFT", version_id, body)


@router.delete("/documents/{document_id}", response_model=ManagedKnowledgeDocumentDeletion)
def document_delete(document_id: UUID, body: MutateTaxonomy, request: Request, context: Context):
    return invoke(service(request, context).mutate, "DELETE_DRAFT", document_id, body)


def lifecycle_endpoint(operation):
    def endpoint(version_id: UUID, body: MutateTaxonomy, request: Request, context: Context):
        return invoke(service(request, context).mutate, operation, version_id, body)

    return endpoint


for path, operation in {
    "validate": "VALIDATE",
    "submit-review": "SUBMIT_REVIEW",
    "approve": "APPROVE",
    "publish": "PUBLISH",
    "expire": "EXPIRE",
    "supersede": "SUPERSEDE",
    "archive": "ARCHIVE",
}.items():
    router.add_api_route(
        "/documents/versions/{version_id}/" + path,
        lifecycle_endpoint(operation),
        methods=["POST"],
        response_model=ManagedKnowledgeVersionMutation,
        name="kb_document_" + path,
    )


@router.get("/documents/versions/{version_id}/preview", response_model=KnowledgeDocumentPreview)
def document_preview(
    version_id: UUID,
    request: Request,
    context: Context,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return invoke(
        service(request, context).repository.preview, version_id, page=page, page_size=page_size
    )


@router.get("/documents/versions/{version_id}/original", response_class=StreamingResponse)
def document_original(version_id: UUID, request: Request, context: Context):
    from pathlib import PurePosixPath
    from urllib.parse import quote

    from crossborder_compliance.interfaces.api.routes.knowledge_uploads import service as uploads

    def open_original():
        original = service(request, context).repository.original(version_id)
        storage = uploads(request, context).storage
        if original["artifact_ref"] != f"s3://{storage.bucket}/{original['object_key']}":
            raise ValueError("KNOWLEDGE_ORIGINAL_PIN_MISMATCH")
        body = storage.client.get_object(
            Bucket=storage.bucket, Key=original["object_key"], VersionId=original["object_version"]
        )
        if body["ContentLength"] != original["byte_size"]:
            body["Body"].close()
            raise ValueError("KNOWLEDGE_ORIGINAL_SIZE_MISMATCH")
        return original, body["Body"]

    original, body = invoke(open_original)

    def chunks():
        try:
            while chunk := body.read(1024 * 1024):
                yield chunk
        finally:
            body.close()

    name = quote(PurePosixPath(original["relative_path"]).name, safe="")
    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(original["byte_size"]),
            "Content-Disposition": "attachment; filename*=UTF-8''" + name,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )
