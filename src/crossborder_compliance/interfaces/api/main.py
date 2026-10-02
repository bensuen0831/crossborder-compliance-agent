from fastapi import FastAPI

from crossborder_compliance.config import get_settings
from crossborder_compliance.interfaces.api.routes.admin_metadata import router as admin_metadata_router
from crossborder_compliance.interfaces.api.routes.health import router as health_router
from crossborder_compliance.interfaces.api.routes.metadata import router as metadata_router
from crossborder_compliance.interfaces.api.routes.documents import router as documents_router
from crossborder_compliance.interfaces.api.routes.context_resolution import router as context_resolution_router
from crossborder_compliance.interfaces.api.routes.knowledge import router as knowledge_router
from crossborder_compliance.observability.logging import configure_logging
from crossborder_compliance.observability.tracing import configure_tracing

from crossborder_compliance.interfaces.api.routes.retrieval import router as retrieval_router

configure_logging()
settings = get_settings()
configure_tracing(settings.otel_service_name)

app = FastAPI(title="Cross-border Compliance Agent", version="0.7.0-phase1g")
app.include_router(health_router)
app.include_router(metadata_router)
app.include_router(admin_metadata_router)
app.include_router(documents_router)
app.include_router(context_resolution_router)
app.include_router(knowledge_router)

app.include_router(retrieval_router)
