"""Versioned legal rule contracts and deterministic evaluation; no infrastructure imports."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crossborder_compliance.domain.rule_ast import (
    FieldType,
    RuleValidationError,
    evaluate,
    parse_ast,
    typed_value,
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClassificationAction(Contract):
    kind: Literal["CLASSIFY"] = "CLASSIFY"
    scheme_version_id: UUID
    category_ids: tuple[UUID, ...] = ()
    level_id: UUID | None = None
    reason_code: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def target(self):
        if not self.category_ids and self.level_id is None:
            raise ValueError("classification action needs category or level")
        return self


class RuleScope(Contract):
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1)
    industry_codes: tuple[str, ...] = ()
    scenario_codes: tuple[str, ...] = ()
    product_codes: tuple[str, ...] = ()
    data_category_codes: tuple[str, ...] = ()


class RuleFactContext(Contract):
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    context_version: int = Field(ge=1)
    data_item_id: UUID | None
    jurisdiction_id: UUID
    as_of: date
    values: dict[str, object]
    fact_refs: dict[str, tuple[UUID, ...]]
    evidence_ids: tuple[UUID, ...] = ()
    evidence_types: tuple[str, ...] = ()
    industry_codes: tuple[str, ...] = ()
    scenario_codes: tuple[str, ...] = ()
    product_codes: tuple[str, ...] = ()
    data_category_codes: tuple[str, ...] = ()
    confidence: float = Field(default=1.0, ge=0, le=1)
    review_required: bool = False


class RuleTestCase(Contract):
    facts: dict[str, object]
    expected_match: bool
    expected_actions: tuple[ClassificationAction, ...]
    expected_severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"] | None
    expected_evidence_requirement: tuple[str, ...]


class RuleContract(Contract):
    dsl_version: Literal[1] = 1
    fields: dict[str, FieldType]
    conditions: dict[str, object]
    actions: tuple[ClassificationAction, ...] = Field(min_length=1, max_length=50)
    scope: RuleScope
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    priority: int = Field(ge=0, le=100000)
    legal_basis_ids: tuple[UUID, ...] = ()
    evidence_required: tuple[str, ...] = ()
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_contract(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("invalid effective date interval")
        parse_ast(self.conditions, self.fields)
        return self


class ComplianceRule(Contract):
    rule_id: UUID
    rule_version_id: UUID
    tenant_id: UUID
    version: int = Field(ge=1)
    contract: RuleContract
    lifecycle: Literal["DRAFT", "PENDING_REVIEW", "APPROVED", "ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"]
    approved_by: str | None = None
    published_by: str | None = None


class RuleHit(Contract):
    rule_hit_id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    rule_version_id: UUID
    tenant_id: UUID
    project_id: UUID
    data_item_id: UUID | None
    analysis_snapshot_id: UUID
    context_version: int
    matched: bool
    triggered_actions: tuple[ClassificationAction, ...]
    severity: str | None
    priority: int
    legal_basis_ids: tuple[UUID, ...]
    evidence_requirement: tuple[str, ...]
    evidence_ids: tuple[UUID, ...]
    matched_fact_refs: tuple[UUID, ...]
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason_code: str
    review_required: bool
    validation_status: Literal["VALIDATED"] = "VALIDATED"


def run_rule_tests(contract: RuleContract, cases: tuple[RuleTestCase, ...]) -> None:
    if not cases:
        raise RuleValidationError("at least one persisted rule test is required")
    ast = parse_ast(contract.conditions, contract.fields)
    for case in cases:
        facts = {k: typed_value(v, contract.fields[k], literal=True) for k, v in case.facts.items()
                 if k in contract.fields}
        if set(case.facts) - set(contract.fields):
            raise RuleValidationError("test has unknown field")
        match = evaluate(ast, facts)
        if (match != case.expected_match
            or (contract.actions if match else ()) != case.expected_actions
            or (contract.severity if match else None) != case.expected_severity
            or (contract.evidence_required if match else ()) != case.expected_evidence_requirement):
            raise RuleValidationError("rule test failed")


def validate_conflicts(rules: tuple[ComplianceRule, ...]) -> None:
    """Conservative overlap gate: ambiguous same-priority scheme targets need resolution."""
    for index, left in enumerate(rules):
        for right in rules[index + 1:]:
            a, b = left.contract, right.contract
            if a.priority != b.priority or not set(a.scope.jurisdiction_ids) & set(b.scope.jurisdiction_ids):
                continue
            if (a.effective_to and a.effective_to < b.effective_from) or (b.effective_to and b.effective_to < a.effective_from):
                continue
            disjoint = any(x and y and not set(x) & set(y) for x, y in (
                (a.scope.industry_codes, b.scope.industry_codes),
                (a.scope.scenario_codes, b.scope.scenario_codes),
                (a.scope.product_codes, b.scope.product_codes),
                (a.scope.data_category_codes, b.scope.data_category_codes)))
            if disjoint:
                continue
            for x in a.actions:
                for y in b.actions:
                    if x.scheme_version_id == y.scheme_version_id and x != y:
                        raise RuleValidationError("ambiguous same-priority classification rules")


class SafeRuleEngine:
    def evaluate(self, rules: tuple[ComplianceRule, ...], facts: RuleFactContext,
                 *, pinned_versions: frozenset[UUID], historical: bool = False) -> tuple[RuleHit, ...]:
        selected = []
        for rule in rules:
            if rule.tenant_id != facts.tenant_id:
                raise LookupError("rule not found")
            if rule.rule_version_id not in pinned_versions:
                raise RuleValidationError("rule version is not snapshot pinned")
            allowed = {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"} if historical else {"ACTIVE"}
            if rule.lifecycle not in allowed or not rule.approved_by or not rule.published_by:
                raise RuleValidationError("rule has no approved publication")
            c = rule.contract
            if facts.as_of < c.effective_from or (c.effective_to and facts.as_of > c.effective_to):
                continue
            if facts.jurisdiction_id not in c.scope.jurisdiction_ids:
                continue
            if any(required and not set(required) & set(actual) for required, actual in (
                (c.scope.industry_codes, facts.industry_codes),
                (c.scope.scenario_codes, facts.scenario_codes),
                (c.scope.product_codes, facts.product_codes),
                (c.scope.data_category_codes, facts.data_category_codes))):
                continue
            selected.append(rule)
        validate_conflicts(tuple(selected))
        hits = []
        for rule in sorted(selected, key=lambda r: (-r.contract.priority, str(r.rule_version_id))):
            c = rule.contract
            ast = parse_ast(c.conditions, c.fields)
            if any(not facts.fact_refs.get(key) for key in ast.referenced_fields if key in facts.values):
                raise RuleValidationError("formal facts require source references")
            match = evaluate(ast, {key: value for key, value in facts.values.items() if key in c.fields})
            hits.append(RuleHit(
                rule_id=rule.rule_id, rule_version_id=rule.rule_version_id,
                tenant_id=facts.tenant_id, project_id=facts.project_id,
                data_item_id=facts.data_item_id, analysis_snapshot_id=facts.analysis_snapshot_id,
                context_version=facts.context_version, matched=match,
                triggered_actions=c.actions if match else (), severity=c.severity if match else None,
                priority=c.priority, legal_basis_ids=c.legal_basis_ids,
                evidence_requirement=c.evidence_required if match else (), evidence_ids=facts.evidence_ids,
                matched_fact_refs=tuple(sorted({ref for key in ast.referenced_fields
                    for ref in facts.fact_refs.get(key, ())}, key=str)) if match else (),
                reason_code="RULE_MATCH" if match else "RULE_NOT_MATCHED",
                review_required=facts.review_required or not set(c.evidence_required) <= set(facts.evidence_types)))
        return tuple(hits)
