from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.context import repository_context_from_request

router = APIRouter(prefix="/api/v1/metadata", tags=["metadata-runtime"])

RESOURCE_KEYS = (
    "jurisdictions",
    "scenarios",
    "products",
    "data-types",
    "data-flow-types",
    "classification-schemes",
    "model-capabilities",
)

_SECRET_KEYS = {
    "api_key", "access_token", "refresh_token", "client_secret", "password",
    "credential", "credential_value", "secret", "token", "secret_ref",
}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize(item)
            for key, item in value.items()
            if str(key).lower() not in _SECRET_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _registry(request: Request, context: RepositoryContext, resource: str):
    provider = getattr(request.app.state, "registry_provider", None)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="registry provider is not configured",
        )
    registry = provider(context, resource)
    if registry is None:
        raise HTTPException(status_code=404, detail="metadata registry is not configured")
    return registry


def _install_resource(resource: str) -> None:
    @router.get(f"/{resource}", name=f"metadata_{resource}")
    def list_metadata(
        request: Request,
        context: RepositoryContext = Depends(repository_context_from_request),
    ):
        registry = _registry(request, context, resource)
        return {
            "resource": resource,
            "tenant_id": str(context.tenant_id),
            "registry_version": registry.version(),
            "items": _sanitize(registry.list()),
        }


for _resource in RESOURCE_KEYS:
    _install_resource(_resource)
