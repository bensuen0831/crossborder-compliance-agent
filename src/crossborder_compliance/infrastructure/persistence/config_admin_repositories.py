from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import sessionmaker

from crossborder_compliance.application.metadata_services import (
    AdminActionPolicy,
    MetadataLifecycleError,
    lifecycle_transition_allowed,
)
from crossborder_compliance.domain.metadata import GovernanceStatus
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    AdminPublishRecordEntity,
    KnowledgeCollectionEntity,
    KnowledgeCollectionVersionEntity,
    PromptDefinitionEntity,
    PromptBindingEntity,
    PromptVersionEntity,
    RegistrySyncEventEntity,
    RuleDefinitionEntity,
    RuleVersionEntity,
    TemplateDefinitionEntity,
    TemplateVersionEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataOptimisticConcurrencyError,
)
from crossborder_compliance.infrastructure.persistence.rule_governance import (
    contract_values, replace_tests, transition_gate,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostgresGovernedArtifactAdminRepository:
    """Typed Prompt/Rule/Template/Knowledge governance source-of-truth."""

    RESOURCE_SPECS = {
        "prompts": {
            "kind": "PROMPT",
            "definition": PromptDefinitionEntity,
            "version": PromptVersionEntity,
            "definition_pk": "prompt_definition_id",
            "version_pk": "prompt_version_id",
            "definition_fk": "prompt_definition_id",
        },
        "rules": {
            "kind": "RULE",
            "definition": RuleDefinitionEntity,
            "version": RuleVersionEntity,
            "definition_pk": "rule_definition_id",
            "version_pk": "rule_version_id",
            "definition_fk": "rule_definition_id",
        },
        "templates": {
            "kind": "TEMPLATE",
            "definition": TemplateDefinitionEntity,
            "version": TemplateVersionEntity,
            "definition_pk": "template_definition_id",
            "version_pk": "template_version_id",
            "definition_fk": "template_definition_id",
        },
        "knowledge-collections": {
            "kind": "KNOWLEDGE",
            "definition": KnowledgeCollectionEntity,
            "version": KnowledgeCollectionVersionEntity,
            "definition_pk": "knowledge_collection_id",
            "version_pk": "knowledge_collection_version_id",
            "definition_fk": "knowledge_collection_id",
        },
    }

    def __init__(self, session_factory: sessionmaker, context: RepositoryContext, resource: str):
        if resource not in self.RESOURCE_SPECS:
            raise ValueError(f"unsupported governed resource: {resource}")
        self._sessions = session_factory
        self._context = context
        self._spec = self.RESOURCE_SPECS[resource]
        self._policy = AdminActionPolicy()

    @property
    def tenant_id(self) -> str:
        return str(self._context.tenant_id)

    def _require(self, scope: str) -> None:
        self._policy.require(self._context, scope)

    def bind_llm_invocation(self, version_id, purpose):
        """Reuse canonical PromptBinding; new snapshots resolve published purpose bindings."""
        self._require("metadata:publish")
        if self._spec["kind"] != "PROMPT":
            raise ValueError("PROMPT_BINDING_RESOURCE_INVALID")
        with self._sessions() as session, session.begin():
            version = session.scalar(select(PromptVersionEntity).where(
                PromptVersionEntity.tenant_id == self.tenant_id,
                PromptVersionEntity.prompt_version_id == str(version_id),
                PromptVersionEntity.lifecycle_status == "ACTIVE",
                PromptVersionEntity.status == "ACTIVE",
            ))
            if version is None:
                raise LookupError("published prompt not found")
            binding = session.scalar(select(PromptBindingEntity).where(
                PromptBindingEntity.tenant_id == self.tenant_id,
                PromptBindingEntity.prompt_version_id == str(version_id),
                PromptBindingEntity.binding_type == "LLM_INVOCATION_PURPOSE",
                PromptBindingEntity.binding_ref == purpose.value,
            ))
            if binding is None:
                binding = PromptBindingEntity(prompt_binding_id=str(uuid4()), tenant_id=self.tenant_id,
                    prompt_version_id=str(version_id), binding_type="LLM_INVOCATION_PURPOSE",
                    binding_ref=purpose.value)
                session.add(binding)
                session.flush()
            return {"binding_id": binding.prompt_binding_id, "prompt_version_id": str(version_id), "purpose": purpose.value}

    def create_draft(self, *, code: str, display_name: str, payload: dict[str, object]) -> dict[str, object]:
        self._require(self._policy.draft_scope)
        definition_model = self._spec["definition"]
        version_model = self._spec["version"]
        definition_pk = self._spec["definition_pk"]
        version_pk = self._spec["version_pk"]
        definition_fk = self._spec["definition_fk"]
        definition_id = str(uuid4())
        version_id = str(uuid4())

        definition_kwargs = {
            definition_pk: definition_id,
            "tenant_id": self.tenant_id,
            "code": code,
            "display_name": display_name,
            "active_version_id": None,
            "status": "ACTIVE",
        }
        if definition_model is TemplateDefinitionEntity:
            definition_kwargs["template_type"] = str(
                payload.get("template_type", "ENTERPRISE_TEMPLATE")
            )

        version_kwargs = {
            version_pk: version_id,
            "tenant_id": self.tenant_id,
            definition_fk: definition_id,
            "version_no": 1,
            "lifecycle_status": GovernanceStatus.DRAFT.value,
            "status": "ACTIVE",
        }
        self._apply_payload(version_model, version_kwargs, payload)

        with self._sessions() as session, session.begin():
            session.add(definition_model(**definition_kwargs))
            session.flush()
            version = version_model(**version_kwargs)
            session.add(version)
            session.flush()
            if version_model is RuleVersionEntity:
                replace_tests(session, version, payload)
        return {
            "definition_id": definition_id,
            "version_id": version_id,
            "version_no": 1,
            "lifecycle_status": GovernanceStatus.DRAFT.value,
            "record_version": 1,
        }

    def update_draft(
        self,
        version_id: UUID,
        *,
        payload: dict[str, object],
        expected_record_version: int,
    ) -> dict[str, object]:
        self._require(self._policy.draft_scope)
        model = self._spec["version"]
        pk = getattr(model, self._spec["version_pk"])
        values: dict[str, object] = {
            "record_version": model.record_version + 1,
            "updated_at": utcnow(),
        }
        self._apply_payload(model, values, payload)
        with self._sessions() as session, session.begin():
            if model is RuleVersionEntity:
                existing = session.scalar(select(model).where(pk == str(version_id), model.tenant_id == self.tenant_id).with_for_update())
                if existing is not None and existing.runtime_contract_json is not None and "runtime_contract" not in payload:
                    raise ValueError("V1 draft updates require the complete runtime_contract and tests")
            result = session.execute(
                update(model)
                .where(
                    pk == str(version_id),
                    model.tenant_id == self.tenant_id,
                    model.lifecycle_status == GovernanceStatus.DRAFT.value,
                    model.record_version == expected_record_version,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise MetadataOptimisticConcurrencyError("draft update failed or version changed")
            if model is RuleVersionEntity:
                row = session.scalar(select(model).where(pk == str(version_id), model.tenant_id == self.tenant_id))
                replace_tests(session, row, payload)
        return self.get_version(version_id)

    def transition(
        self,
        version_id: UUID,
        *,
        target_status: str,
        expected_record_version: int,
    ) -> dict[str, object]:
        required = (
            self._policy.review_scope
            if target_status in {GovernanceStatus.APPROVED.value, GovernanceStatus.DRAFT.value}
            else self._policy.publish_scope
            if target_status in {
                GovernanceStatus.ACTIVE.value,
                GovernanceStatus.SUPERSEDED.value,
                GovernanceStatus.ARCHIVED.value,
                GovernanceStatus.EXPIRED.value,
            }
            else self._policy.draft_scope
        )
        self._require(required)
        model = self._spec["version"]
        definition_model = self._spec["definition"]
        pk_name = self._spec["version_pk"]
        def_pk_name = self._spec["definition_pk"]
        fk_name = self._spec["definition_fk"]
        with self._sessions() as session, session.begin():
            row = session.scalar(
                select(model).where(
                    getattr(model, pk_name) == str(version_id),
                    model.tenant_id == self.tenant_id,
                )
                .with_for_update()
            )
            if row is None:
                raise LookupError("config version not found in tenant scope")
            if row.record_version != expected_record_version:
                raise MetadataOptimisticConcurrencyError("config version changed")
            if not lifecycle_transition_allowed(row.lifecycle_status, target_status):
                raise MetadataLifecycleError(
                    f"invalid lifecycle transition: {row.lifecycle_status} -> {target_status}"
                )
            if model is RuleVersionEntity:
                transition_gate(session, row, target_status, self._context.permission.actor_id)
            row.lifecycle_status = target_status
            row.record_version += 1
            row.updated_at = utcnow()
            definition_id = getattr(row, fk_name)

            if target_status == GovernanceStatus.ACTIVE.value:
                definition = session.scalar(
                    select(definition_model).where(
                        getattr(definition_model, def_pk_name) == definition_id,
                        definition_model.tenant_id == self.tenant_id,
                    )
                )
                if definition is None:
                    raise LookupError("config definition missing")
                old_id = definition.active_version_id
                if old_id and old_id != str(version_id):
                    old = session.scalar(
                        select(model).where(
                            getattr(model, pk_name) == old_id,
                            model.tenant_id == self.tenant_id,
                        )
                    )
                    if old and old.lifecycle_status == GovernanceStatus.ACTIVE.value:
                        old.lifecycle_status = GovernanceStatus.SUPERSEDED.value
                        old.record_version += 1
                        old.updated_at = utcnow()
                definition.active_version_id = str(version_id)
                definition.record_version += 1
                definition.updated_at = utcnow()
                session.add(
                    AdminPublishRecordEntity(
                        publish_record_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind=self._spec["kind"],
                        version_id=str(version_id),
                        published_by=self._context.permission.actor_id,
                        published_at=utcnow(),
                        status="ACTIVE",
                    )
                )
                session.add(
                    RegistrySyncEventEntity(
                        registry_sync_event_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind=self._spec["kind"],
                        object_id=definition_id,
                        version_id=str(version_id),
                        event_version=row.version_no,
                        attempts=0,
                        status="PENDING",
                    )
                )
            session.flush()
            return self._row_dict(row)

    def get_version(self, version_id: UUID) -> dict[str, object]:
        model = self._spec["version"]
        with self._sessions() as session:
            row = session.scalar(
                select(model).where(
                    getattr(model, self._spec["version_pk"]) == str(version_id),
                    model.tenant_id == self.tenant_id,
                )
            )
            if row is None:
                raise LookupError("config version not found in tenant scope")
            return self._row_dict(row)

    def history(self, definition_id: UUID) -> list[dict[str, object]]:
        model = self._spec["version"]
        fk = getattr(model, self._spec["definition_fk"])
        with self._sessions() as session:
            rows = session.scalars(
                select(model)
                .where(model.tenant_id == self.tenant_id, fk == str(definition_id))
                .order_by(model.version_no.desc())
            ).all()
            return [self._row_dict(row) for row in rows]

    def impact_preview(self, definition_id: UUID) -> dict[str, object]:
        return {
            "definition_id": str(definition_id),
            "object_kind": self._spec["kind"],
            "requires_runtime_restart": False,
            "registry_refresh_required": True,
        }

    @staticmethod
    def _apply_payload(model, target: dict[str, object], payload: dict[str, object]) -> None:
        if model is PromptVersionEntity:
            target["template_text"] = str(payload.get("template_text", ""))
            target["capability_requirement_json"] = list(
                payload.get("capability_requirement", [])
            )
        elif model is RuleVersionEntity:
            target["safe_dsl_json"] = dict(payload.get("safe_dsl", {}))
            target["scope_json"] = dict(payload.get("scope", {}))
            target["priority"] = int(payload.get("priority", 100))
            target.update(contract_values(payload))
        elif model is TemplateVersionEntity:
            target["field_schema_json"] = dict(payload.get("field_schema", {}))
            target["content_ref"] = payload.get("content_ref")
        elif model is KnowledgeCollectionVersionEntity:
            target["payload_json"] = dict(payload)

    def _row_dict(self, row) -> dict[str, object]:
        return {
            "version_id": getattr(row, self._spec["version_pk"]),
            "definition_id": getattr(row, self._spec["definition_fk"]),
            "version_no": row.version_no,
            "lifecycle_status": row.lifecycle_status,
            "record_version": row.record_version,
        }
