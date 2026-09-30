from __future__ import annotations
import json
import os
from pathlib import Path
from uuid import uuid4
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.infrastructure.persistence.runtime_operations import SqlRuntimeOperations
from crossborder_compliance.workflows.langgraph_adapter import LangGraphWorkflowRuntimeAdapter, installed_version
from crossborder_compliance.workflows.runtime_context import RuntimeContext
from crossborder_compliance.workflows.state import STATE_SCHEMA_VERSION

STATE_FILE = Path(os.getenv("SMOKE_STATE_FILE", "/tmp/phase1a_smoke_ids.json"))
GRAPH_DEFINITION_VERSION = "phase1a-smoke-v1"

def _checkpoint_row_count(uri: str, workflow_run_id: str) -> int:
    import psycopg
    with psycopg.connect(uri) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM checkpoints WHERE thread_id=%s", (workflow_run_id,))
            return int(cur.fetchone()[0])

def main() -> None:
    settings = get_settings()
    _engine, session_factory = build_session_factory(settings.database_url)
    repo = RuntimeRepository(session_factory)
    tenant_id = uuid4(); snapshot_id = uuid4(); workflow_run_id = uuid4(); project_version_id = uuid4()
    langgraph_version = installed_version("langgraph")
    checkpointer_version = installed_version("langgraph-checkpoint-postgres")
    repo.create_snapshot_and_run(
        snapshot_id=snapshot_id, workflow_run_id=workflow_run_id, tenant_id=tenant_id,
        project_version_id=project_version_id, graph_definition_version=GRAPH_DEFINITION_VERSION,
        langgraph_runtime_version=langgraph_version, checkpointer_version=checkpointer_version,
        state_schema_version=STATE_SCHEMA_VERSION,
    )
    context = RuntimeContext(
        operations=SqlRuntimeOperations(repo), request_id=f"smoke-{workflow_run_id}",
        graph_definition_version=GRAPH_DEFINITION_VERSION, langgraph_runtime_version=langgraph_version,
        checkpointer_version=checkpointer_version,
    )
    adapter = LangGraphWorkflowRuntimeAdapter(postgres_uri=settings.langgraph_database_uri, context=context)
    ref = adapter.start(workflow_run_id, {
        "workflow_run_id": str(workflow_run_id), "analysis_snapshot_id": str(snapshot_id),
        "tenant_id": str(tenant_id), "phase": "START", "node_a_completed": False, "completed": False,
    })
    checkpoint_state = adapter.inspect_checkpoint_state(workflow_run_id)
    checkpoint_rows = _checkpoint_row_count(settings.langgraph_database_uri, str(workflow_run_id))
    payload = {
        "workflow_run_id": str(workflow_run_id), "thread_id": ref.thread_id,
        "analysis_snapshot_id": str(snapshot_id), "tenant_id": str(tenant_id),
        "project_version_id": str(project_version_id), "graph_definition_version": GRAPH_DEFINITION_VERSION,
        "langgraph_runtime_version": langgraph_version, "checkpointer_version": checkpointer_version,
        "state_schema_version": STATE_SCHEMA_VERSION, "process1_checkpoint_row_count": checkpoint_rows,
        "process1_checkpoint_values": checkpoint_state["values"], "process1_checkpoint_next": checkpoint_state["next"],
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({"process":"start","workflow_run_id":str(workflow_run_id),"thread_id":ref.thread_id,
        "domain_status":ref.status,"review_task_count":repo.review_task_count(workflow_run_id),
        "checkpoint_row_count":checkpoint_rows,"checkpoint_next":checkpoint_state["next"]},sort_keys=True))
    if ref.status != "REVIEW_REQUIRED" or checkpoint_rows <= 0:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
