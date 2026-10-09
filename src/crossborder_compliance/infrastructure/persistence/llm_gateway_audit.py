"""Allowlisted gateway events in the existing canonical audit authority."""

from uuid import UUID, uuid5

from sqlalchemy import select

from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    AnalysisSnapshotRegistryPinEntity,
)
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    AuditEventEntity,
    ProjectVersionEntity,
)


class PostgresGatewayAudit:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context

    def record(self, event):
        if event.tenant_id != self.context.tenant_id:
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        with self.sessions() as s, s.begin():
            snapshot = s.scalar(
                select(AnalysisSnapshotEntity)
                .join(
                    ProjectVersionEntity,
                    AnalysisSnapshotEntity.project_version_id
                    == ProjectVersionEntity.project_version_id,
                )
                .where(
                    AnalysisSnapshotEntity.tenant_id == str(event.tenant_id),
                    AnalysisSnapshotEntity.analysis_snapshot_id == str(event.analysis_snapshot_id),
                    ProjectVersionEntity.tenant_id == str(event.tenant_id),
                    ProjectVersionEntity.project_id == str(event.project_id),
                )
            )
            if snapshot is None:
                raise GatewayDenied("RESOURCE_NOT_FOUND")
            run_id = UUID(snapshot.provenance_json["workflow_run_id"])
            identity = str(uuid5(event.request_id, f"{event.reason_code}:{event.model_id}"))
            if s.get(AuditEventEntity, identity) is None:
                payload = event.model_dump(mode="json")
                payload["actor_id"] = self.context.permission.actor_id
                pins = s.scalars(
                    select(AnalysisSnapshotRegistryPinEntity).where(
                        AnalysisSnapshotRegistryPinEntity.tenant_id == str(event.tenant_id),
                        AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id
                        == str(event.analysis_snapshot_id),
                        AnalysisSnapshotRegistryPinEntity.pin_type.in_(
                            ("LLM_PROMPT", "LLM_INVOCATION_POLICY")
                        ),
                    )
                ).all()
                payload["prompt_version_id"] = next(
                    (
                        p.version_id
                        for p in pins
                        if p.pin_type == "LLM_PROMPT" and p.object_id == str(event.prompt_id)
                    ),
                    None,
                )
                payload["invocation_policy_versions"] = sorted(
                    p.version_id for p in pins if p.pin_type == "LLM_INVOCATION_POLICY"
                )
                allowed_id = str(uuid5(event.request_id, f"ALLOWED:{event.model_id}"))
                started = s.get(AuditEventEntity, allowed_id)
                payload["started_at"] = (
                    started.occurred_at if started else event.recorded_at
                ).isoformat()
                payload["completed_at"] = (
                    event.recorded_at.isoformat() if event.reason_code != "ALLOWED" else None
                )
                s.add(
                    AuditEventEntity(
                        audit_event_id=identity,
                        tenant_id=str(event.tenant_id),
                        workflow_run_id=str(run_id),
                        analysis_snapshot_id=str(event.analysis_snapshot_id),
                        event_type=f"LLM_{event.reason_code}",
                        provenance_json=payload,
                        occurred_at=event.recorded_at,
                    )
                )
