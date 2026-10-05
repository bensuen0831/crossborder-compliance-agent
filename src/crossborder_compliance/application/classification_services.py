from __future__ import annotations

from typing import Protocol
from uuid import UUID

from crossborder_compliance.domain.classification import (
    ClassificationOutcome,
    ClassificationPolicy,
    ClassificationScheme,
    classify,
)
from crossborder_compliance.domain.rule_ast import MissingRuleFact
from crossborder_compliance.domain.rules import ComplianceRule, RuleFactContext, SafeRuleEngine


class ClassificationRepositoryPort(Protocol):
    def prepare(
        self,
        project_id: UUID,
        snapshot_id: UUID,
        data_item_id: UUID | None,
        scheme_version_id: UUID,
    ) -> tuple[RuleFactContext, ClassificationScheme, tuple[ComplianceRule, ...]]: ...
    def save(self, outcome: ClassificationOutcome) -> ClassificationOutcome: ...
    def get_result(self, result_id: UUID) -> dict: ...


class ClassificationService:
    def __init__(
        self, repository: ClassificationRepositoryPort, policy: ClassificationPolicy | None = None
    ):
        self.repository = repository
        self.policy = policy or ClassificationPolicy()

    def execute(
        self,
        *,
        project_id: UUID,
        snapshot_id: UUID,
        data_item_id: UUID | None,
        scheme_version_id: UUID,
    ) -> ClassificationOutcome:
        facts, scheme, rules = self.repository.prepare(
            project_id, snapshot_id, data_item_id, scheme_version_id
        )
        if facts.data_item_id is None:
            return ClassificationOutcome(status=self.policy.no_data, reason_codes=("NO_DATA_ITEM",))
        if not facts.values:
            return ClassificationOutcome(
                status="INSUFFICIENT_INPUT", reason_codes=("NO_FORMAL_FACTS",)
            )
        try:
            hits = SafeRuleEngine().evaluate(
                rules,
                facts,
                pinned_versions=frozenset(r.rule_version_id for r in rules),
                historical=True,
            )
        except MissingRuleFact:
            return ClassificationOutcome(
                status="INSUFFICIENT_INPUT", reason_codes=("MISSING_REQUIRED_FACT",)
            )
        outcome = classify(scheme, facts, hits)
        return self.repository.save(outcome)
