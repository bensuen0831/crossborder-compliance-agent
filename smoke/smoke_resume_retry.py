from __future__ import annotations
import json
import os
from collections import Counter
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
    ids=json.loads(STATE_FILE.read_text(encoding="utf-8"))
    workflow_run_id=UUID(ids["workflow_run_id"]); settings=get_settings()
    _engine,session_factory=build_session_factory(settings.database_url); repo=RuntimeRepository(session_factory)
    before_events=Counter(repo.canonical_event_types(workflow_run_id)); before_reviews=repo.review_task_count(workflow_run_id)
    context=RuntimeContext(operations=SqlRuntimeOperations(repo),request_id=f"smoke-retry-{workflow_run_id}",
        graph_definition_version=ids["graph_definition_version"],langgraph_runtime_version=installed_version("langgraph"),
        checkpointer_version=installed_version("langgraph-checkpoint-postgres"))
    adapter=LangGraphWorkflowRuntimeAdapter(postgres_uri=settings.langgraph_database_uri,context=context)
    ref=adapter.resume(workflow_run_id,ids["review_decision"])
    after_events=Counter(repo.canonical_event_types(workflow_run_id)); after_reviews=repo.review_task_count(workflow_run_id)
    safe=(ref.status=="COMPLETED" and before_reviews==after_reviews==1 and before_events==after_events)
    ids["resume_retry_safe"]=safe; ids["resume_retry_returned_existing_status"]=ref.status
    ids["resume_retry_event_counts_unchanged"]=before_events==after_events
    ids["resume_retry_review_count_unchanged"]=before_reviews==after_reviews==1
    STATE_FILE.write_text(json.dumps(ids,indent=2,sort_keys=True,default=str),encoding="utf-8")
    print(json.dumps({"process":"resume-retry","safe":safe,"status":ref.status,
        "review_task_count_before":before_reviews,"review_task_count_after":after_reviews,
        "event_counts_before":dict(before_events),"event_counts_after":dict(after_events)},sort_keys=True))
    raise SystemExit(0 if safe else 2)

if __name__=="__main__":
    main()
