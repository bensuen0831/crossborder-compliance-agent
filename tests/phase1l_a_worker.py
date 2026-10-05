"""Synthetic orchestration port for real cross-process PostgreSQL runtime tests only."""

import json
import sys
from pathlib import Path
from uuid import UUID

from crossborder_compliance.application.workflow_skeleton import (
    SemanticStep,
    StageExecutionResult,
    StageOutcomeCode,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.infrastructure.persistence.runtime_operations import (
    SqlRuntimeOperations,
)
from crossborder_compliance.infrastructure.persistence.workflow_authorization import (
    SqlWorkflowAuthorization,
)
from crossborder_compliance.workflows.canonical import GRAPH_VERSION, CanonicalGraphFactory
from crossborder_compliance.workflows.langgraph_adapter import (
    LangGraphWorkflowRuntimeAdapter,
    installed_version,
)
from crossborder_compliance.workflows.runtime_context import RuntimeContext


class ReviewStage:
    def __init__(self, status):
        self.status = status

    def execute(self, request):
        return StageExecutionResult(
            status=StageOutcomeCode.SUCCESS if request.review_ref else self.status
        )


def adapter(ids):
    settings = get_settings()
    sessions = build_session_factory(settings.database_url)[1]
    context = RepositoryContext.user(
        UUID(ids["tenant"]), "reviewer", {"workflow:read", "workflow:execute", "workflow:review"}
    )
    auth = SqlWorkflowAuthorization(
        sessions, context, request_context_ref=UUID(ids["request"]), mode="SCENARIO_LEVEL"
    )
    factory = CanonicalGraphFactory(
        authorization=auth,
        stages={SemanticStep.REQUIREMENT: ReviewStage(ids.get("review_status", "REVIEW_REQUIRED"))},
    )
    repo = RuntimeRepository(sessions)
    runtime = LangGraphWorkflowRuntimeAdapter(
        postgres_uri=settings.langgraph_database_uri,
        context=RuntimeContext(
            SqlRuntimeOperations(repo),
            "test-request",
            GRAPH_VERSION,
            installed_version("langgraph"),
            installed_version("langgraph-checkpoint-postgres"),
        ),
        graph_factory=factory,
    )
    return runtime, factory, repo


if __name__ == "__main__":
    action, filename = sys.argv[1:]
    ids = json.loads(Path(filename).read_text())
    runtime, factory, repo = adapter(ids)
    wf = UUID(ids["run"])
    if action == "start":
        ref = runtime.start(wf, factory.initial_state(wf))
    else:
        ref = runtime.resume(wf, ids["decision"])
    print(
        json.dumps(
            {
                "status": ref.status,
                "reviews": repo.review_task_count(wf),
                "checkpoint": runtime.inspect_checkpoint_state(wf)["values"],
            }
        )
    )
