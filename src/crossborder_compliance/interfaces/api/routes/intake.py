"""Typed production intake transport; browser facts never carry authority."""

from typing import Annotated
from functools import partial
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import DBAPIError, IntegrityError

from crossborder_compliance.application.intake_services import (
    ConfirmProjectIntake,
    CreateProjectFromIntake,
    IntakeView,
    UpdateIntakeDraft,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.intake_composition import intake_service, prepare_snapshot
from crossborder_compliance.infrastructure.persistence.project_intake import IntakeConflict
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1", tags=["project-intake"])
Context = Annotated[RepositoryContext, Depends(get_repository_context)]


def invoke(request, context, operation, *args):
    try:
        secret_factory = getattr(request.app.state, "llm_secret_store_factory", None)
        preparer = getattr(request.app.state, "intake_snapshot_preparer", None) or partial(
            prepare_snapshot, llm_dependencies={
                "storage": getattr(request.app.state, "document_object_storage", None),
                "secrets": secret_factory(context) if secret_factory else None,
                "redaction": getattr(request.app.state, "llm_data_redaction_service", None),
            })
        return getattr(intake_service(sessions(request), context, preparer), operation)(*args)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(404, "intake resource not found") from exc
    except (IntakeConflict, IntegrityError) as exc:
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
