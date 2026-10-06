"""Read-only scalar projections over the existing workflow persistence.

No new store or decision logic. ORM rows remain within persistence sessions.
"""

from uuid import UUID

from sqlalchemy import select

from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    ProjectEntity,
    ProjectVersionEntity,
    ReviewTaskEntity,
    WorkflowRunEntity,
)


class WorkflowReadProjection:
    def __init__(self, sessions, context):
        self.sessions = sessions
        self.tenant = str(context.tenant_id)

    def require_scope(self, project_id, snapshot_id):
        with self.sessions() as session:
            snapshot = session.get(AnalysisSnapshotEntity, str(snapshot_id))
            version = (
                session.get(ProjectVersionEntity, snapshot.project_version_id) if snapshot else None
            )
            project = session.get(ProjectEntity, str(project_id))
            if (
                not snapshot
                or not version
                or not project
                or version.project_id != str(project_id)
                or any(row.tenant_id != self.tenant for row in (snapshot, version, project))
                or snapshot.status != "ACTIVE"
                or project.status != "ACTIVE"
            ):
                raise LookupError("workflow resource not found")

    def run_scope(self, run_id):
        with self.sessions() as session:
            run = session.get(WorkflowRunEntity, str(run_id))
            snapshot = (
                session.get(AnalysisSnapshotEntity, run.analysis_snapshot_id) if run else None
            )
            version = (
                session.get(ProjectVersionEntity, snapshot.project_version_id) if snapshot else None
            )
            if (
                not run or run.tenant_id != self.tenant or not version or not snapshot
                or version.tenant_id != self.tenant or snapshot.tenant_id != self.tenant
            ):
                raise LookupError("workflow resource not found")
            return UUID(version.project_id), UUID(run.analysis_snapshot_id)

    def pending_review(self, run_id):
        with self.sessions() as session:
            return session.scalar(
                select(ReviewTaskEntity.review_id)
                .where(
                    ReviewTaskEntity.workflow_run_id == str(run_id),
                    ReviewTaskEntity.tenant_id == self.tenant,
                    ReviewTaskEntity.review_type == "WORKFLOW_STAGE_REVIEW",
                    ReviewTaskEntity.status == "PENDING",
                )
                .order_by(ReviewTaskEntity.created_at.desc())
            )
