from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from crossborder_compliance.domain.contracts import WorkflowEventType
from crossborder_compliance.infrastructure.persistence.models import Base
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.workflows.events import canonical_event
def _repo():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return RuntimeRepository(sessionmaker(bind=engine,expire_on_commit=False))
def test_deterministic_canonical_event_is_idempotent_across_interrupt_replay():
    repo=_repo(); tenant=uuid4(); wf=uuid4(); snap=uuid4()
    repo.create_snapshot_and_run(snapshot_id=snap,workflow_run_id=wf,tenant_id=tenant,project_version_id=uuid4(),graph_definition_version="g",langgraph_runtime_version="l",checkpointer_version="c",state_schema_version="s")
    first=canonical_event(event_type=WorkflowEventType.REVIEW_REQUIRED,workflow_run_id=wf,tenant_id=tenant,request_id="r1",node_code="node_b",event_key="node_b:review-required")
    replay=canonical_event(event_type=WorkflowEventType.REVIEW_REQUIRED,workflow_run_id=wf,tenant_id=tenant,request_id="r2",node_code="node_b",event_key="node_b:review-required")
    assert first.event_id==replay.event_id
    repo.record_event(tenant,first); repo.record_event(tenant,replay)
    assert repo.canonical_event_types(wf)==[WorkflowEventType.REVIEW_REQUIRED.value]
def test_review_task_and_status_transitions_are_reentrant():
    repo=_repo(); tenant=uuid4(); wf=uuid4(); snap=uuid4()
    repo.create_snapshot_and_run(snapshot_id=snap,workflow_run_id=wf,tenant_id=tenant,project_version_id=uuid4(),graph_definition_version="g",langgraph_runtime_version="l",checkpointer_version="c",state_schema_version="s")
    r1=repo.ensure_review_task(workflow_run_id=wf,tenant_id=tenant,idempotency_key=f"review:{wf}")
    r2=repo.ensure_review_task(workflow_run_id=wf,tenant_id=tenant,idempotency_key=f"review:{wf}")
    assert r1==r2 and repo.review_task_count(wf)==1
    repo.set_status(wf,"REVIEW_REQUIRED"); repo.set_status(wf,"REVIEW_REQUIRED")
    assert repo.status(wf)=="REVIEW_REQUIRED"
