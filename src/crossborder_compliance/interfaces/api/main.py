from fastapi import FastAPI
from crossborder_compliance.config import get_settings
from crossborder_compliance.interfaces.api.routes.health import router as health_router
from crossborder_compliance.interfaces.api.routes.metadata import router as metadata_router
from crossborder_compliance.observability.logging import configure_logging
from crossborder_compliance.observability.tracing import configure_tracing

configure_logging(); settings=get_settings(); configure_tracing(settings.otel_service_name)
app=FastAPI(title="Cross-border Compliance Agent",version="0.1.0-phase1a")
app.include_router(health_router); app.include_router(metadata_router)
