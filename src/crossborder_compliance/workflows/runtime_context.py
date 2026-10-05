from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from crossborder_compliance.application.ports import RuntimeOperationsPort


@dataclass(frozen=True)
class RuntimeContext:
    """Runtime dependencies; preferred locale is presentation-only, never checkpointed."""

    operations: RuntimeOperationsPort
    request_id: str
    graph_definition_version: str
    langgraph_runtime_version: str
    checkpointer_version: str
    preferred_locale: Literal["zh-CN", "zh-HK", "en-US"] | None = None

    def __post_init__(self) -> None:
        if self.preferred_locale not in {None, "zh-CN", "zh-HK", "en-US"}:
            raise ValueError("unsupported presentation locale")
