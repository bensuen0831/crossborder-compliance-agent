"""Reference-only transport over the existing trusted-host workflow delivery.

The host prepares the durable run and reconstructible pinned plan through the
existing application semantics. This router owns no plan/run persistence.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from crossborder_compliance.application.workflow_formal import FormalWorkflowPlan
from crossborder_compliance.application.workflow_skeleton import WorkflowDeliveryRetryableFailure
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.classification_repository import (
    PostgresFormalClassificationRepository,
)
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)
from crossborder_compliance.infrastructure.persistence.workflow_read_projection import (
    WorkflowReadProjection,
)
from crossborder_compliance.infrastructure.workflow_formal_composition import (
    formal_workflow_runtime,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context

router = APIRouter(prefix="/api/v1", tags=["canonical-workflow"])
Context = Annotated[RepositoryContext, Depends(get_repository_context)]
RefStep = Literal[
    "requirement",
    "formal_context",
    "data_flow",
    "jurisdiction",
    "knowledge_scope",
    "retrieval",
    "sufficiency",
    "classification",
    "applicability",
]


class WorkflowStart(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_run_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    status: Literal["RUNNING", "COMPLETED", "REVIEW_REQUIRED", "WARNING", "FAILED", "CANCELLED"]
    current_step: str | None = Field(default=None, max_length=40)
    result_refs: dict[RefStep, tuple[UUID, ...]] = Field(default_factory=dict, max_length=9)
    reason_codes: tuple[str, ...] = Field(default=(), max_length=16)
    review_id: UUID | None = None
    fallback_ref: UUID | None = None


def sessions(request):
    return (
        getattr(request.app.state, "knowledge_session_factory", None)
        or build_session_factory(get_settings().database_url)[1]
    )


def scope(sf, context, project_id, snapshot_id, operation):
    if (
        f"workflow:{operation}" not in context.permission.scopes
        or f"project:{project_id}:comply" not in context.permission.scopes
    ):
        raise LookupError("workflow resource not found")
    WorkflowReadProjection(sf, context).require_scope(project_id, snapshot_id)


def delivery(request, context, project_id, snapshot_id, operation, expected_run=None):
    sf = sessions(request)
    scope(sf, context, project_id, snapshot_id, operation)
    if operation == "execute":
        scope(sf, context, project_id, snapshot_id, "read")
    provider = getattr(request.app.state, "formal_workflow_host", None)
    if provider is None:
        raise HTTPException(409, "WORKFLOW_HOST_PLAN_REQUIRED")
    run_id, prepared = provider(context, project_id, snapshot_id)
    run_id, plan = UUID(str(run_id)), FormalWorkflowPlan.model_validate(prepared)
    if (plan.tenant_id, plan.project_id, plan.analysis_snapshot_id) != (
        context.tenant_id,
        project_id,
        snapshot_id,
    ) or (expected_run is not None and run_id != expected_run):
        raise LookupError("workflow resource not found")
    runtime, factory = formal_workflow_runtime(
        sessions=sf,
        context=context,
        plan=plan,
        postgres_uri=get_settings().langgraph_database_uri,
        request_id=str(getattr(request.state, "request_id", "workflow-http")),
    )
    factory.authorize(run_id, operation)
    return sf, runtime, factory, run_id


def view(sf, runtime, context, run_id, project_id, snapshot_id):
    # Internal adapter read is authorization-revalidated; no raw state/config
    # escapes. The external DTO contains only selected canonical identifiers.
    state = runtime.inspect_checkpoint_state(run_id)["values"]
    refs = {
        key: state.get("result_ref_sets", {}).get(key, [value])
        for key, value in state.get("result_refs", {}).items()
        if key in RefStep.__args__
    }
    for ref in refs.get("classification", []):
        result = PostgresFormalClassificationRepository(sf, context).get_result(UUID(ref))
        if (result["project_id"], result["analysis_snapshot_id"]) != (
            str(project_id),
            str(snapshot_id),
        ):
            raise LookupError("workflow resource not found")
    for ref in refs.get("applicability", []):
        result = PostgresCountryComplianceRepository(sf, context).read(UUID(ref))
        if (result.project_id, result.analysis_snapshot_id) != (project_id, snapshot_id):
            raise LookupError("workflow resource not found")
    for ref in refs.get("retrieval", []):
        result = PostgresRetrievalRepository(sf, context).scoped_saved_response(ref)
        query = result["query"]
        if (query["project_id"], query["analysis_snapshot_id"]) != (
            str(project_id),
            str(snapshot_id),
        ):
            raise LookupError("workflow resource not found")
    review_id = state.get("review_ref")
    if runtime.get_status(run_id) == "REVIEW_REQUIRED" and not review_id:
        review_id = WorkflowReadProjection(sf, context).pending_review(run_id)
    return WorkflowView(
        workflow_run_id=run_id,
        project_id=project_id,
        analysis_snapshot_id=snapshot_id,
        status=runtime.get_status(run_id),
        current_step=state.get("current_step"),
        result_refs=refs,
        reason_codes=state.get("reason_codes", ()),
        review_id=review_id,
        fallback_ref=state.get("fallback_ref"),
    )


def translate(exc):
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, (LookupError, PermissionError)):
        raise HTTPException(404, "workflow resource not found") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(409, "WORKFLOW_CONTEXT_NOT_READY") from exc
    if isinstance(exc, WorkflowDeliveryRetryableFailure):
        raise HTTPException(503, "WORKFLOW_DELIVERY_BUSY") from exc
    raise exc


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/workflow", response_model=WorkflowView)
def start(
    project_id: UUID, snapshot_id: UUID, body: WorkflowStart, request: Request, context: Context
):
    try:
        sf, runtime, factory, run_id = delivery(
            request, context, project_id, snapshot_id, "execute"
        )
        # Initialize the same official checkpointer before the delivery guard's
        # transaction; first concurrent-index DDL cannot wait on our own guard.
        # Trusted scope and canonical authorization have already passed.
        runtime.inspect_checkpoint_state(run_id)
        runtime.start(run_id, factory.initial_state(run_id))
        return view(sf, runtime, context, run_id, project_id, snapshot_id)
    except Exception as exc:
        translate(exc)


@router.get("/workflows/{run_id}", response_model=WorkflowView)
def read(run_id: UUID, request: Request, context: Context):
    try:
        sf = sessions(request)
        project_id, snapshot_id = WorkflowReadProjection(sf, context).run_scope(run_id)
        sf, runtime, _, _ = delivery(request, context, project_id, snapshot_id, "read", run_id)
        return view(sf, runtime, context, run_id, project_id, snapshot_id)
    except Exception as exc:
        translate(exc)
