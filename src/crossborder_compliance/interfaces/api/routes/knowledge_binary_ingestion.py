"""Native original-file ingestion delegates to the existing canonical Knowledge service."""

from uuid import UUID

from fastapi import APIRouter, Request

from crossborder_compliance.application.knowledge_services import KnowledgeIngestionService
from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
    PostgresKnowledgeImportBatches,
)
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)
from crossborder_compliance.interfaces.api.knowledge_binary_ingestion_schemas import (
    KnowledgeBinaryIngestionRequest,
    KnowledgeBinaryIngestionView,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])


@router.post(
    "/versions/{identity}/binary-ingestion",
    status_code=202,
    response_model=KnowledgeBinaryIngestionView,
)
def ingest(
    identity: UUID, body: KnowledgeBinaryIngestionRequest, request: Request, context: Context
):
    def execute():
        factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
        owner = PostgresKnowledgeRepository(factory, context)
        queue = getattr(request.app.state, "knowledge_queue", None)
        run = KnowledgeIngestionService(owner, queue=queue).ingest(
            str(identity), body.model_dump(mode="json")
        )
        work = PostgresKnowledgeImportBatches(factory, context).queue_existing_ingestion(
            run["ingestion_run_id"]
        )
        return {**owner.get_run(run["ingestion_run_id"]), "batch_id": work["batch_id"]}

    return invoke(execute)
