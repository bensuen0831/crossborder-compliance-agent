from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.infrastructure.persistence.runtime_operations import (
    SqlRuntimeOperations,
)
from crossborder_compliance.workflows.langgraph_adapter import (
    LangGraphWorkflowRuntimeAdapter,
)
from crossborder_compliance.workflows.runtime_context import RuntimeContext

STATE_FILE = Path(os.getenv("SMOKE_STATE_FILE", "/tmp/phase1a_smoke_ids.json"))


def main() -> None:
    ids = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    workflow_run_id = UUID(ids["workflow_run_id"])
    settings = get_settings()
    _engine, session_factory = build_session_factory(settings.database_url)
    repo = RuntimeRepository(session_factory)
    operations = SqlRuntimeOperations(repo)

    authoritative = operations.load_authoritative_workflow_context(workflow_run_id)
    domain_context = {
        "workflow_run_id": str(authoritative.workflow_run_id),
        "thread_id": authoritative.thread_id,
        "tenant_id": str(authoritative.tenant_id),
        "analysis_snapshot_id": str(authoritative.analysis_snapshot_id),
        "status": authoritative.status,
        "pending_review_ids": [
            str(review_id) for review_id in authoritative.pending_review_ids
        ],
        "graph_definition_version": authoritative.graph_definition_version,
        "langgraph_runtime_version": authoritative.langgraph_runtime_version,
        "checkpointer_version": authoritative.checkpointer_version,
        "state_schema_version": authoritative.state_schema_version,
    }

    if (
        domain_context["workflow_run_id"] != ids["workflow_run_id"]
        or domain_context["thread_id"] != ids["workflow_run_id"]
        or domain_context["status"] != "REVIEW_REQUIRED"
        or len(domain_context["pending_review_ids"]) != 1
    ):
        print(
            json.dumps(
                {
                    "process": "resume",
                    "domain_authorization_valid": False,
                    "domain_context": domain_context,
                },
                default=str,
            )
        )
        raise SystemExit(2)

    context = RuntimeContext(
        operations=operations,
        request_id=f"smoke-resume-{workflow_run_id}",
        graph_definition_version=authoritative.graph_definition_version,
        langgraph_runtime_version=authoritative.langgraph_runtime_version,
        checkpointer_version=authoritative.checkpointer_version,
    )
    adapter = LangGraphWorkflowRuntimeAdapter(
        postgres_uri=settings.langgraph_database_uri,
        context=context,
    )

    before = adapter.inspect_checkpoint_state(workflow_run_id)
    values = before["values"]
    checkpoint_consistent = (
        values.get("workflow_run_id") == domain_context["workflow_run_id"]
        and values.get("analysis_snapshot_id")
        == domain_context["analysis_snapshot_id"]
        and values.get("tenant_id") == domain_context["tenant_id"]
    )
    if not checkpoint_consistent:
        print(
            json.dumps(
                {
                    "process": "resume",
                    "domain_authorization_valid": True,
                    "checkpoint_consistency": False,
                    "domain_context": domain_context,
                    "checkpoint_values": values,
                },
                default=str,
            )
        )
        raise SystemExit(2)

    decision = {"decision": "APPROVE", "decided_by": "phase1a-smoke"}
    ref = adapter.resume(workflow_run_id, decision)

    ids["process2_domain_authoritative_context"] = domain_context
    ids["process2_domain_context_authoritative"] = True
    ids["process2_checkpoint_consistency_only"] = checkpoint_consistent
    ids["process2_checkpoint_context_preserved"] = checkpoint_consistent
    ids["process2_checkpoint_values_before_resume"] = values
    ids["review_decision"] = decision
    STATE_FILE.write_text(
        json.dumps(ids, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "process": "resume",
                "workflow_run_id": str(workflow_run_id),
                "thread_id": ref.thread_id,
                "domain_status": ref.status,
                "domain_authorization_source": "WorkflowRun/AnalysisSnapshot Repository",
                "checkpoint_role": "runtime recovery + consistency assertion only",
                "checkpoint_context_preserved": checkpoint_consistent,
                "review_task_count": repo.review_task_count(workflow_run_id),
                "canonical_events": repo.canonical_event_types(workflow_run_id),
            },
            sort_keys=True,
        )
    )
    if ref.status != "COMPLETED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
