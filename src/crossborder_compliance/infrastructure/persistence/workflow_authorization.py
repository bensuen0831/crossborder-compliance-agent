"""Fresh existing DB/security authority, never checkpoint identity or client thread ID."""

from uuid import UUID

from crossborder_compliance.application.workflow_skeleton import ExecutionIdentity
from crossborder_compliance.domain.contracts import ReviewDecisionDTO
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    ProjectEntity,
    ProjectVersionEntity,
    ReviewTaskEntity,
    WorkflowRunEntity,
)


class SqlWorkflowAuthorization:
    def __init__(self, sessions, context, *, request_context_ref, mode):
        self.sessions = sessions
        self.context = context
        self.request_context_ref = request_context_ref
        self.mode = mode

    def authorize(self, workflow_run_id, operation):
        required = {
            "read": "workflow:read",
            "execute": "workflow:execute",
            "review": "workflow:review",
        }[operation]
        if required not in self.context.permission.scopes:
            raise PermissionError("workflow not found")
        with self.sessions() as s:
            run = s.get(WorkflowRunEntity, str(workflow_run_id))
            if run is None or run.tenant_id != str(self.context.tenant_id):
                raise PermissionError("workflow not found")
            self.context.assert_tenant(UUID(run.tenant_id))
            snapshot = s.get(AnalysisSnapshotEntity, run.analysis_snapshot_id)
            version = s.get(ProjectVersionEntity, snapshot.project_version_id) if snapshot else None
            project = s.get(ProjectEntity, version.project_id) if version else None
            if (
                snapshot is None
                or version is None
                or project is None
                or any(v.tenant_id != run.tenant_id for v in (snapshot, version, project))
                or snapshot.status != "ACTIVE"
                or project.status != "ACTIVE"
                or run.thread_id != str(workflow_run_id)
            ):
                raise PermissionError("workflow not found")
            return ExecutionIdentity(
                workflow_run_id=workflow_run_id,
                tenant_id=UUID(run.tenant_id),
                project_id=UUID(project.project_id),
                analysis_snapshot_id=UUID(snapshot.analysis_snapshot_id),
                request_context_ref=self.request_context_ref,
                mode=self.mode,
                graph_definition_version=run.graph_definition_version,
                state_schema_version=run.state_schema_version,
                langgraph_runtime_version=run.langgraph_runtime_version,
                checkpointer_version=run.checkpointer_version,
            )

    def authorize_review(self, workflow_run_id, decision):
        identity = self.authorize(workflow_run_id, "review")
        parsed = ReviewDecisionDTO.model_validate(decision)
        if parsed.decided_by != self.context.permission.actor_id:
            raise PermissionError("review not found")
        with self.sessions() as s:
            review = s.get(ReviewTaskEntity, str(parsed.review_id))
            if (
                review is None
                or review.tenant_id != str(identity.tenant_id)
                or review.workflow_run_id != str(workflow_run_id)
                or review.review_type != "WORKFLOW_STAGE_REVIEW"
            ):
                raise PermissionError("review not found")
            value = parsed.model_dump(mode="json")
            if review.status != "PENDING" and review.decision_json != value:
                raise ValueError("REVIEW_ALREADY_RESOLVED")
            return value
