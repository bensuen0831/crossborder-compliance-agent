"""Import HTTP adaptation delegates tenant, actor, CAS and canonical mapping to owners."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from crossborder_compliance.domain.knowledge_batches import (
    ConfirmKnowledgeBatchItems,
    CreateKnowledgeImportBatch,
)
from crossborder_compliance.domain.knowledge_upload import KnowledgeUploadMutation
from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
    PostgresKnowledgeImportBatches,
)
from crossborder_compliance.interfaces.api.knowledge_batch_schemas import KnowledgeBatchView
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])


def repository(request, context):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return PostgresKnowledgeImportBatches(factory, context)


@router.post("/import-batches", status_code=201, response_model=KnowledgeBatchView)
def create(body: CreateKnowledgeImportBatch, request: Request, context: Context):
    return invoke(lambda: repository(request, context).create(body))


@router.get("/import-batches/{identity}", response_model=KnowledgeBatchView)
def detail(
    identity: UUID,
    request: Request,
    context: Context,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return invoke(
        lambda: repository(request, context).detail(identity, page=page, page_size=page_size)
    )


@router.post("/import-batches/{identity}/confirm-items", response_model=KnowledgeBatchView)
def confirm(identity: UUID, body: ConfirmKnowledgeBatchItems, request: Request, context: Context):
    return invoke(lambda: repository(request, context).confirm_items(identity, body))


@router.post("/import-batches/{identity}/cancel", response_model=KnowledgeBatchView)
def cancel(identity: UUID, body: KnowledgeUploadMutation, request: Request, context: Context):
    return invoke(lambda: repository(request, context).cancel(identity, body))


@router.post("/import-batches/{identity}/retry", response_model=KnowledgeBatchView)
def retry(identity: UUID, body: KnowledgeUploadMutation, request: Request, context: Context):
    return invoke(lambda: repository(request, context).retry(identity, body))
