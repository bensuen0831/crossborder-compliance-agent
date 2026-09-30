from __future__ import annotations
from typing import NotRequired, TypedDict

class SmokeGraphState(TypedDict):
    workflow_run_id: str
    analysis_snapshot_id: str
    tenant_id: str
    phase: str
    node_a_completed: bool
    review_id: NotRequired[str]
    review_decision: NotRequired[dict[str, object]]
    completed: bool

STATE_SCHEMA_VERSION = "phase1a-smoke-state-v1"
