from __future__ import annotations

from fastapi import APIRouter, Depends

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresConfigRegistrySourceRepository,
    PostgresModelRegistryRepository,
    PostgresRegistrySourceRepository,
)
from crossborder_compliance.infrastructure.registry import (
    ClassificationRegistry,
    GenericMetadataRegistry,
    JurisdictionRegistry,
    ModelRegistry,
    ProductRegistry,
    ScenarioRegistry,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context


router = APIRouter(prefix="/api/v1/metadata", tags=["metadata"])


@router.get("/bootstrap")
def bootstrap_metadata():
    # Backward-compatible Phase 1A bootstrap contract. Dynamic options use the typed endpoints below.
    return {
        "metadata_version": "phase1c-registry",
        "jurisdictions": [],
        "scenarios": [],
        "product_domains": [],
        "products": [],
        "data_types": [],
        "data_flow_types": [],
    }


def _sources(context: RepositoryContext):
    settings = get_settings()
    _, sf = build_session_factory(settings.database_url)
    return (
        PostgresRegistrySourceRepository(sf, context),
        PostgresConfigRegistrySourceRepository(sf, context),
        PostgresModelRegistryRepository(sf, context),
    )


def _response(registry):
    registry.refresh()
    return {
        "registry_version": registry.version(),
        "health": registry.health(),
        "items": registry.list(),
    }


@router.get("/jurisdictions")
def jurisdictions(context: RepositoryContext = Depends(get_repository_context)):
    _, config, _ = _sources(context)
    return _response(JurisdictionRegistry(config))


@router.get("/scenarios")
def scenarios(context: RepositoryContext = Depends(get_repository_context)):
    generic, _, _ = _sources(context)
    return _response(ScenarioRegistry(generic))


@router.get("/products")
def products(context: RepositoryContext = Depends(get_repository_context)):
    generic, _, _ = _sources(context)
    return _response(ProductRegistry(generic))


@router.get("/data-types")
def data_types(context: RepositoryContext = Depends(get_repository_context)):
    generic, _, _ = _sources(context)
    return _response(GenericMetadataRegistry(generic, "DATA_TYPE"))


@router.get("/data-flow-types")
def data_flow_types(context: RepositoryContext = Depends(get_repository_context)):
    generic, _, _ = _sources(context)
    return _response(GenericMetadataRegistry(generic, "DATA_FLOW_TYPE"))


@router.get("/classification-schemes")
def classification_schemes(context: RepositoryContext = Depends(get_repository_context)):
    _, config, _ = _sources(context)
    return _response(ClassificationRegistry(config))


@router.get("/model-capabilities")
def model_capabilities(context: RepositoryContext = Depends(get_repository_context)):
    _, _, model_source = _sources(context)
    registry = ModelRegistry(model_source)
    registry.refresh()
    capabilities = sorted(
        {
            capability
            for row in registry.list()
            for capability in row.get("capabilities", [])
        }
    )
    return {
        "registry_version": registry.version(),
        "health": registry.health(),
        "items": capabilities,
    }
