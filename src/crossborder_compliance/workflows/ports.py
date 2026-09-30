from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from crossborder_compliance.domain.contracts import ReviewDecisionDTO, WorkflowEventDTO

@dataclass(frozen=True)
class WorkflowRunRef:
    workflow_run_id: UUID
    thread_id: str
    status: str

class WorkflowRuntimePort(ABC):
    @abstractmethod
    def start(self, workflow_run_id: UUID, initial_state: dict[str, Any]) -> WorkflowRunRef: ...
    @abstractmethod
    def resume(self, workflow_run_id: UUID, review_decision: ReviewDecisionDTO | dict[str, Any]) -> WorkflowRunRef: ...
    @abstractmethod
    def cancel(self, workflow_run_id: UUID) -> None: ...
    @abstractmethod
    def get_status(self, workflow_run_id: UUID) -> str: ...
    @abstractmethod
    def stream_events(self, workflow_run_id: UUID) -> Iterable[WorkflowEventDTO]: ...
