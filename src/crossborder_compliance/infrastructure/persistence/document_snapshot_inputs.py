"""Pin the existing intake/document/parse authorities before E formalization."""
from uuid import UUID

from sqlalchemy import select

from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.document_repositories import PostgresDocumentIntelligenceRepository


def pin_intake_document_inputs(sessions, context, project_id, snapshot_id):
    tenant = str(context.tenant_id)
    with sessions() as session:
        snapshot = session.get(b.AnalysisSnapshotEntity, str(snapshot_id))
        version = session.get(b.ProjectVersionEntity, snapshot.project_version_id)
        if snapshot.tenant_id != tenant or version.project_id != str(project_id) or version.status != "CONFIRMED":
            raise LookupError("confirmed snapshot input unavailable")
        if snapshot.provenance_json.get("document_input_universe_pinned"):
            return tuple(UUID(run_id) for run_id in session.scalars(select(d.AnalysisSnapshotParseRunPinEntity.parse_run_id).where(
                d.AnalysisSnapshotParseRunPinEntity.tenant_id == tenant,
                d.AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id == str(snapshot_id),
            )).all())
        # Explicit production links are authoritative even after unlinking all
        # documents. Legacy trusted D inputs can only use their active versions.
        managed = session.scalar(select(d.ProjectVersionDocumentLinkEntity.link_id).join(
            b.ProjectVersionEntity,
            b.ProjectVersionEntity.project_version_id == d.ProjectVersionDocumentLinkEntity.project_version_id,
        ).where(b.ProjectVersionEntity.project_id == str(project_id), d.ProjectVersionDocumentLinkEntity.tenant_id == tenant)) is not None
        if managed:
            version_ids = session.scalars(select(d.ProjectVersionDocumentLinkEntity.document_version_id).where(
                d.ProjectVersionDocumentLinkEntity.tenant_id == tenant,
                d.ProjectVersionDocumentLinkEntity.project_version_id == version.project_version_id,
            )).all()
        else:
            version_ids = session.scalars(select(b.DocumentEntity.active_version_id).where(
                b.DocumentEntity.tenant_id == tenant, b.DocumentEntity.project_id == str(project_id),
                b.DocumentEntity.status == "ACTIVE", b.DocumentEntity.active_version_id.is_not(None),
            )).all()
        selected = []
        for version_id in version_ids:
            document_version = session.get(b.DocumentVersionEntity, version_id)
            document = session.get(b.DocumentEntity, document_version.document_id)
            if document_version.tenant_id != tenant or document.tenant_id != tenant or document.project_id != str(project_id):
                raise LookupError("document outside snapshot project")
            # Native-v1 has a canonical durable parse task; legacy D sources
            # retain their existing successful run contract, never fabricate one.
            run = session.scalar(select(d.DocumentParseRunDetailEntity).where(
                d.DocumentParseRunDetailEntity.tenant_id == tenant,
                d.DocumentParseRunDetailEntity.document_version_id == version_id,
            ).order_by(d.DocumentParseRunDetailEntity.parse_run_version.desc()))
            base_run = session.get(b.DocumentParseRunEntity, run.parse_run_id) if run else None
            if base_run is None or base_run.status != "COMPLETED":
                raise ValueError("INSUFFICIENT_INPUT: DOCUMENT_PARSE_NOT_READY")
            quality = session.scalar(select(d.DocumentParseQualityEntity).where(
                d.DocumentParseQualityEntity.tenant_id == tenant, d.DocumentParseQualityEntity.parse_run_id == run.parse_run_id))
            if quality is None or quality.quality_status not in {"PASS", "WARNING"}:
                raise ValueError("REVIEW_REQUIRED: DOCUMENT_PARSE_QUALITY")
            selected.append((UUID(version_id), UUID(run.parse_run_id)))
    repo = PostgresDocumentIntelligenceRepository(sessions, context)
    for version_id, run_id in selected:
        repo.pin_parse_run(analysis_snapshot_id=snapshot_id, document_version_id=version_id, parse_run_id=run_id)
    with sessions() as session, session.begin():
        snapshot = session.get(b.AnalysisSnapshotEntity, str(snapshot_id))
        snapshot.provenance_json = {**snapshot.provenance_json, "document_input_universe_pinned": True}
    return tuple(run_id for _, run_id in selected)
