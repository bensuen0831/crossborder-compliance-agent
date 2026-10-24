"""F0 channel over the existing metadata review lifecycle, not M2-D workflow review."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request

from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.domain.regulatory_acceptance import ACCEPTANCE_TYPES
from crossborder_compliance.infrastructure.persistence.regulatory_acceptance import (
    PostgresRegulatoryAcceptance,
)
from crossborder_compliance.interfaces.api.regulatory_acceptance_schemas import (
    AcceptanceReadinessView,
    AcceptanceRecordView,
    AcceptanceTransition,
    ImportAcceptanceDraft,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(
    prefix="/api/v1/admin/knowledge-management/acceptance", tags=["regulatory-acceptance-readiness"]
)


def repository(request, context):
    return PostgresRegulatoryAcceptance(sessions(request), context)


@router.get("/templates")
def templates(context: Context):
    invoke(require_management_permission, context, "acceptance:read")
    return {
        "approval_status": "TEMPLATES_NOT_APPROVED_GOLD_STANDARDS",
        "real_regulatory_legal_acceptance": "NOT_EXECUTED",
        "schemas": {kind: model.model_json_schema() for kind, model in ACCEPTANCE_TYPES.items()},
    }


@router.post("/records", status_code=201, response_model=AcceptanceRecordView)
def import_draft(body: ImportAcceptanceDraft, request: Request, context: Context):
    return invoke(repository(request, context).import_draft, body)


@router.get("/records/{identity}", response_model=AcceptanceRecordView)
def read(identity: UUID, request: Request, context: Context):
    return invoke(repository(request, context).read, identity)


@router.post("/records/{identity}/{action}", response_model=AcceptanceRecordView)
def transition(
    identity: UUID,
    action: Literal["submit-review", "approve", "reject", "publish"],
    body: AcceptanceTransition,
    request: Request,
    context: Context,
):
    return invoke(
        repository(request, context).transition, identity, action, body.expected_record_version
    )


@router.get("/cases/{identity}/readiness", response_model=AcceptanceReadinessView)
def readiness(
    identity: UUID, request: Request, context: Context, gold_review_version_id: UUID | None = None
):
    return invoke(repository(request, context).readiness, identity, gold_review_version_id)
