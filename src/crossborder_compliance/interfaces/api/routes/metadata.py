from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.domain.localized_metadata import PresentationLocale
from crossborder_compliance.interfaces.api.metadata_presenter import present_metadata
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.registry_catalog import TenantRegistryProvider
from crossborder_compliance.interfaces.api.dependencies import get_repository_context


router = APIRouter(prefix="/api/v1/metadata", tags=["metadata"])


@lru_cache
def _provider() -> TenantRegistryProvider:
    settings = get_settings()
    _, sf = build_session_factory(settings.database_url)
    return TenantRegistryProvider(sf)


def _response(resource: str, context: RepositoryContext, locale: PresentationLocale | None = None):
    _provider().invalidate(context, resource)
    registry = _provider()(context, resource)
    if registry is None:
        return {"registry_version": "EMPTY", "health": {"status": "UNAVAILABLE"}, "items": []}
    return {
        "registry_version": registry.version(),
        "health": registry.health(),
        "items": [present_metadata(row, locale) for row in registry.list()] if locale else registry.list(),
    }


@router.get("/bootstrap")
def bootstrap_metadata():
    return {
        "metadata_version": "phase1c-registry",
        "jurisdictions": [],
        "scenarios": [],
        "product_domains": [],
        "products": [],
        "data_types": [],
        "data_flow_types": [],
    }


@router.get("/jurisdictions")
def jurisdictions(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
    return _response("jurisdictions", context, locale)


@router.get("/scenarios")
def scenarios(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
    return _response("scenarios", context, locale)


@router.get("/products")
def products(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
    return _response("products", context, locale)


@router.get("/data-types")
def data_types(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
    return _response("data-types", context, locale)


@router.get("/data-flow-types")
def data_flow_types(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
    return _response("data-flow-types", context, locale)


@router.get("/classification-schemes")
def classification_schemes(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
    return _response("classification-schemes", context, locale)


@router.get("/model-capabilities")
def model_capabilities(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
    return _response("model-capabilities", context, locale)


def _generic_runtime_endpoint(resource):
    def endpoint(context: RepositoryContext = Depends(get_repository_context), locale: PresentationLocale | None = None):
        # Existing provider stays a projection; refresh derives newly committed metadata.
        _provider().invalidate(context, resource)
        return _response(resource, context, locale)
    endpoint.__name__ = "runtime_" + resource.replace("-", "_")
    return endpoint


for _resource in ("skills", "country-profiles", "scenario-adjustments", "country-capabilities", "applicability-configs", "rule-packs", "obligation-policies", "compliance-path-policies", "risk-policies", "recommendation-policies"):
    router.add_api_route("/" + _resource, _generic_runtime_endpoint(_resource), methods=["GET"])
