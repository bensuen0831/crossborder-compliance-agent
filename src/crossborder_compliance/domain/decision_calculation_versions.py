"""Frozen support propagation strategies within the single FormalDecision owner.

Legacy semantics exactly match merge_support at formal baseline df3a109 and PR
head 4c79243. Only the historical verifier selects them. No laws/rules are copied.
"""
from dataclasses import dataclass
from typing import Callable, Iterable

from crossborder_compliance.domain.decision_contracts import DecisionEngineVersion, LegalSupport, unique


def legacy_merge_support(supports):
    # Preserve the original single-pass consumption, including its exhaustion.
    return LegalSupport(
        **{
            key: unique(v for s in supports for v in getattr(s, key))
            for key in LegalSupport.model_fields
        }
    )


@dataclass(frozen=True)
class DecisionCalculation:
    engine_version: DecisionEngineVersion
    merge_support: Callable[[Iterable[LegalSupport]], LegalSupport]
