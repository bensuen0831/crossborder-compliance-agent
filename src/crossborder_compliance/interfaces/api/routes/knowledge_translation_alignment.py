"""Scoped management of human clause alignment over canonical knowledge translations."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from crossborder_compliance.domain.knowledge_translation_alignment import (
    CreateTranslationAlignment,
    ReviewTranslationAlignment,
)
from crossborder_compliance.infrastructure.persistence.knowledge_translation_alignment import (
    PostgresKnowledgeTranslationAlignment,
)
from crossborder_compliance.interfaces.api.knowledge_management_schemas import (
    TranslationAlignmentPage,
    TranslationAlignmentView,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])


def owner(request, context):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return PostgresKnowledgeTranslationAlignment(factory, context)


@router.post("/translation-alignments", status_code=201, response_model=TranslationAlignmentView)
def create(body: CreateTranslationAlignment, request: Request, context: Context):
    return invoke(owner(request, context).create, body)


@router.get(
    "/documents/versions/{version_id}/translation-alignments",
    response_model=TranslationAlignmentPage,
)
def list_alignments(
    version_id: UUID,
    request: Request,
    context: Context,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return invoke(owner(request, context).list, version_id, page=page, page_size=page_size)


@router.post(
    "/translation-alignments/{translation_id}/review", response_model=TranslationAlignmentView
)
def review(
    translation_id: UUID, body: ReviewTranslationAlignment, request: Request, context: Context
):
    return invoke(owner(request, context).review, translation_id, body)
