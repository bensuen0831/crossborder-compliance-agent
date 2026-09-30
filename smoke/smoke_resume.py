from __future__ import annotations
import json
import os
from pathlib import Path
from uuid import UUID
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.infrastructure.persistence.runtime_operations import SqlRuntimeOperations
from crossborder_compliance.workflows.langgraph_adapter import LangGraphWorkflowRuntimeAdapter, installed_version
from crossborder_compliance.workflows.runtime_context import RuntimeContext

STATE_FILE = Path(os.getenv("SMOKE_STATE_FILE", "/tmp/phase1a_smoke_ids.json"))

def main() -> None:
    ids = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    workflow_run_id = UUID(ids["workflow_run_id"])
    settings = get_settings()
    _engine, session_factory = build_session_factory(settings.database_url)
    repo = RuntimeRepository(session_factory)
    context = RuntimeContext(operations=SqlRuntimeOperations(repo),request_id=f"smoke-resume-{workflow_run_id}",
        graph_definition_version=ids["graph_definition_version"],langgraph_runtime_version=installed_version("langgraph"),
        checkpointer_version=installed_version("langgraph-checkpoint-postgres"))
    adapter = LangGraphWorkflowRuntimeAdapter(postgres_uri=settings.langgraph_database_uri,context=context)
    before = adapter.inspect_checkpoint_state(workflow_run_id)
    values = before["values"]
    preserved = (values.get("workflow_run_id")==ids["workflow_run_id"]
        and values.get("analysis_snapshot_id")==ids["analysis_snapshot_id"]
        and values.get("tenant_id")==ids["tenant_id"])
    if not preserved:
        print(json.dumps({"process":"resume","checkpoint_context_preserved":False,"values":values},default=str))
        raise SystemExit(2)
    decision={"decision":"APPROVE","decided_by":"phase1a-smoke"}
    ref=adapter.resume(workflow_run_id,decision)
    ids["process2_checkpoint_context_preserved"]=preserved
    ids["process2_checkpoint_values_before_resume"]=values
    ids["review_decision"]=decision
    STATE_FILE.write_text(json.dumps(ids,indent=2,sort_keys=True,default=str),encoding="utf-8")
    print(json.dumps({"process":"resume","workflow_run_id":str(workflow_run_id),"thread_id":ref.thread_id,
        "domain_status":ref.status,"checkpoint_context_preserved":preserved,
        "review_task_count":repo.review_task_count(workflow_run_id),
        "canonical_events":repo.canonical_event_types(workflow_run_id)},sort_keys=True))
    if ref.status!="COMPLETED":
        raise SystemExit(2)

if __name__=="__main__":
    main()
