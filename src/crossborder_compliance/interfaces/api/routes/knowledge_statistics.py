"""Authenticated SQL statistics; client data never supplies counts or tenant scope."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from crossborder_compliance.infrastructure.persistence.knowledge_statistics import (
    PostgresKnowledgeStatistics,
)
from crossborder_compliance.interfaces.api.knowledge_management_schemas import (
    KnowledgeLifecycle,
    KnowledgeStatisticsView,
    KnowledgeCrossTabView,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])


@router.get("/statistics", response_model=KnowledgeStatisticsView)
def summary(
    request: Request,
    context: Context,
    query: str = Query(default="", max_length=250),
    label_id: UUID | None = None,
    label_ids: Annotated[list[UUID] | None, Query(max_length=64)] = None,
    lifecycle: KnowledgeLifecycle | None = None,
    language: str | None = Query(default=None, max_length=80),
):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return invoke(
        PostgresKnowledgeStatistics(factory, context).summary,
        query=query,
        label_id=label_id,
        label_ids=label_ids or (),
        lifecycle=lifecycle,
        language=language,
    )


@router.get("/statistics/cross-tab", response_model=KnowledgeCrossTabView)
def cross_tab(
    request: Request, context: Context,
    dimension: Literal["category", "topic", "language", "format", "status", "source"],
    query: str = Query(default="", max_length=250),
    label_id: UUID | None = None,
    label_ids: Annotated[list[UUID] | None, Query(max_length=64)] = None,
    lifecycle: KnowledgeLifecycle | None = None,
    language: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100),
):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return invoke(PostgresKnowledgeStatistics(factory, context).cross_tab, dimension=dimension,
        query=query, label_id=label_id, label_ids=label_ids or (), lifecycle=lifecycle, language=language,
        page=page, page_size=page_size)
