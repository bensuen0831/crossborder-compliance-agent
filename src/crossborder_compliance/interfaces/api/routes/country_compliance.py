"""Reference-only Phase1I APIs; trusted scopes and canonical sources supply all facts."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from crossborder_compliance.application.country_compliance_services import (
    ApplicabilityRequest,
    CountryComplianceSkill,
)
from crossborder_compliance.application.metadata_services import AdminActionPolicy
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.compliance_profiles import CapabilityInput, CapabilityKind
from crossborder_compliance.domain.localized_metadata import PresentationLocale
from crossborder_compliance.domain.rules import Contract
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.metadata_presenter import present_applicability
from crossborder_compliance.interfaces.api.routes.admin_metadata import _translate_error

router = APIRouter(prefix="/api/v1", tags=["country-scenario-applicability"])
Context = Annotated[RepositoryContext, Depends(get_repository_context)]


class ProfilePinRequest(Contract):
    jurisdiction_id: UUID


class ApplicabilityExecutionRequest(Contract):
    analysis_snapshot_id: UUID
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    jurisdiction_id: UUID
    applicability_config_id: UUID
    retrieval_run_id: UUID
    classification_result_ids: tuple[UUID, ...] = ()
    rule_hit_ids: tuple[UUID, ...] = ()


class CapabilityRequest(Contract):
    analysis_snapshot_id: UUID
    jurisdiction_id: UUID
    kind: CapabilityKind
    data_item_id: UUID | None = None
    classification_result_id: UUID | None = None


class MetadataVersionRequest(Contract):
    payload: dict


def repository(context):
    return PostgresCountryComplianceRepository(
        build_session_factory(get_settings().database_url)[1], context
    )


def translate(exc):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail="compliance permission denied") from exc
    _translate_error(exc)


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/compliance-pins")
def initialize(project_id: UUID, snapshot_id: UUID, request: ProfilePinRequest, context: Context):
    try:
        return repository(context).initialize(project_id, snapshot_id, request.jurisdiction_id)
    except Exception as exc:
        translate(exc)


@router.get(
    "/projects/{project_id}/snapshots/{snapshot_id}/country-configurations/{jurisdiction_id}"
)
def configuration(project_id: UUID, snapshot_id: UUID, jurisdiction_id: UUID, context: Context):
    try:
        return CountryComplianceSkill(repository(context)).resolve_profile(
            project_id=project_id, snapshot_id=snapshot_id, jurisdiction_id=jurisdiction_id
        )
    except Exception as exc:
        translate(exc)


@router.post("/projects/{project_id}/regulation-applicability")
def execute(project_id: UUID, request: ApplicabilityExecutionRequest, context: Context):
    try:
        refs = ApplicabilityRequest(project_id=project_id, **request.model_dump())
        return CountryComplianceSkill(repository(context)).resolve_regulation_applicability(refs)
    except Exception as exc:
        translate(exc)


@router.get("/regulation-applicability/{result_id}")
def read(result_id: UUID, context: Context):
    try:
        return repository(context).read(result_id)
    except Exception as exc:
        translate(exc)


@router.post("/projects/{project_id}/country-capabilities")
def capability(project_id: UUID, request: CapabilityRequest, context: Context):
    try:
        repo = repository(context)
        _, pin, _, _, inputs = repo.formal(
            project_id, request.analysis_snapshot_id, request.jurisdiction_id
        )
        classifications = ()
        hits = ()
        evidence = ()
        if request.classification_result_id:
            result = repo.classification(request.classification_result_id)
            if (
                result.project_id,
                result.analysis_snapshot_id,
                result.data_item_id,
                result.jurisdiction_id,
                result.context_version,
            ) != (
                project_id,
                request.analysis_snapshot_id,
                request.data_item_id,
                request.jurisdiction_id,
                pin.context_resolution_version,
            ):
                raise LookupError("classification belongs to another capability scope")
            classifications = (result.classification_result_id,)
            hits = result.rule_hit_ids
            evidence = result.evidence_ids
        if request.data_item_id:
            # Consume the existing formal-context subject validator, never caller facts.
            repo.retrieval.formal_context(
                str(project_id),
                "DATA_ITEM",
                str(request.data_item_id),
                str(request.analysis_snapshot_id),
            )
        typed = CapabilityInput(
            tenant_id=context.tenant_id,
            project_id=project_id,
            analysis_snapshot_id=request.analysis_snapshot_id,
            jurisdiction_id=request.jurisdiction_id,
            kind=request.kind,
            data_item_id=request.data_item_id,
            available_inputs=tuple(sorted(inputs)),
            classification_result_ids=classifications,
            rule_hit_ids=hits,
            evidence_ids=evidence,
        )
        return CountryComplianceSkill(repo).resolve_capability(typed)
    except Exception as exc:
        translate(exc)


@router.post("/admin/compliance-configurations/{definition_id}/versions")
def version(definition_id: UUID, request: MetadataVersionRequest, context: Context):
    try:
        AdminActionPolicy().require(context, "metadata:admin")
        sessions = build_session_factory(get_settings().database_url)[1]
        return PostgresAdminMetadataRepository(sessions, context).create_version(
            definition_id=definition_id, payload=request.payload
        )
    except Exception as exc:
        translate(exc)


class ScenarioRuleHitRequest(Contract):
    jurisdiction_id: UUID
    retrieval_run_id: UUID


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/scenarios/{scenario_id}/rule-hits")
def scenario_hits(
    project_id: UUID,
    snapshot_id: UUID,
    scenario_id: UUID,
    request: ScenarioRuleHitRequest,
    context: Context,
):
    try:
        return repository(context).scenario_rule_hits(
            project_id, snapshot_id, scenario_id, request.jurisdiction_id, request.retrieval_run_id
        )
    except Exception as exc:
        translate(exc)


@router.get("/regulation-applicability/{result_id}/presentation")
def presentation(result_id: UUID, context: Context, locale: PresentationLocale = "en-US"):
    try:
        repo = repository(context)
        result = repo.read(result_id)
        with repo.sessions() as session:
            from crossborder_compliance.infrastructure.persistence.metadata_models import (
                MetadataVersionEntity,
            )

            version = repo.get(
                session, MetadataVersionEntity, result.applicability_config_version_id
            )
            return present_applicability(
                result.model_dump(mode="json"), version.payload_json, locale
            )
    except Exception as exc:
        translate(exc)
