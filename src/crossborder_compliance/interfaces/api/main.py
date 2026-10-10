from contextlib import asynccontextmanager

from fastapi import FastAPI

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.compliance_profile_worker import (
    ComplianceProfilePublicationWorker,
)
from crossborder_compliance.infrastructure.knowledge_publication_worker import (
    KnowledgePublicationWorker,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.interfaces.api.routes.admin_metadata import (
    router as admin_metadata_router,
)
from crossborder_compliance.interfaces.api.routes.classification import (
    router as classification_router,
)
from crossborder_compliance.interfaces.api.routes.context_resolution import (
    router as context_resolution_router,
)
from crossborder_compliance.interfaces.api.routes.country_compliance import (
    router as country_compliance_router,
)
from crossborder_compliance.interfaces.api.routes.decisions import router as decisions_router
from crossborder_compliance.interfaces.api.routes.documents import router as documents_router
from crossborder_compliance.interfaces.api.routes.health import router as health_router
from crossborder_compliance.interfaces.api.routes.knowledge import router as knowledge_router
from crossborder_compliance.interfaces.api.routes.llm_models import router as llm_models_router
from crossborder_compliance.interfaces.api.routes.metadata import router as metadata_router
from crossborder_compliance.interfaces.api.routes.model_providers import bindings_router
from crossborder_compliance.interfaces.api.routes.model_providers import (
    router as model_providers_router,
)
from crossborder_compliance.interfaces.api.routes.retrieval import router as retrieval_router
from crossborder_compliance.observability.logging import configure_logging
from crossborder_compliance.observability.tracing import configure_tracing

configure_logging()
settings = get_settings()
configure_tracing(settings.otel_service_name)


@asynccontextmanager
async def lifespan(app):
    sessions = getattr(app.state, "knowledge_session_factory", None)
    owned_engine = None
    if sessions is None:
        owned_engine, sessions = build_session_factory(settings.database_url)
    # One deployment-owned pool, not a fresh pool for every HTTP request.
    # RepositoryContext and live authorization remain request scoped.
    app.state.knowledge_session_factory = sessions
    worker = KnowledgePublicationWorker(
        sessions, settings.redis_url, embedding=getattr(app.state, "query_embedding_port", None)
    )
    app.state.knowledge_publication_worker = worker
    worker.start()
    profile_worker = ComplianceProfilePublicationWorker(sessions)
    app.state.compliance_profile_worker = profile_worker
    profile_worker.start()
    # Canonical business execution remains behind the existing runtime; this
    # worker owns only durable channel delivery and webhook retries.
    from crossborder_compliance.infrastructure.integration_worker import IntegrationDeliveryWorker
    integration_worker = IntegrationDeliveryWorker(app)
    app.state.integration_delivery_worker = integration_worker
    integration_worker.start()
    try:
        yield
    finally:
        integration_worker.stop()
        profile_worker.stop()
        worker.stop()
        if owned_engine is not None:
            owned_engine.dispose()
            if app.state.knowledge_session_factory is sessions:
                del app.state.knowledge_session_factory


app = FastAPI(lifespan=lifespan, title="Cross-border Compliance Agent", version="0.7.0-phase1g")
app.include_router(health_router)
app.include_router(metadata_router)
from crossborder_compliance.interfaces.api.routes.integrations import admin_router as integration_admin_router
app.include_router(integration_admin_router)
app.include_router(admin_metadata_router)
app.include_router(documents_router)
app.include_router(context_resolution_router)
app.include_router(classification_router)
app.include_router(country_compliance_router)
app.include_router(decisions_router)

# Specific write-only credential routes precede generic /admin/{kind} routes.
app.include_router(model_providers_router)
app.include_router(bindings_router)
app.include_router(llm_models_router)
app.include_router(knowledge_router)

app.include_router(retrieval_router)
