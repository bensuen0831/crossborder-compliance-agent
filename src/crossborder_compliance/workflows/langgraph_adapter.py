from __future__ import annotations

import importlib.metadata
import os
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from crossborder_compliance.domain.contracts import ReviewDecisionDTO, WorkflowEventDTO, WorkflowEventType
from crossborder_compliance.workflows.events import canonical_event
from crossborder_compliance.workflows.ports import WorkflowRunRef, WorkflowRuntimePort
from crossborder_compliance.workflows.runtime_context import RuntimeContext
from crossborder_compliance.workflows.state import SmokeGraphState

class LangGraphDependencyError(RuntimeError):
    pass

def _require_langgraph():
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command, interrupt
        return END, START, StateGraph, Command, interrupt, PostgresSaver
    except ImportError as exc:
        raise LangGraphDependencyError(
            "Install langgraph>=1.2,<1.3 and langgraph-checkpoint-postgres>=3.1,<3.2 with psycopg"
        ) from exc

def installed_version(name: str, fallback: str = "unavailable") -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return fallback

class LangGraphWorkflowRuntimeAdapter(WorkflowRuntimePort):
    def __init__(self, *, postgres_uri: str, context: RuntimeContext):
        self.postgres_uri = postgres_uri
        self.context = context
        if os.getenv("LANGGRAPH_STRICT_MSGPACK", "true").lower() not in {"1", "true", "yes"}:
            raise ValueError("LANGGRAPH_STRICT_MSGPACK must be enabled")

    def _graph(self, checkpointer):
        END, START, StateGraph, _Command, interrupt, _ = _require_langgraph()
        ops = self.context.operations
        request_id = self.context.request_id

        def node_a(state: SmokeGraphState) -> dict[str, Any]:
            wf = UUID(state["workflow_run_id"])
            tenant = UUID(state["tenant_id"])
            ops.record_event(
                tenant,
                canonical_event(
                    event_type=WorkflowEventType.NODE_COMPLETED,
                    workflow_run_id=wf,
                    tenant_id=tenant,
                    request_id=request_id,
                    node_code="node_a",
                    status="COMPLETED",
                    payload={"phase": "A_DONE"},
                    event_key="node_a:completed",
                ),
            )
            return {"phase": "A_DONE", "node_a_completed": True}

        def node_b(state: SmokeGraphState) -> dict[str, Any]:
            wf = UUID(state["workflow_run_id"])
            tenant = UUID(state["tenant_id"])
            review_id = ops.ensure_review_task(
                workflow_run_id=wf,
                tenant_id=tenant,
                idempotency_key=f"phase1a-review:{wf}",
            )
            ops.mark_review_required(wf)
            ops.record_event(
                tenant,
                canonical_event(
                    event_type=WorkflowEventType.REVIEW_REQUIRED,
                    workflow_run_id=wf,
                    tenant_id=tenant,
                    request_id=request_id,
                    node_code="node_b",
                    status="REVIEW_REQUIRED",
                    payload={"review_id": str(review_id)},
                    event_key="node_b:review-required",
                ),
            )
            decision = interrupt(
                {"review_id": str(review_id), "action": "Approve Phase 1A smoke continuation"}
            )
            ops.resolve_review(review_id, decision)
            ops.mark_resumed(wf)
            ops.record_event(
                tenant,
                canonical_event(
                    event_type=WorkflowEventType.WORKFLOW_RESUMED,
                    workflow_run_id=wf,
                    tenant_id=tenant,
                    request_id=request_id,
                    node_code="node_b",
                    status="RUNNING",
                    payload={"review_id": str(review_id)},
                    event_key="node_b:resumed",
                ),
            )
            return {"phase": "RESUMED", "review_id": str(review_id), "review_decision": decision}

        def node_c(state: SmokeGraphState) -> dict[str, Any]:
            wf = UUID(state["workflow_run_id"])
            tenant = UUID(state["tenant_id"])
            snapshot = UUID(state["analysis_snapshot_id"])
            ops.mark_completed(wf, tenant, snapshot)
            ops.record_event(
                tenant,
                canonical_event(
                    event_type=WorkflowEventType.WORKFLOW_COMPLETED,
                    workflow_run_id=wf,
                    tenant_id=tenant,
                    request_id=request_id,
                    node_code="node_c",
                    status="COMPLETED",
                    payload={"phase": "COMPLETED"},
                    event_key="node_c:completed",
                ),
            )
            return {"phase": "COMPLETED", "completed": True}

        graph = StateGraph(SmokeGraphState)
        graph.add_node("node_a", node_a)
        graph.add_node("node_b", node_b)
        graph.add_node("node_c", node_c)
        graph.add_edge(START, "node_a")
        graph.add_edge("node_a", "node_b")
        graph.add_edge("node_b", "node_c")
        graph.add_edge("node_c", END)
        return graph.compile(checkpointer=checkpointer)

    @staticmethod
    def _config(workflow_run_id: UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(workflow_run_id)}, "recursion_limit": 20}

    def start(self, workflow_run_id: UUID, initial_state: dict[str, Any]) -> WorkflowRunRef:
        *_, PostgresSaver = _require_langgraph()
        with PostgresSaver.from_conn_string(self.postgres_uri) as checkpointer:
            checkpointer.setup()
            graph = self._graph(checkpointer)
            tenant = UUID(str(initial_state["tenant_id"]))
            self.context.operations.record_event(
                tenant,
                canonical_event(
                    event_type=WorkflowEventType.WORKFLOW_STARTED,
                    workflow_run_id=workflow_run_id,
                    tenant_id=tenant,
                    request_id=self.context.request_id,
                    status="RUNNING",
                    event_key="workflow:started",
                ),
            )
            graph.invoke(initial_state, self._config(workflow_run_id))
        return WorkflowRunRef(
            workflow_run_id=workflow_run_id,
            thread_id=str(workflow_run_id),
            status=self.get_status(workflow_run_id),
        )

    def resume(
        self,
        workflow_run_id: UUID,
        review_decision: ReviewDecisionDTO | dict[str, Any],
    ) -> WorkflowRunRef:
        current_status = self.get_status(workflow_run_id)
        if current_status == "COMPLETED":
            return WorkflowRunRef(
                workflow_run_id=workflow_run_id,
                thread_id=str(workflow_run_id),
                status=current_status,
            )

        _END, _START, _StateGraph, Command, _interrupt, PostgresSaver = _require_langgraph()
        decision = (
            review_decision.model_dump(mode="json")
            if isinstance(review_decision, ReviewDecisionDTO)
            else review_decision
        )
        with PostgresSaver.from_conn_string(self.postgres_uri) as checkpointer:
            checkpointer.setup()
            graph = self._graph(checkpointer)
            graph.invoke(Command(resume=decision), self._config(workflow_run_id))
        return WorkflowRunRef(
            workflow_run_id=workflow_run_id,
            thread_id=str(workflow_run_id),
            status=self.get_status(workflow_run_id),
        )

    def inspect_checkpoint_state(self, workflow_run_id: UUID) -> dict[str, Any]:
        *_, PostgresSaver = _require_langgraph()
        with PostgresSaver.from_conn_string(self.postgres_uri) as checkpointer:
            checkpointer.setup()
            graph = self._graph(checkpointer)
            snapshot = graph.get_state(self._config(workflow_run_id))
            return {
                "values": dict(snapshot.values or {}),
                "next": list(snapshot.next or ()),
                "created_at": snapshot.created_at,
                "config": dict(snapshot.config or {}),
            }

    def cancel(self, workflow_run_id: UUID) -> None:
        raise NotImplementedError("Phase 1A skeleton")

    def get_status(self, workflow_run_id: UUID) -> str:
        return self.context.operations.status(workflow_run_id)

    def stream_events(self, workflow_run_id: UUID) -> Iterable[WorkflowEventDTO]:
        return iter(())
