from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from crossborder_compliance.application.metadata_services import (
    AdminAuthorizationError,
    MetadataLifecycleError,
    MetadataLifecycleService,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.metadata import GovernanceStatus
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataOptimisticConcurrencyError,
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresClassificationAdminRepository,
    PostgresJurisdictionAdminRepository,
    PostgresModelAdminRepository,
)
from crossborder_compliance.interfaces.api.admin_schemas import (
    AdminDraftRequest,
    AdminDraftUpdateRequest,
    AdminTransitionRequest,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context


router = APIRouter(prefix="/api/v1/admin", tags=["admin-metadata"])

_GENERIC_KINDS = {
    "scenarios": "SCENARIO",
    "products": "PRODUCT",
}
_GOVERNED_ARTIFACTS = {
    "prompts",
    "rules",
    "templates",
    "knowledge-collections",
}
_ALL_RESOURCES = (
    "jurisdictions",
    "scenarios",
    "products",
    "classification-schemes",
    "models",
    "prompts",
    "rules",
    "templates",
    "knowledge-collections",
)


class _AdminFacade:
    def __init__(self, resource: str, context: RepositoryContext):
        settings = get_settings()
        _, sf = build_session_factory(settings.database_url)
        self.resource = resource
        self.context = context
        self.generic_repo = None
        self.generic_service = None
        if resource in _GENERIC_KINDS:
            self.generic_repo = PostgresAdminMetadataRepository(sf, context)
            self.generic_service = MetadataLifecycleService(self.generic_repo, context)
            self.repo = self.generic_repo
        elif resource == "jurisdictions":
            self.repo = PostgresJurisdictionAdminRepository(sf, context)
        elif resource == "classification-schemes":
            self.repo = PostgresClassificationAdminRepository(sf, context)
        elif resource == "models":
            self.repo = PostgresModelAdminRepository(sf, context)
        elif resource in _GOVERNED_ARTIFACTS:
            self.repo = PostgresGovernedArtifactAdminRepository(sf, context, resource)
        else:
            raise ValueError(f"unsupported admin resource: {resource}")

    def create(self, request: AdminDraftRequest) -> dict[str, object]:
        if self.generic_service:
            parent = UUID(request.parent_definition_id) if request.parent_definition_id else None
            return self.generic_service.create_draft(
                kind=_GENERIC_KINDS[self.resource],
                code=request.code,
                display_name=request.display_name,
                payload=request.payload,
                parent_definition_id=parent,
            )
        return self.repo.create_draft(
            code=request.code,
            display_name=request.display_name,
            payload=request.payload,
        )

    def update(self, version_id: UUID, request: AdminDraftUpdateRequest) -> dict[str, object]:
        if self.generic_service:
            return self.generic_service.update_draft(
                version_id,
                payload=request.payload,
                expected_record_version=request.expected_record_version,
            )
        return self.repo.update_draft(
            version_id,
            payload=request.payload,
            expected_record_version=request.expected_record_version,
        )

    def transition(
        self,
        version_id: UUID,
        action: str,
        request: AdminTransitionRequest,
    ) -> dict[str, object]:
        if self.generic_service:
            method = {
                "submit-review": self.generic_service.submit_review,
                "approve": self.generic_service.approve,
                "reject": self.generic_service.reject,
                "publish": self.generic_service.publish,
                "supersede": self.generic_service.supersede,
                "archive": self.generic_service.archive,
            }[action]
            return method(version_id, expected_record_version=request.expected_record_version)

        target = {
            "submit-review": GovernanceStatus.PENDING_REVIEW.value,
            "approve": GovernanceStatus.APPROVED.value,
            "reject": GovernanceStatus.DRAFT.value,
            "publish": GovernanceStatus.ACTIVE.value,
            "supersede": GovernanceStatus.SUPERSEDED.value,
            "archive": GovernanceStatus.ARCHIVED.value,
        }[action]
        return self.repo.transition(
            version_id,
            target_status=target,
            expected_record_version=request.expected_record_version,
        )

    def history(self, definition_id: UUID) -> list[dict[str, object]]:
        return self.repo.history(definition_id)

    def impact(self, definition_id: UUID) -> dict[str, object]:
        return self.repo.impact_preview(definition_id)


def _translate_error(exc: Exception) -> None:
    if isinstance(exc, AdminAuthorizationError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, (MetadataLifecycleError, MetadataOptimisticConcurrencyError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


def _make_create(resource: str):
    def endpoint(
        request: AdminDraftRequest,
        context: RepositoryContext = Depends(get_repository_context),
    ):
        try:
            return _AdminFacade(resource, context).create(request)
        except Exception as exc:
            _translate_error(exc)
    endpoint.__name__ = f"create_{resource.replace('-', '_')}_draft"
    return endpoint


def _make_update(resource: str):
    def endpoint(
        version_id: UUID,
        request: AdminDraftUpdateRequest,
        context: RepositoryContext = Depends(get_repository_context),
    ):
        try:
            return _AdminFacade(resource, context).update(version_id, request)
        except Exception as exc:
            _translate_error(exc)
    endpoint.__name__ = f"update_{resource.replace('-', '_')}_draft"
    return endpoint


def _make_transition(resource: str, action: str):
    def endpoint(
        version_id: UUID,
        request: AdminTransitionRequest,
        context: RepositoryContext = Depends(get_repository_context),
    ):
        try:
            return _AdminFacade(resource, context).transition(version_id, action, request)
        except Exception as exc:
            _translate_error(exc)
    endpoint.__name__ = f"{action.replace('-', '_')}_{resource.replace('-', '_')}"
    return endpoint


def _make_history(resource: str):
    def endpoint(
        definition_id: UUID,
        context: RepositoryContext = Depends(get_repository_context),
    ):
        try:
            return {"items": _AdminFacade(resource, context).history(definition_id)}
        except Exception as exc:
            _translate_error(exc)
    endpoint.__name__ = f"{resource.replace('-', '_')}_version_history"
    return endpoint


def _make_impact(resource: str):
    def endpoint(
        definition_id: UUID,
        context: RepositoryContext = Depends(get_repository_context),
    ):
        try:
            return _AdminFacade(resource, context).impact(definition_id)
        except Exception as exc:
            _translate_error(exc)
    endpoint.__name__ = f"{resource.replace('-', '_')}_impact_preview"
    return endpoint


for _resource in _ALL_RESOURCES:
    router.add_api_route(
        f"/{_resource}",
        _make_create(_resource),
        methods=["POST"],
        summary=f"Create {_resource} draft",
    )
    router.add_api_route(
        f"/{_resource}/{{version_id}}/draft",
        _make_update(_resource),
        methods=["PATCH"],
        summary=f"Update {_resource} draft",
    )
    for _action in ("submit-review", "approve", "reject", "publish", "supersede", "archive"):
        router.add_api_route(
            f"/{_resource}/{{version_id}}/{_action}",
            _make_transition(_resource, _action),
            methods=["POST"],
            summary=f"{_action} {_resource}",
        )
    router.add_api_route(
        f"/{_resource}/{{definition_id}}/versions",
        _make_history(_resource),
        methods=["GET"],
        summary=f"{_resource} version history",
    )
    router.add_api_route(
        f"/{_resource}/{{definition_id}}/impact-preview",
        _make_impact(_resource),
        methods=["GET"],
        summary=f"{_resource} impact preview",
    )
