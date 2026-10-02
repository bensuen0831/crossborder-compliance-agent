from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from crossborder_compliance.application.context_services import ContextResolutionService
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.context_repositories import (
    PostgresContextResolutionRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)
from crossborder_compliance.interfaces.api.context_schemas import (
    ContextConflictDTO, ContextConflictResolveRequestDTO,
    ContextResolutionRunRequestDTO, ContextResolutionRunResponseDTO,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context

router = APIRouter(prefix="/api/v1", tags=["context-resolution"])


def _repo(request: Request) -> PostgresContextResolutionRepository:
    ctx = get_repository_context(request)
    sf = build_session_factory(get_settings().database_url)[1]
    return PostgresContextResolutionRepository(sf, ctx)


def _service(request: Request) -> ContextResolutionService:
    injected = getattr(request.app.state, "context_resolution_service", None)
    if injected is not None:
        return injected
    return ContextResolutionService(_repo(request))


@router.get("/projects/{project_id}/business-context")
def get_business_context(project_id: UUID, request: Request):
    return _repo(request).get_business_context(project_id)


@router.get("/projects/{project_id}/product-context")
def get_product_context(project_id: UUID, request: Request):
    return _repo(request).get_product_context(project_id)


@router.get("/projects/{project_id}/scenario-context")
def get_scenario_context(project_id: UUID, request: Request):
    return _repo(request).get_scenario_context(project_id)


@router.get("/projects/{project_id}/systems")
def get_systems(project_id: UUID, request: Request):
    return _repo(request).get_systems(project_id)


@router.get("/projects/{project_id}/parties")
def get_parties(project_id: UUID, request: Request):
    return _repo(request).get_parties(project_id)


@router.get("/projects/{project_id}/data-items")
def get_data_items(project_id: UUID, request: Request):
    return _repo(request).get_data_items(project_id)


@router.get("/projects/{project_id}/data-groups")
def get_data_groups(project_id: UUID, request: Request):
    return _repo(request).get_data_groups(project_id)


@router.get("/projects/{project_id}/data-flows")
def get_data_flows(project_id: UUID, request: Request):
    return _repo(request).get_data_flows(project_id)


@router.get("/projects/{project_id}/jurisdiction-context")
def get_jurisdiction_context(project_id: UUID, request: Request):
    return _repo(request).get_jurisdiction_context(project_id)


@router.get("/projects/{project_id}/context-resolution")
def get_context_resolution(project_id: UUID, request: Request):
    result = _repo(request).get_context_resolution(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="context resolution not found")
    return asdict(result)


@router.get("/projects/{project_id}/context-conflicts", response_model=list[ContextConflictDTO])
def get_context_conflicts(project_id: UUID, request: Request):
    return _repo(request).list_conflicts(project_id)


@router.post(
    "/projects/{project_id}/context-resolution/run",
    response_model=ContextResolutionRunResponseDTO,
)
def run_context_resolution(
    project_id: UUID, payload: ContextResolutionRunRequestDTO, request: Request
):
    service = _service(request)
    try:
        return service.run(
            project_id,
            selected_product_scope=tuple(payload.selected_product_scope),
            detected_product_scope=tuple(payload.detected_product_scope),
            selected_scenarios=tuple(payload.selected_scenarios),
            detected_scenarios=tuple(payload.detected_scenarios),
            systems=tuple(payload.systems), devices=tuple(payload.devices),
            parties=tuple(payload.parties), jurisdictions=tuple(payload.jurisdictions),
            data_item_product_bindings=payload.data_item_product_bindings,
            data_item_flow_bindings=payload.data_item_flow_bindings,
            data_groups=tuple(x.model_dump() for x in payload.data_groups),
            workflow_run_id=payload.workflow_run_id,
        )
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/context-conflicts/{conflict_id}/resolve",
    response_model=ContextConflictDTO,
)
def resolve_context_conflict(
    conflict_id: UUID, payload: ContextConflictResolveRequestDTO, request: Request
):
    repo = _repo(request)
    try:
        return repo.resolve_conflict(
            conflict_id, resolution=payload.resolution, resolved_by=payload.resolved_by,
            expected_record_version=payload.expected_record_version,
        )
    except OptimisticConcurrencyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
