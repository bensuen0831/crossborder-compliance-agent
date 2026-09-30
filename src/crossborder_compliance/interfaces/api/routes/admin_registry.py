from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from crossborder_compliance.application.metadata_services import AdminAuthorizationError
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.context import repository_context_from_request

router = APIRouter(prefix="/api/v1/admin", tags=["admin-metadata"])

RESOURCE_KIND = {
    "jurisdictions": "JURISDICTION",
    "scenarios": "SCENARIO",
    "products": "PRODUCT",
    "classification-schemes": "CLASSIFICATION_SCHEME",
    "models": "MODEL",
    "prompts": "PROMPT",
    "rules": "RULE",
    "templates": "TEMPLATE",
    "knowledge-collections": "KNOWLEDGE_COLLECTION",
}
RESOURCE_KEYS = tuple(RESOURCE_KIND)

_SECRET_KEYS = {
    "api_key", "access_token", "refresh_token", "client_secret", "password",
    "credential", "credential_value", "secret", "token",
}


class DraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=250)
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_definition_id: UUID | None = None


class DraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_record_version: int = Field(ge=1)


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_record_version: int = Field(ge=1)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _SECRET_KEYS or (lowered.endswith("_token") and lowered != "token_ref"):
                continue
            result[str(key)] = _sanitize(item)
        return result
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _service(request: Request, resource: str, context: RepositoryContext):
    provider = getattr(request.app.state, "admin_service_provider", None)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin service provider is not configured",
        )
    service = provider(context, resource)
    if service is None:
        raise HTTPException(status_code=404, detail="admin resource is not configured")
    return service


def _call(fn, *args, **kwargs):
    try:
        return _sanitize(fn(*args, **kwargs))
    except AdminAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _install_resource(resource: str) -> None:
    base = f"/{resource}"

    @router.post(base, name=f"admin_{resource}_create_draft")
    def create_draft(
        body: DraftCreateRequest,
        request: Request,
        context: RepositoryContext = Depends(repository_context_from_request),
    ):
        service = _service(request, resource, context)
        return _call(
            service.create_draft,
            kind=RESOURCE_KIND[resource],
            code=body.code,
            display_name=body.display_name,
            payload=body.payload,
            parent_definition_id=body.parent_definition_id,
        )

    @router.put(base + "/versions/{version_id}", name=f"admin_{resource}_update_draft")
    def update_draft(
        version_id: UUID,
        body: DraftUpdateRequest,
        request: Request,
        context: RepositoryContext = Depends(repository_context_from_request),
    ):
        service = _service(request, resource, context)
        return _call(
            service.update_draft,
            version_id,
            payload=body.payload,
            expected_record_version=body.expected_record_version,
        )

    def transition(action: str):
        def endpoint(
            version_id: UUID,
            body: TransitionRequest,
            request: Request,
            context: RepositoryContext = Depends(repository_context_from_request),
        ):
            service = _service(request, resource, context)
            method = getattr(service, action)
            return _call(
                method,
                version_id,
                expected_record_version=body.expected_record_version,
            )
        endpoint.__name__ = f"{resource.replace('-', '_')}_{action}"
        return endpoint

    for action in ("submit_review", "approve", "reject", "publish", "supersede", "archive"):
        router.add_api_route(
            base + f"/versions/{{version_id}}/{action.replace('_', '-')}",
            transition(action),
            methods=["POST"],
            name=f"admin_{resource}_{action}",
        )

    @router.get(base + "/{definition_id}/versions", name=f"admin_{resource}_history")
    def history(
        definition_id: UUID,
        request: Request,
        context: RepositoryContext = Depends(repository_context_from_request),
    ):
        service = _service(request, resource, context)
        return _call(service.history, definition_id)

    @router.get(base + "/{definition_id}/impact-preview", name=f"admin_{resource}_impact")
    def impact_preview(
        definition_id: UUID,
        request: Request,
        context: RepositoryContext = Depends(repository_context_from_request),
    ):
        service = _service(request, resource, context)
        return _call(service.impact_preview, definition_id)


for _resource in RESOURCE_KEYS:
    _install_resource(_resource)
