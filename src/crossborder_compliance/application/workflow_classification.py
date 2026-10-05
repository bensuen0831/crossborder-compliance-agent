"""Reuse Phase 1H formal classification without embedding legal logic in a node."""

from crossborder_compliance.application.workflow_skeleton import (
    StageExecutionResult,
    StageOutcomeCode,
)


class ClassificationWorkflowStage:
    def __init__(self, service, *, project_id, snapshot_id, data_item_id, scheme_version_id):
        self.service = service
        self.project_id = project_id
        self.snapshot_id = snapshot_id
        self.data_item_id = data_item_id
        self.scheme_version_id = scheme_version_id

    def execute(self, request):
        if (request.identity.project_id, request.identity.analysis_snapshot_id) != (
            self.project_id,
            self.snapshot_id,
        ):
            raise PermissionError("classification context not found")
        outcome = self.service.execute(
            project_id=self.project_id,
            snapshot_id=self.snapshot_id,
            data_item_id=self.data_item_id,
            scheme_version_id=self.scheme_version_id,
        )
        status = (
            StageOutcomeCode.SUCCESS
            if outcome.status == "CLASSIFIED"
            else StageOutcomeCode(outcome.status)
        )
        return StageExecutionResult(
            status=status,
            result_ref=outcome.result.classification_result_id if outcome.result else None,
            reason_codes=outcome.reason_codes,
        )
