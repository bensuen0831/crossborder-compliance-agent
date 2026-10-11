"""Typed production intake transport; browser facts never carry authority."""

from functools import partial
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import DBAPIError, IntegrityError

from crossborder_compliance.application.candidate_governance_services import (
    CandidateDecisionReceipt,
    CandidatePreview,
    DocumentCandidateGovernanceService,
    PrepareDocumentCandidates,
    ResolveDocumentCandidates,
)
from crossborder_compliance.application.intake_services import (
    ConfirmProjectIntake,
    CreateProjectFromIntake,
    IntakeView,
    UpdateIntakeDraft,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.intake_composition import (
    intake_service,
    prepare_snapshot,
)
from crossborder_compliance.infrastructure.persistence.candidate_governance import (
    PostgresCandidateGovernance,
)
from crossborder_compliance.infrastructure.persistence.project_intake import IntakeConflict
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1", tags=["project-intake"])
Context = Annotated[RepositoryContext, Depends(get_repository_context)]


def invoke(request, context, operation, *args):
    try:
        secret_factory = getattr(request.app.state, "llm_secret_store_factory", None)
        preparer = getattr(request.app.state, "intake_snapshot_preparer", None) or partial(
            prepare_snapshot,
            llm_dependencies={
                "storage": getattr(request.app.state, "document_object_storage", None),
                "secrets": secret_factory(context) if secret_factory else None,
                "redaction": getattr(request.app.state, "llm_data_redaction_service", None),
            },
        )
        return getattr(intake_service(sessions(request), context, preparer), operation)(*args)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(404, "intake resource not found") from exc
    except IntakeConflict as exc:
        code = str(exc)
        raise HTTPException(
            409,
            code
            if code.startswith(("CANDIDATE_", "INVALID_CANDIDATE_"))
            else "INTAKE_VERSION_OR_IDEMPOTENCY_CONFLICT",
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(409, "INTAKE_VERSION_OR_IDEMPOTENCY_CONFLICT") from exc
    except DBAPIError as exc:
        # A concurrent REPEATABLE READ confirmation must be retried from a
        # fresh authorized transaction, never surfaced as a false confirmation.
        if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
            raise HTTPException(409, "INTAKE_CONCURRENT_TRANSACTION_RETRY") from exc
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/projects", response_model=IntakeView, status_code=201)
def create(body: CreateProjectFromIntake, request: Request, context: Context):
    return invoke(request, context, "create", body)


@router.get("/projects/{project_id}/intake", response_model=IntakeView)
def read(project_id: UUID, request: Request, context: Context, version: int | None = None):
    return invoke(request, context, "read", project_id, version)


@router.put("/projects/{project_id}/intake", response_model=IntakeView)
def update(project_id: UUID, body: UpdateIntakeDraft, request: Request, context: Context):
    return invoke(request, context, "update", project_id, body)


@router.post("/projects/{project_id}/intake/confirm", response_model=IntakeView)
def confirm(project_id: UUID, body: ConfirmProjectIntake, request: Request, context: Context):
    return invoke(request, context, "confirm", project_id, body)


def candidate_invoke(request, context, operation, *args):
    secret_factory = getattr(request.app.state, "llm_secret_store_factory", None)
    service = DocumentCandidateGovernanceService(
        PostgresCandidateGovernance(
            sessions(request),
            context,
            storage=getattr(request.app.state, "document_object_storage", None),
            secrets=secret_factory(context) if secret_factory else None,
            redaction=getattr(request.app.state, "llm_data_redaction_service", None),
        )
    )
    try:
        return getattr(service, operation)(*args)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(404, "candidate resource not found") from exc
    except IntakeConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(409, "CANDIDATE_CONCURRENT_TRANSACTION_RETRY") from exc
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
            raise HTTPException(409, "CANDIDATE_CONCURRENT_TRANSACTION_RETRY") from exc
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/projects/{project_id}/candidate-preparation", response_model=CandidatePreview)
def prepare_candidates(
    project_id: UUID, body: PrepareDocumentCandidates, request: Request, context: Context
):
    return candidate_invoke(request, context, "prepare", project_id, body)


@router.get("/projects/{project_id}/candidate-preview", response_model=CandidatePreview)
def candidate_preview(
    project_id: UUID,
    request: Request,
    context: Context,
    candidate_preparation_id: UUID | None = None,
):
    return candidate_invoke(request, context, "preview", project_id, candidate_preparation_id)


@router.post("/projects/{project_id}/candidate-decisions", response_model=CandidateDecisionReceipt)
def decide_candidates(
    project_id: UUID, body: ResolveDocumentCandidates, request: Request, context: Context
):
    return candidate_invoke(request, context, "resolve", project_id, body)
