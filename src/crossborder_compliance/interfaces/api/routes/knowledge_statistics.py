"""Authenticated SQL statistics; client data never supplies counts or tenant scope."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from crossborder_compliance.infrastructure.persistence.knowledge_statistics import (
    PostgresKnowledgeStatistics,
)
from crossborder_compliance.interfaces.api.knowledge_management_schemas import (
    KnowledgeLifecycle,
    KnowledgeStatisticsView,
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
    lifecycle: KnowledgeLifecycle | None = None,
    language: str | None = Query(default=None, max_length=80),
):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return invoke(
        PostgresKnowledgeStatistics(factory, context).summary,
        query=query,
        label_id=label_id,
        lifecycle=lifecycle,
        language=language,
    )
