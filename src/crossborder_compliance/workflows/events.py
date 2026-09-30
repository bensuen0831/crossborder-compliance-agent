from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5
from crossborder_compliance.domain.contracts import ProvenanceDTO, WorkflowEventDTO, WorkflowEventType

_ALLOWED = {e.value for e in WorkflowEventType}

def canonical_event(*, event_type: WorkflowEventType, workflow_run_id: UUID, tenant_id: UUID,
                    request_id: str, node_code: str | None = None, status: str | None = None,
                    payload: dict[str, Any] | None = None, event_key: str | None = None) -> WorkflowEventDTO:
    if event_type.value not in _ALLOWED:
        raise ValueError("unsupported canonical workflow event")
    event_id = uuid5(NAMESPACE_URL, f"workflow:{workflow_run_id}:{event_key}") if event_key else uuid4()
    return WorkflowEventDTO(
        event_id=event_id, event_type=event_type, workflow_run_id=workflow_run_id,
        node_code=node_code, status=status, payload=payload or {},
        timestamp=datetime.now(timezone.utc), request_id=request_id,
        provenance=ProvenanceDTO(source_type="workflow_runtime", source_ref=str(workflow_run_id),
            generated_by="LangGraphEventAdapter", request_id=request_id),
    )

def sanitize_raw_langgraph_event(raw: dict[str, Any]) -> dict[str, Any]:
    return {"raw_event_name": str(raw.get("event", "unknown")), "adapter_version": "1.0"}
