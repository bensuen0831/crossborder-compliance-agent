"""Helpers of the existing ContextResolution repository, not another fact store."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from crossborder_compliance.application.structured_intake import StructuredIntakeBinding
from crossborder_compliance.domain.contracts import ProjectIntakeContext, ProvenanceDTO
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b


def inputs(repo, project_id, intake_version_id, snapshot_id):
    tenant = repo.tenant_id
    if (
        not repo._context.permission.system
        and f"project:{project_id}:comply" not in repo._context.permission.scopes
    ):
        raise LookupError("structured intake not found")
    with repo._sessions() as s, s.begin():
        version = repo._get(
            s, b.ProjectVersionEntity, b.ProjectVersionEntity.project_version_id, intake_version_id
        )
        snapshot = repo._get(
            s, b.AnalysisSnapshotEntity, b.AnalysisSnapshotEntity.analysis_snapshot_id, snapshot_id
        )
        if (
            version is None
            or snapshot is None
            or version.project_id != str(project_id)
            or version.status not in {"CONFIRMED", "SUPERSEDED"}
            or snapshot.project_version_id != version.project_version_id
        ):
            raise LookupError("exact confirmed intake snapshot required")
        intake = ProjectIntakeContext.model_validate(version.intake_json)
        if intake.project_id != project_id or intake.record_version != version.version_no:
            raise ValueError("intake identity/version mismatch")
        confirmed = snapshot.provenance_json
        if (
            confirmed.get("intake_version") != version.version_no
            or not confirmed.get("confirmed_by")
            or not confirmed.get("confirmed_at")
        ):
            raise ValueError("confirmed intake audit required")
        definitions = s.scalars(
            select(m.MetadataDefinitionEntity).where(
                m.MetadataDefinitionEntity.tenant_id == tenant,
                m.MetadataDefinitionEntity.kind == "BUSINESS_FACT_TYPE",
                m.MetadataDefinitionEntity.status == "ACTIVE",
            )
        ).all()
        result = []
        for definition in definitions:
            if not definition.active_version_id:
                continue
            config = repo._get(
                s,
                m.MetadataVersionEntity,
                m.MetadataVersionEntity.version_id,
                UUID(definition.active_version_id),
            )
            if config is None:
                raise ValueError("structured binding version unavailable")
            raw = config.payload_json.get("structured_intake_binding")
            if raw is None:
                continue
            if (
                config.lifecycle_status != "ACTIVE"
                or not config.approved_by
                or not config.published_at
                or not s.scalar(
                    select(m.AdminPublishRecordEntity).where(
                        m.AdminPublishRecordEntity.tenant_id == tenant,
                        m.AdminPublishRecordEntity.object_kind == "BUSINESS_FACT_TYPE",
                        m.AdminPublishRecordEntity.version_id == config.version_id,
                    )
                )
            ):
                raise ValueError("structured binding requires reviewed published metadata")
            if (config.effective_from and config.effective_from > intake.analysis_as_of_date) or (
                config.effective_to and config.effective_to < intake.analysis_as_of_date
            ):
                continue
            if (
                not repo._context.permission.system
                and not set(config.payload_json.get("permission_scopes", []))
                <= repo._context.permission.scopes
            ):
                raise LookupError("structured binding not authorized")
            binding = StructuredIntakeBinding.model_validate(raw)
            original = getattr(intake, binding.field_path)
            if original is None or original == "" or original == []:
                continue
            normalized = binding.normalize(original)
            existing = s.scalar(
                select(m.AnalysisSnapshotRegistryPinEntity).where(
                    m.AnalysisSnapshotRegistryPinEntity.tenant_id == tenant,
                    m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(snapshot_id),
                    m.AnalysisSnapshotRegistryPinEntity.pin_type
                    == "STRUCTURED_INTAKE_FACT_BINDING",
                    m.AnalysisSnapshotRegistryPinEntity.logical_key == definition.definition_id,
                )
            )
            if existing and existing.version_id != config.version_id:
                raise ValueError("structured intake binding pin is immutable")
            if not existing:
                s.add(
                    m.AnalysisSnapshotRegistryPinEntity(
                        pin_id=str(uuid4()),
                        tenant_id=tenant,
                        analysis_snapshot_id=str(snapshot_id),
                        pin_type="STRUCTURED_INTAKE_FACT_BINDING",
                        logical_key=definition.definition_id,
                        object_id=definition.definition_id,
                        version_id=config.version_id,
                        version_no=config.version_no,
                    )
                )
            provenance = ProvenanceDTO(
                source_type="USER_INPUT",
                source_ref=version.project_version_id,
                source_version=str(version.version_no),
                source_locator=binding.field_path,
                actor_ref=confirmed["confirmed_by"],
                request_id=str(snapshot_id),
                generated_by="StructuredIntakeFormalization",
                generated_at=datetime.fromisoformat(confirmed["confirmed_at"]),
            )
            result.append(
                dict(
                    fact_type=definition.code,
                    normalized_value=normalized,
                    original_value=original,
                    confidence=1.0,
                    structured_provenance=(provenance,),
                )
            )
        return result


def validate_references(sessions, context, intake, snapshot_id):
    """Validate canonical intake references and freeze existing registry versions."""
    from crossborder_compliance.infrastructure.persistence import models as b

    tenant = str(context.tenant_id)
    with sessions() as s, s.begin():
        for kind, refs in (
            ("INDUSTRY", [intake.industry] if intake.industry else []),
            ("SCENARIO", [intake.business_scenario]),
            ("PRODUCT", intake.selected_products),
            ("PRODUCT_DOMAIN", intake.selected_product_domains),
            ("DATA_CATEGORY", intake.data_categories),
        ):
            for ref in dict.fromkeys(refs):
                definition = s.scalar(
                    select(m.MetadataDefinitionEntity).where(
                        m.MetadataDefinitionEntity.tenant_id == tenant,
                        m.MetadataDefinitionEntity.definition_id == str(UUID(ref)),
                        m.MetadataDefinitionEntity.kind == kind,
                        m.MetadataDefinitionEntity.status == "ACTIVE",
                    )
                )
                version = (
                    s.get(m.MetadataVersionEntity, definition.active_version_id)
                    if definition
                    else None
                )
                if (
                    not version
                    or version.tenant_id != tenant
                    or version.lifecycle_status != "ACTIVE"
                ):
                    raise LookupError("intake metadata not found")
                if (
                    version.effective_from and version.effective_from > intake.analysis_as_of_date
                ) or (version.effective_to and version.effective_to < intake.analysis_as_of_date):
                    raise ValueError("intake metadata outside effective period")
                if (
                    not context.permission.system
                    and not set(version.payload_json.get("permission_scopes", []))
                    <= context.permission.scopes
                ):
                    raise LookupError("intake metadata not authorized")
                s.add(
                    m.AnalysisSnapshotRegistryPinEntity(
                        pin_id=str(uuid4()),
                        tenant_id=tenant,
                        analysis_snapshot_id=str(snapshot_id),
                        pin_type="INTAKE_METADATA",
                        logical_key=definition.definition_id,
                        object_id=definition.definition_id,
                        version_id=version.version_id,
                        version_no=version.version_no,
                    )
                )
        for model, pk, refs in (
            (
                b.ProjectPartyEntity,
                b.ProjectPartyEntity.project_party_id,
                intake.organizations + intake.third_parties,
            ),
            (b.DocumentEntity, b.DocumentEntity.document_id, intake.uploaded_documents),
        ):
            for ref in dict.fromkeys(refs):
                row = s.scalar(
                    select(model).where(
                        model.tenant_id == tenant,
                        model.project_id == str(intake.project_id),
                        pk == str(UUID(ref)),
                        model.status == "ACTIVE",
                    )
                )
                if row is None:
                    raise LookupError("intake project reference not found")


def authorize_pins(sessions, context, snapshot_id):
    """Historical pins retain versions but never grant current access."""
    tenant = str(context.tenant_id)
    with sessions() as s:
        pins = s.scalars(
            select(m.AnalysisSnapshotRegistryPinEntity).where(
                m.AnalysisSnapshotRegistryPinEntity.tenant_id == tenant,
                m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(snapshot_id),
                m.AnalysisSnapshotRegistryPinEntity.pin_type.in_(
                    ["INTAKE_METADATA", "STRUCTURED_INTAKE_FACT_BINDING"]
                ),
            )
        ).all()
        for pin in pins:
            version = s.get(m.MetadataVersionEntity, pin.version_id)
            if not version or version.tenant_id != tenant or version.definition_id != pin.object_id:
                raise LookupError("intake pin not found")
            if (
                not context.permission.system
                and not set(version.payload_json.get("permission_scopes", []))
                <= context.permission.scopes
            ):
                raise LookupError("intake pin not authorized")
