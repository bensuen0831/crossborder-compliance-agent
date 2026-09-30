from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.registry_catalog import TenantRegistryProvider
from crossborder_compliance.interfaces.api.dependencies import get_repository_context


router = APIRouter(prefix="/api/v1/metadata", tags=["metadata"])


@lru_cache
def _provider() -> TenantRegistryProvider:
    settings = get_settings()
    _, sf = build_session_factory(settings.database_url)
    return TenantRegistryProvider(sf)


def _response(resource: str, context: RepositoryContext):
    registry = _provider()(context, resource)
    if registry is None:
        return {"registry_version": "EMPTY", "health": {"status": "UNAVAILABLE"}, "items": []}
    return {
        "registry_version": registry.version(),
        "health": registry.health(),
        "items": registry.list(),
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
def jurisdictions(context: RepositoryContext = Depends(get_repository_context)):
    return _response("jurisdictions", context)


@router.get("/scenarios")
def scenarios(context: RepositoryContext = Depends(get_repository_context)):
    return _response("scenarios", context)


@router.get("/products")
def products(context: RepositoryContext = Depends(get_repository_context)):
    return _response("products", context)


@router.get("/data-types")
def data_types(context: RepositoryContext = Depends(get_repository_context)):
    return _response("data-types", context)


@router.get("/data-flow-types")
def data_flow_types(context: RepositoryContext = Depends(get_repository_context)):
    return _response("data-flow-types", context)


@router.get("/classification-schemes")
def classification_schemes(context: RepositoryContext = Depends(get_repository_context)):
    return _response("classification-schemes", context)


@router.get("/model-capabilities")
def model_capabilities(context: RepositoryContext = Depends(get_repository_context)):
    return _response("model-capabilities", context)
