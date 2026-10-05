from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from crossborder_compliance.domain.contracts import (
    ProvenanceDTO,
    WorkflowEventDTO,
    WorkflowEventType,
)

_ALLOWED = {e.value for e in WorkflowEventType}
_STATUSES = {"WAITING", "RUNNING", "COMPLETED", "WARNING", "REVIEW_REQUIRED", "FAILED"}


def canonical_event(
    *,
    event_type: WorkflowEventType,
    workflow_run_id: UUID,
    tenant_id: UUID,
    request_id: str,
    node_code: str | None = None,
    status: str | None = None,
    payload: dict[str, Any] | None = None,
    event_key: str | None = None,
) -> WorkflowEventDTO:
    if event_type.value not in _ALLOWED:
        raise ValueError("unsupported canonical workflow event")
    if status is not None and status not in _STATUSES:
        raise ValueError("unsupported canonical workflow status")
    if payload is not None:
        if "status" in payload and (
            payload["status"] not in _STATUSES or payload["status"] != status
        ):
            raise ValueError("canonical payload status must match event status")
        if "reason_codes" in payload:
            codes = payload["reason_codes"]
            if not isinstance(codes, (list, tuple)) or any(
                not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code)
                for code in codes
            ):
                raise ValueError("structured reason codes only")
    event_id = (
        uuid5(NAMESPACE_URL, f"workflow:{workflow_run_id}:{event_key}") if event_key else uuid4()
    )
    return WorkflowEventDTO(
        event_id=event_id,
        event_type=event_type,
        workflow_run_id=workflow_run_id,
        node_code=node_code,
        status=status,
        payload=payload or {},
        timestamp=datetime.now(UTC),
        request_id=request_id,
        provenance=ProvenanceDTO(
            source_type="workflow_runtime",
            source_ref=str(workflow_run_id),
            generated_by="LangGraphEventAdapter",
            request_id=request_id,
        ),
    )


def sanitize_raw_langgraph_event(raw: dict[str, Any]) -> dict[str, Any]:
    return {"raw_event_name": str(raw.get("event", "unknown")), "adapter_version": "1.0"}
