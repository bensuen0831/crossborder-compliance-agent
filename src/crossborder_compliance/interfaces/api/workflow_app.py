"""Extend the existing API instance with the reference-only workflow boundary.

Trusted deployments configure app.state.formal_workflow_host to reconstruct
their pinned application plan/run. Missing host configuration fails closed.
"""

from crossborder_compliance.interfaces.api.main import app
from crossborder_compliance.interfaces.api.routes.workflow import router

app.include_router(router)
