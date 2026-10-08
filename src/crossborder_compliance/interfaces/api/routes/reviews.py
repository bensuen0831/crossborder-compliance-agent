"""Typed authorized review transport; browser supplies neither actor nor thread."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from crossborder_compliance.application.review_services import (
    HumanReviewService,
    ReviewCorrectionRequest,
    ReviewDecisionRequest,
    ReviewLineage,
    ReviewPage,
    ReviewResumeRequest,
    ReviewView,
)
from crossborder_compliance.application.workflow_skeleton import WorkflowDeliveryRetryableFailure
from crossborder_compliance.domain.contracts import ReviewStatus
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresReviewRepository,
)
from crossborder_compliance.infrastructure.persistence.review_governance import ReviewConflict
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.workflow import (
    authorized_intake_context,
    delivery,
    sessions,
)

router = APIRouter(prefix="/api/v1/reviews", tags=["human-review"])
Context = Annotated[RepositoryContext, Depends(get_repository_context)]


def service(request, context):
    def current_delivery(review):
        current = authorized_intake_context(request, context, review.project_id)
        return delivery(
            request,
            current,
            review.project_id,
            review.analysis_snapshot_id,
            "review",
            review.workflow_run_id,
        )[1]

    def successor_delivery(review, lineage):
        current = authorized_intake_context(request, context, review.project_id)
        _, runtime, factory, run_id = delivery(
            request,
            current,
            review.project_id,
            lineage.successor_snapshot_id,
            "execute",
            lineage.successor_workflow_run_id,
        )
        runtime.inspect_checkpoint_state(run_id)
        runtime.start(run_id, factory.initial_state(run_id))

    return HumanReviewService(
        PostgresReviewRepository(sessions(request), context), current_delivery, successor_delivery
    )


def translate(exc):
    if isinstance(exc, (LookupError, PermissionError)):
        raise HTTPException(404, "REVIEW_NOT_FOUND") from exc
    if isinstance(exc, WorkflowDeliveryRetryableFailure):
        raise HTTPException(503, "WORKFLOW_DELIVERY_BUSY") from exc
    if isinstance(exc, ReviewConflict):
        raise HTTPException(409, str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(409, "CORRECTION_VALIDATION_FAILED") from exc
    raise exc


@router.get("", response_model=ReviewPage)
def list_reviews(
    request: Request,
    context: Context,
    status: ReviewStatus | None = None,
    project_id: UUID | None = None,
    review_type: str | None = None,
    owning_stage: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    order: Literal["CREATED_DESC", "CREATED_ASC"] = "CREATED_DESC",
):
    try:
        return service(request, context).list(
            status=status,
            project_id=project_id,
            review_type=review_type,
            owning_stage=owning_stage,
            created_after=created_after,
            created_before=created_before,
            offset=offset,
            limit=limit,
            order=order,
        )
    except Exception as exc:
        translate(exc)


@router.get("/{review_id}", response_model=ReviewView)
def read_review(review_id: UUID, request: Request, context: Context):
    try:
        return service(request, context).read(review_id)
    except Exception as exc:
        translate(exc)


@router.post("/{review_id}/decisions", response_model=ReviewView)
def decide(review_id: UUID, body: ReviewDecisionRequest, request: Request, context: Context):
    try:
        return service(request, context).decide(review_id, body)
    except Exception as exc:
        translate(exc)


@router.post("/{review_id}/corrections", response_model=ReviewLineage)
def correct(review_id: UUID, body: ReviewCorrectionRequest, request: Request, context: Context):
    try:
        return service(request, context).correct(review_id, body)
    except Exception as exc:
        translate(exc)


@router.post("/{review_id}/resume", response_model=ReviewView)
def resume(
    review_id: UUID,
    request: Request,
    context: Context,
    body: ReviewResumeRequest | None = Body(default=None),
):
    # No browser-supplied actor/thread/token/stage. Reuse the immutable decision.
    try:
        return service(request, context).resume(review_id)
    except Exception as exc:
        translate(exc)


@router.post("/{review_id}/successor/start", response_model=ReviewView)
def continue_successor(
    review_id: UUID,
    request: Request,
    context: Context,
    body: ReviewResumeRequest | None = Body(default=None),
):
    try:
        return service(request, context).continue_successor(review_id)
    except Exception as exc:
        translate(exc)
