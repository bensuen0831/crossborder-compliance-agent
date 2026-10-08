from __future__ import annotations

from collections.abc import Callable

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresConfigRegistrySourceRepository,
    PostgresModelRegistryRepository,
    PostgresRegistrySourceRepository,
)
from crossborder_compliance.infrastructure.registry import (
    ClassificationRegistry,
    GenericMetadataRegistry,
    ModelCapabilityRegistry,
)


class TenantRegistryProvider:
    """Tenant-aware in-memory projection catalog.

    Registry objects are cache projections only. PostgreSQL remains authoritative.
    """

    _GENERIC_KIND = {
        "llm-invocation-policies": "LLM_INVOCATION_POLICY",
        "model-usage-policies": "MODEL_USAGE_POLICY",
        "llm-provider-presets": "LLM_PROVIDER_PRESET",
        "scenarios": "SCENARIO",
        "products": "PRODUCT",
        "data-types": "DATA_TYPE",
        "data-categories": "DATA_CATEGORY",
        "data-flow-types": "DATA_FLOW_TYPE",
        "skills": "SKILL",
        "country-profiles": "COUNTRY_PROFILE",
        "scenario-adjustments": "SCENARIO_ADJUSTMENT",
        "country-capabilities": "COUNTRY_CAPABILITY",
        "applicability-configs": "APPLICABILITY_CONFIG",
        "rule-packs": "RULE_PACK",
        "obligation-policies": "OBLIGATION_POLICY",
        "compliance-path-policies": "COMPLIANCE_PATH_POLICY",
        "risk-policies": "RISK_POLICY",
        "recommendation-policies": "RECOMMENDATION_POLICY",
        "cross-border-assessment-policies": "CROSS_BORDER_ASSESSMENT_POLICY",
        "document-requirement-policies": "DOCUMENT_REQUIREMENT_POLICY",
    }

    def __init__(self, session_factory):
        self._sessions = session_factory
        self._cache: dict[tuple[str, str], object] = {}

    def __call__(self, context: RepositoryContext, resource: str):
        key = (str(context.tenant_id), resource)
        registry = self._cache.get(key)
        if registry is not None:
            return registry

        if resource == "jurisdictions":
            source = PostgresConfigRegistrySourceRepository(self._sessions, context)
            from crossborder_compliance.infrastructure.registry import JurisdictionRegistry
            registry = JurisdictionRegistry(source)
        elif resource in self._GENERIC_KIND:
            source = PostgresRegistrySourceRepository(self._sessions, context)
            registry = GenericMetadataRegistry(source, self._GENERIC_KIND[resource])
        elif resource == "classification-schemes":
            source = PostgresConfigRegistrySourceRepository(self._sessions, context)
            registry = ClassificationRegistry(source)
        elif resource == "model-capabilities":
            source = PostgresModelRegistryRepository(self._sessions, context)
            registry = ModelCapabilityRegistry(source)
        else:
            return None

        registry.refresh()
        self._cache[key] = registry
        return registry

    def invalidate(self, context: RepositoryContext, resource: str | None = None) -> None:
        tenant = str(context.tenant_id)
        for key in list(self._cache):
            if key[0] == tenant and (resource is None or key[1] == resource):
                self._cache.pop(key, None)
