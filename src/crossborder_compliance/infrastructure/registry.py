from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any
from uuid import UUID

from crossborder_compliance.application.registry_ports import RegistryPort
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresConfigRegistrySourceRepository,
    PostgresModelRegistryRepository,
    PostgresRegistrySourceRepository,
)


class ProjectionRegistry(RegistryPort[dict[str, object]]):
    """In-memory projection only. DB/versioned config remains source of truth."""

    def __init__(
        self,
        loader: Callable[[], list[dict[str, object]]],
        *,
        id_field: str = "definition_id",
    ):
        self._loader = loader
        self._id_field = id_field
        self._rows: dict[str, dict[str, object]] = {}
        self._version = "EMPTY"
        self._refresh_count = 0

    def refresh(self) -> None:
        rows = self._loader()
        self._rows = {str(row[self._id_field]): deepcopy(row) for row in rows}
        canonical = json.dumps(
            sorted(
                [
                    {
                        "id": str(row.get(self._id_field)),
                        "version_id": str(row.get("version_id", row.get("model_deployment_id", ""))),
                        "version_no": row.get("version_no", 0),
                    }
                    for row in rows
                ],
                key=lambda item: item["id"],
            ),
            sort_keys=True,
        )
        self._version = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        self._refresh_count += 1

    def get(self, object_id: UUID) -> dict[str, object] | None:
        row = self._rows.get(str(object_id))
        return deepcopy(row) if row else None

    def list(self) -> list[dict[str, object]]:
        return [deepcopy(row) for row in self._rows.values()]

    def resolve(self, **criteria: object) -> dict[str, object] | None:
        for row in self._rows.values():
            if all(
                row.get(key) == value
                or (
                    isinstance(row.get("payload"), dict)
                    and row["payload"].get(key) == value
                )
                for key, value in criteria.items()
            ):
                return deepcopy(row)
        return None

    def version(self) -> str:
        return self._version

    def health(self) -> dict[str, object]:
        return {
            "status": "OK",
            "entry_count": len(self._rows),
            "projection_version": self._version,
            "refresh_count": self._refresh_count,
            "source_of_truth": False,
        }


class GenericMetadataRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresRegistrySourceRepository, kind: str):
        self.kind = kind
        super().__init__(lambda: source.load_active(kind))


class JurisdictionRegistry(GenericMetadataRegistry):
    def __init__(self, source: PostgresRegistrySourceRepository):
        super().__init__(source, "JURISDICTION")


class ScenarioRegistry(GenericMetadataRegistry):
    def __init__(self, source):
        super().__init__(source, "SCENARIO")


class ProductRegistry(GenericMetadataRegistry):
    def __init__(self, source):
        super().__init__(source, "PRODUCT")


class AgentRegistry(GenericMetadataRegistry):
    def __init__(self, source):
        super().__init__(source, "AGENT")


class VerticalAgentRegistry(GenericMetadataRegistry):
    def __init__(self, source):
        super().__init__(source, "VERTICAL_AGENT")


class SkillRegistry(GenericMetadataRegistry):
    def __init__(self, source):
        super().__init__(source, "SKILL")


class ClassificationRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresConfigRegistrySourceRepository):
        super().__init__(source.load_classification_schemes)

    def resolve(self, **criteria: object) -> dict[str, object] | None:
        jurisdiction_id = str(criteria.get("jurisdiction_id")) if criteria.get("jurisdiction_id") else None
        industry_ref = criteria.get("industry_ref")
        scenario_definition_id = (
            str(criteria.get("scenario_definition_id"))
            if criteria.get("scenario_definition_id")
            else None
        )
        candidates: list[tuple[int, dict[str, object]]] = []
        for row in self._rows.values():
            for binding in row.get("bindings", []):
                if jurisdiction_id and binding.get("jurisdiction_id") not in {None, jurisdiction_id}:
                    continue
                if industry_ref and binding.get("industry_ref") not in {None, industry_ref}:
                    continue
                if (
                    scenario_definition_id
                    and binding.get("scenario_definition_id") not in {None, scenario_definition_id}
                ):
                    continue
                candidates.append((int(binding.get("priority", 100)), row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return deepcopy(candidates[0][1])


class ModelRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresModelRegistryRepository):
        super().__init__(source.load_runtime_models, id_field="model_definition_id")

    def resolve(self, **criteria: object) -> dict[str, object] | None:
        capability = criteria.get("capability")
        routing_model_id = criteria.get("model_definition_id")
        if routing_model_id:
            return self.get(UUID(str(routing_model_id)))
        for row in self._rows.values():
            if capability and capability not in row.get("capabilities", []):
                continue
            return deepcopy(row)
        return None


class ModelCapabilityRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresModelRegistryRepository):
        self._model_source = source
        super().__init__(self._load, id_field="definition_id")

    def _load(self) -> list[dict[str, object]]:
        capabilities: set[str] = set()
        for model in self._model_source.load_runtime_models():
            capabilities.update(str(value) for value in model.get("capabilities", []))
        return [
            {
                "definition_id": UUID(int=index + 1),
                "code": capability,
                "display_name": capability.replace("_", " ").title(),
            }
            for index, capability in enumerate(sorted(capabilities))
        ]


class PromptRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresConfigRegistrySourceRepository):
        super().__init__(source.load_prompts)


class RuleRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresConfigRegistrySourceRepository):
        super().__init__(source.load_rules)


class TemplateRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresConfigRegistrySourceRepository):
        super().__init__(source.load_templates)

    def resolve(self, **criteria: object) -> dict[str, object] | None:
        candidates = [
            row
            for row in self._rows.values()
            if all(row.get(key) == value for key, value in criteria.items())
        ]
        if not candidates:
            return None
        # Regulatory templates have governance precedence over enterprise templates.
        candidates.sort(
            key=lambda row: 0 if row.get("template_type") == "REGULATORY_TEMPLATE" else 1
        )
        return deepcopy(candidates[0])


class KnowledgeRegistry(ProjectionRegistry):
    def __init__(self, source: PostgresConfigRegistrySourceRepository):
        super().__init__(source.load_knowledge)
