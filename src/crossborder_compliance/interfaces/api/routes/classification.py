"""Authorized classification: accepts references, never caller-supplied formal facts/results."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from crossborder_compliance.application.classification_services import ClassificationService
from crossborder_compliance.application.metadata_services import AdminActionPolicy
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.classification_repository import (
    PostgresFormalClassificationRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.rule_admin_repository import (
    PostgresRuleAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresClassificationAdminRepository,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.admin_metadata import _translate_error

router = APIRouter(prefix="/api/v1", tags=["rule-classification"])


class ClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_snapshot_id: UUID
    data_item_id: UUID | None = None
    jurisdiction_id: UUID | None = None
    scheme_version_id: UUID


class RuleVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict


class ClassificationPinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme_version_id: UUID


def sessions():
    return build_session_factory(get_settings().database_url)[1]


@router.post("/admin/rules/{definition_id}/versions")
def create_version(
    definition_id: UUID,
    request: RuleVersionRequest,
    context: Annotated[RepositoryContext, Depends(get_repository_context)],
):
    try:
        return PostgresRuleAdminRepository(sessions(), context).create_version(
            definition_id, request.payload
        )
    except Exception as exc:
        _translate_error(exc)


@router.post("/admin/rules/{version_id}/validate")
@router.post("/admin/rules/{version_id}/test")
def validate_rule(
    version_id: UUID, context: Annotated[RepositoryContext, Depends(get_repository_context)]
):
    try:
        return PostgresRuleAdminRepository(sessions(), context).validate(version_id)
    except Exception as exc:
        _translate_error(exc)


@router.post("/admin/classification-schemes/{scheme_id}/versions")
def create_scheme_version(
    scheme_id: UUID,
    request: RuleVersionRequest,
    context: Annotated[RepositoryContext, Depends(get_repository_context)],
):
    try:
        return PostgresClassificationAdminRepository(sessions(), context).create_version(
            scheme_id, payload=request.payload
        )
    except Exception as exc:
        _translate_error(exc)


@router.get("/admin/classification-schemes/{version_id}")
def scheme_detail(
    version_id: UUID, context: Annotated[RepositoryContext, Depends(get_repository_context)]
):
    try:
        AdminActionPolicy().require(context, "metadata:admin")
        return PostgresClassificationAdminRepository(sessions(), context).get_detail(version_id)
    except Exception as exc:
        _translate_error(exc)


@router.get("/admin/rules/{version_id}")
def rule_detail(
    version_id: UUID, context: Annotated[RepositoryContext, Depends(get_repository_context)]
):
    try:
        return PostgresRuleAdminRepository(sessions(), context).get_detail(version_id)
    except Exception as exc:
        _translate_error(exc)


@router.post("/projects/{project_id}/classifications")
def execute(
    project_id: UUID,
    request: ClassificationRequest,
    context: Annotated[RepositoryContext, Depends(get_repository_context)],
):
    try:
        repository = PostgresFormalClassificationRepository(sessions(), context)
        return ClassificationService(repository).execute(
            project_id=project_id,
            snapshot_id=request.analysis_snapshot_id,
            data_item_id=request.data_item_id,
            scheme_version_id=request.scheme_version_id,
            jurisdiction_id=request.jurisdiction_id,
        )
    except Exception as exc:
        _translate_error(exc)


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/classification-pins")
def pin_classification(
    project_id: UUID,
    snapshot_id: UUID,
    request: ClassificationPinRequest,
    context: Annotated[RepositoryContext, Depends(get_repository_context)],
):
    try:
        return PostgresFormalClassificationRepository(sessions(), context).pin_configuration(
            project_id, snapshot_id, request.scheme_version_id
        )
    except Exception as exc:
        _translate_error(exc)


@router.get("/classifications/{result_id}")
def result(result_id: UUID, context: Annotated[RepositoryContext, Depends(get_repository_context)]):
    try:
        return PostgresFormalClassificationRepository(sessions(), context).get_result(result_id)
    except Exception as exc:
        _translate_error(exc)
