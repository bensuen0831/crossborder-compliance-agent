from __future__ import annotations
from dataclasses import dataclass
from crossborder_compliance.application.ports import RuntimeOperationsPort

@dataclass(frozen=True)
class RuntimeContext:
    operations: RuntimeOperationsPort
    request_id: str
    graph_definition_version: str
    langgraph_runtime_version: str
    checkpointer_version: str
