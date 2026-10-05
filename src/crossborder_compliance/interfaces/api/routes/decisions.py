"""Trusted reference-only J endpoints; no workflow or frontend wiring."""

from uuid import UUID

from fastapi import APIRouter

from crossborder_compliance.application.decision_services import (
    DecisionRequest,
    FormalDecisionService,
)
from crossborder_compliance.domain.decision_contracts import StageKind
from crossborder_compliance.domain.localized_metadata import PresentationLocale, resolve_display
from crossborder_compliance.domain.rules import Contract
from crossborder_compliance.interfaces.api.routes.country_compliance import (
    Context,
    repository,
    translate,
)

router = APIRouter(prefix="/api/v1", tags=["formal-decisions"])


class DecisionPinRequest(Contract):
    analysis_snapshot_id: UUID


@router.post("/projects/{project_id}/decision-pins")
def initialize(project_id: UUID, request: DecisionPinRequest, context: Context):
    try:
        return repository(context).initialize_decisions(project_id, request.analysis_snapshot_id)
    except Exception as exc:
        translate(exc)


@router.post("/projects/{project_id}/formal-decisions")
def execute(project_id: UUID, request: DecisionRequest, context: Context):
    try:
        if project_id != request.project_id:
            raise LookupError("decision project mismatch")
        result = FormalDecisionService(repository(context)).execute(request)
        return {"result": result, "summary_status": result.summary_status}
    except Exception as exc:
        translate(exc)


@router.get("/formal-decisions/{stage}/{result_id}")
def read(stage: StageKind, result_id: UUID, context: Context):
    try:
        result = repository(context).read_decision(stage, result_id)
        return {"result": result, "summary_status": result.summary_status}
    except Exception as exc:
        translate(exc)


@router.get("/formal-decisions/{stage}/{result_id}/presentation")
def present(stage: StageKind, result_id: UUID, locale: PresentationLocale, context: Context):
    try:
        from crossborder_compliance.infrastructure.persistence.decision_repository import (
            _loaded,
            prepare,
        )

        repo = repository(context)
        result = repo.read_decision(stage, result_id)
        with repo.sessions() as session:
            row, _ = _loaded(repo, session, stage, result_id)
            request = DecisionRequest.model_validate(row.request_json)
        inputs, _ = prepare(repo, request, "read")
        kind = {
            "OBLIGATION": "OBLIGATION_POLICY",
            "CANDIDATE_PATH": "COMPLIANCE_PATH_POLICY",
            "RISK": "RISK_POLICY",
            "RECOMMENDATION": "RECOMMENDATION_POLICY",
            "FINAL_PATH": "RECOMMENDATION_POLICY",
        }[stage]
        policy = inputs.policy(kind)
        labels = policy.config.localized_code_labels if policy else {}
        display = {
            code: resolve_display(code, None, labels.get(code), locale)
            for code in (*result.reason_codes, result.summary_status)
        }
        return {"result": result, "summary_status": result.summary_status, "presentation": display}
    except Exception as exc:
        translate(exc)
