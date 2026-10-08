"""Extend the existing API instance with the reference-only workflow boundary.

Trusted deployments configure app.state.formal_workflow_host to reconstruct
their pinned application plan/run. Missing host configuration fails closed.
"""

from crossborder_compliance.interfaces.api.main import app
from crossborder_compliance.interfaces.api.routes.workflow import router

app.include_router(router)

from crossborder_compliance.interfaces.api.routes.intake import router as intake_router

app.include_router(intake_router)

from crossborder_compliance.interfaces.api.routes.intake_documents import router as intake_documents_router
app.include_router(intake_documents_router)

from crossborder_compliance.interfaces.api.routes.reviews import router as reviews_router
app.include_router(reviews_router)
