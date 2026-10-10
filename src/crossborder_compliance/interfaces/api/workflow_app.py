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

from crossborder_compliance.interfaces.api.routes.external import router as external_router
app.include_router(external_router)


@app.get('/api/v1/external/openapi.json',include_in_schema=False)
def external_contract():
    from crossborder_compliance.interfaces.api.external_openapi import external_openapi
    return external_openapi()
