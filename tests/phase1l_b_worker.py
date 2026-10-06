"""Cross-process real owning-service composition; test manifest holds refs only."""

import json
import os
import sys
from pathlib import Path
from uuid import UUID

from crossborder_compliance.application.workflow_formal import FormalWorkflowPlan
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.workflow_formal_composition import (
    formal_workflow_runtime,
)


def build(manifest):
    settings = get_settings()
    context = RepositoryContext.user(UUID(manifest["tenant"]), "author", set(manifest["scopes"]))
    return formal_workflow_runtime(
        sessions=build_session_factory(settings.database_url)[1],
        context=context,
        plan=FormalWorkflowPlan.model_validate(manifest["plan"]),
        postgres_uri=settings.langgraph_database_uri,
        request_id="formal-workflow-test",
        preferred_locale=manifest.get("locale"),
    )


if __name__ == "__main__":
    action, filename = sys.argv[1:]
    manifest = json.loads(Path(filename).read_text())
    runtime, factory = build(manifest)
    if manifest.get("crash_stage"):
        from crossborder_compliance.application.workflow_skeleton import SemanticStep

        step = SemanticStep(manifest["crash_stage"])
        original = factory.stages[step]

        class CrashAfterSideEffects:
            def execute(self, request):
                original.execute(request)
                os._exit(73)

        factory.stages[step] = CrashAfterSideEffects()
    wf = UUID(manifest["run"])
    if action == "start":
        runtime.start(wf, factory.initial_state(wf))
    elif action == "resume":
        runtime.resume(wf, manifest["decision"])
    elif action != "inspect":
        raise ValueError("invalid operation")
    checkpoint = runtime.inspect_checkpoint_state(wf)
    print(
        json.dumps(
            {
                "status": runtime.get_status(wf),
                "state": checkpoint["values"],
                "checkpoint_id": checkpoint["config"]["configurable"]["checkpoint_id"],
                "next": checkpoint["next"],
            }
        )
    )
