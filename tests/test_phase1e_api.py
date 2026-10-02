from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)
from crossborder_compliance.interfaces.api.routes import context_resolution as routes


class Service:
    def run(self, project_id, **kwargs):
        return {
            "context_resolution_run_id":str(uuid4()),
            "project_id":str(project_id),
            "version":1,
            "statistics":{
                "raw_field_count":3,
                "normalized_data_item_count":1,
                "data_group_count":1,
                "data_flow_node_count":2,
                "data_flow_edge_count":1,
                "unresolved_count":0,
                "conflict_count":0,
                "review_required_count":0,
            },
            "review_task_ids":[],
            "confidence":1.0,
        }


class Repo:
    def __init__(self):
        self.conflict_id=uuid4()
    def list_conflicts(self, project_id):
        return [{
            "conflict_id":str(self.conflict_id),"project_id":str(project_id),
            "conflict_type":"PRODUCT_CONTEXT_CONFLICT","object_type":"PRODUCT_CONTEXT",
            "object_ids":[],"reason_code":"FIXTURE","details":{},"source_trace_ids":[],
            "confidence":1.0,"resolution_status":"OPEN","review_required":True,
            "record_version":1,
        }]
    def resolve_conflict(self, conflict_id, *, resolution, resolved_by, expected_record_version):
        if expected_record_version!=1:
            raise OptimisticConcurrencyError("context conflict version changed")
        return {
            "conflict_id":str(conflict_id),"project_id":str(uuid4()),
            "conflict_type":"PRODUCT_CONTEXT_CONFLICT","object_type":"PRODUCT_CONTEXT",
            "object_ids":[],"reason_code":"FIXTURE","details":{},"source_trace_ids":[],
            "confidence":1.0,"resolution_status":"RESOLVED","review_required":True,
            "record_version":2,
        }


def _app(authorized=True):
    app=FastAPI()
    tenant=uuid4()
    if authorized:
        @app.middleware("http")
        async def trusted(request:Request,call_next):
            request.state.repository_context=RepositoryContext.user(tenant,"phase1e-api")
            return await call_next(request)
        app.state.context_resolution_service=Service()
    app.include_router(routes.router)
    return app


def test_context_resolution_run_requires_trusted_context_and_returns_typed_result():
    project=uuid4()
    unauthorized=TestClient(_app(False))
    denied=unauthorized.post(f"/api/v1/projects/{project}/context-resolution/run",json={})
    assert denied.status_code==401

    client=TestClient(_app(True))
    response=client.post(
        f"/api/v1/projects/{project}/context-resolution/run",
        json={"selected_product_scope":[],"detected_product_scope":[]},
    )
    assert response.status_code==200
    body=response.json()
    assert body["project_id"]==str(project)
    assert body["statistics"]["raw_field_count"]==3
    assert body["statistics"]["normalized_data_item_count"]==1


def test_context_conflict_api_uses_optimistic_concurrency(monkeypatch):
    app=_app(True);fake=Repo()
    monkeypatch.setattr(routes,"_repo",lambda request:fake)
    client=TestClient(app)
    conflict=fake.conflict_id

    ok=client.post(
        f"/api/v1/context-conflicts/{conflict}/resolve",
        json={
            "resolution":{"effective_product_scope":[str(uuid4())]},
            "resolved_by":"reviewer","expected_record_version":1,
        },
    )
    assert ok.status_code==200
    assert ok.json()["resolution_status"]=="RESOLVED"

    stale=client.post(
        f"/api/v1/context-conflicts/{conflict}/resolve",
        json={
            "resolution":{"effective_product_scope":[str(uuid4())]},
            "resolved_by":"stale","expected_record_version":2,
        },
    )
    assert stale.status_code==409


def test_phase1e_required_api_paths_are_registered():
    paths={route.path for route in routes.router.routes}
    required={
        "/api/v1/projects/{project_id}/business-context",
        "/api/v1/projects/{project_id}/product-context",
        "/api/v1/projects/{project_id}/scenario-context",
        "/api/v1/projects/{project_id}/systems",
        "/api/v1/projects/{project_id}/parties",
        "/api/v1/projects/{project_id}/data-items",
        "/api/v1/projects/{project_id}/data-groups",
        "/api/v1/projects/{project_id}/data-flows",
        "/api/v1/projects/{project_id}/jurisdiction-context",
        "/api/v1/projects/{project_id}/context-resolution",
        "/api/v1/projects/{project_id}/context-conflicts",
        "/api/v1/projects/{project_id}/context-resolution/run",
        "/api/v1/context-conflicts/{conflict_id}/resolve",
    }
    assert required<=paths
