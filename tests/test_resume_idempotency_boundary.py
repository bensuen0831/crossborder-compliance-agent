from __future__ import annotations
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from crossborder_compliance.infrastructure.persistence.models import Base
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.infrastructure.persistence.runtime_operations import SqlRuntimeOperations
from crossborder_compliance.workflows.langgraph_adapter import LangGraphWorkflowRuntimeAdapter
from crossborder_compliance.workflows.runtime_context import RuntimeContext
def test_completed_resume_retry_returns_existing_without_langgraph_dependency():
    engine=create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine)
    repo=RuntimeRepository(sessionmaker(bind=engine,expire_on_commit=False))
    tenant=uuid4(); workflow_run_id=uuid4(); snapshot=uuid4()
    repo.create_snapshot_and_run(snapshot_id=snapshot,workflow_run_id=workflow_run_id,tenant_id=tenant,project_version_id=uuid4(),
        graph_definition_version="g",langgraph_runtime_version="l",checkpointer_version="c",state_schema_version="s")
    repo.mark_completed(workflow_run_id,tenant,snapshot)
    adapter=LangGraphWorkflowRuntimeAdapter(postgres_uri="postgresql://unused",context=RuntimeContext(
        operations=SqlRuntimeOperations(repo),request_id="retry",graph_definition_version="g",langgraph_runtime_version="l",checkpointer_version="c"))
    ref=adapter.resume(workflow_run_id,{"decision":"APPROVE"})
    assert ref.status=="COMPLETED"; assert ref.thread_id==str(workflow_run_id)
