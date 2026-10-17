"""Validation shared by both channels over canonical metadata, without another registry."""

from uuid import UUID

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB

from crossborder_compliance.domain.knowledge_management import TAXONOMY_KINDS, TaxonomyPayload
from crossborder_compliance.infrastructure.persistence import metadata_models as m


class KnowledgeManagementConflict(ValueError):
    pass


def is_managed_taxonomy(kind, payload):
    return kind in TAXONOMY_KINDS and (
        kind != "JURISDICTION_CONFIG" or payload.get("management_schema") == "KB01_TAXONOMY_V1"
    )


def validate_taxonomy_payload(session, definition, payload):
    value = TaxonomyPayload.model_validate(
        {key: val for key, val in payload.items() if key in TaxonomyPayload.model_fields}
    )
    limit = 200 if definition.kind == "JURISDICTION_CONFIG" else 250
    if (
        is_managed_taxonomy(definition.kind, payload)
        and definition.kind == "JURISDICTION_CONFIG"
        and value.jurisdiction_type is None
    ):
        raise ValueError("JURISDICTION_TYPE_REQUIRED")
    if any(len(name) > limit for name in value.localized_display.localized_display_names.values()):
        raise ValueError("TAXONOMY_DISPLAY_NAME_TOO_LONG")

    def scoped(identity):
        row = session.scalar(
            select(m.MetadataDefinitionEntity).where(
                m.MetadataDefinitionEntity.tenant_id == definition.tenant_id,
                m.MetadataDefinitionEntity.definition_id == str(identity),
            )
        )
        if row is None:
            raise LookupError("taxonomy reference not found")
        if row.kind != definition.kind:
            raise ValueError("TAXONOMY_REFERENCE_KIND_MISMATCH")
        return row

    parent_id, seen = value.parent_definition_id, {definition.definition_id}
    while parent_id:
        if len(seen) > 64:
            raise ValueError("TAXONOMY_HIERARCHY_TOO_DEEP")
        if str(parent_id) in seen:
            raise KnowledgeManagementConflict("TAXONOMY_PARENT_CYCLE")
        seen.add(str(parent_id))
        parent = scoped(parent_id)
        version = session.scalar(
            select(m.MetadataVersionEntity)
            .where(
                m.MetadataVersionEntity.tenant_id == definition.tenant_id,
                m.MetadataVersionEntity.definition_id == parent.definition_id,
                *(
                    [m.MetadataVersionEntity.version_id == parent.active_version_id]
                    if parent.active_version_id
                    else []
                ),
            )
            .order_by(m.MetadataVersionEntity.version_no.desc())
            .limit(1)
        )
        parent_id = version.payload_json.get("parent_definition_id") if version else None
    if set(value.merge_source_record_versions) != set(value.merge_source_definition_ids):
        raise ValueError("TAXONOMY_MERGE_VERSION_SET_MISMATCH")
    for source_id in value.merge_source_definition_ids:
        source = scoped(source_id)
        if source.definition_id == definition.definition_id:
            raise ValueError("INVALID_TAXONOMY_MERGE_SOURCE")
        if value.merge_source_record_versions[UUID(source.definition_id)] != source.record_version:
            raise KnowledgeManagementConflict("TAXONOMY_MERGE_SOURCE_CHANGED")
        # Follow currently published presentation aliases. No legal identity is
        # redirected, and an alias cycle or competing destination fails closed.
        pending, visited = [definition.definition_id], set()
        while pending:
            current_id = pending.pop()
            if current_id in visited:
                continue
            if len(visited) >= 64:
                raise ValueError("TAXONOMY_ALIAS_CHAIN_TOO_DEEP")
            visited.add(current_id)
            destinations = session.scalars(
                select(m.MetadataDefinitionEntity.definition_id)
                .join(
                    m.MetadataVersionEntity,
                    m.MetadataVersionEntity.version_id
                    == m.MetadataDefinitionEntity.active_version_id,
                )
                .where(
                    m.MetadataDefinitionEntity.tenant_id == definition.tenant_id,
                    m.MetadataDefinitionEntity.kind == definition.kind,
                    m.MetadataVersionEntity.tenant_id == definition.tenant_id,
                    m.MetadataVersionEntity.lifecycle_status == "ACTIVE",
                    cast(m.MetadataVersionEntity.payload_json, JSONB)[
                        "merge_source_definition_ids"
                    ].contains([current_id]),
                )
            ).all()
            if source.definition_id in destinations:
                raise KnowledgeManagementConflict("TAXONOMY_ALIAS_CYCLE")
            pending.extend(destinations)
        competing = session.scalars(
            select(m.MetadataDefinitionEntity.definition_id)
            .join(
                m.MetadataVersionEntity,
                m.MetadataVersionEntity.version_id == m.MetadataDefinitionEntity.active_version_id,
            )
            .where(
                m.MetadataDefinitionEntity.tenant_id == definition.tenant_id,
                m.MetadataDefinitionEntity.kind == definition.kind,
                m.MetadataDefinitionEntity.definition_id != definition.definition_id,
                m.MetadataVersionEntity.tenant_id == definition.tenant_id,
                m.MetadataVersionEntity.lifecycle_status == "ACTIVE",
                cast(m.MetadataVersionEntity.payload_json, JSONB)[
                    "merge_source_definition_ids"
                ].contains([source.definition_id]),
            )
        ).all()
        if competing:
            raise KnowledgeManagementConflict("TAXONOMY_ALIAS_AMBIGUOUS")
    return value
