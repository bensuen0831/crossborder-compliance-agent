from contextlib import asynccontextmanager

from fastapi import FastAPI

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.knowledge_publication_worker import (
    KnowledgePublicationWorker,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.interfaces.api.routes.admin_metadata import (
    router as admin_metadata_router,
)
from crossborder_compliance.interfaces.api.routes.context_resolution import (
    router as context_resolution_router,
)
from crossborder_compliance.interfaces.api.routes.documents import router as documents_router
from crossborder_compliance.interfaces.api.routes.health import router as health_router
from crossborder_compliance.interfaces.api.routes.knowledge import router as knowledge_router
from crossborder_compliance.interfaces.api.routes.metadata import router as metadata_router
from crossborder_compliance.interfaces.api.routes.retrieval import router as retrieval_router
from crossborder_compliance.interfaces.api.routes.classification import router as classification_router
from crossborder_compliance.observability.logging import configure_logging
from crossborder_compliance.observability.tracing import configure_tracing

configure_logging()
settings = get_settings()
configure_tracing(settings.otel_service_name)


@asynccontextmanager
async def lifespan(app):
    sessions = (
        getattr(app.state, "knowledge_session_factory", None)
        or build_session_factory(settings.database_url)[1]
    )
    worker = KnowledgePublicationWorker(
        sessions, settings.redis_url, embedding=getattr(app.state, "query_embedding_port", None)
    )
    app.state.knowledge_publication_worker = worker
    worker.start()
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(lifespan=lifespan, title="Cross-border Compliance Agent", version="0.7.0-phase1g")
app.include_router(health_router)
app.include_router(metadata_router)
app.include_router(admin_metadata_router)
app.include_router(documents_router)
app.include_router(context_resolution_router)
app.include_router(knowledge_router)

app.include_router(retrieval_router)
app.include_router(classification_router)
