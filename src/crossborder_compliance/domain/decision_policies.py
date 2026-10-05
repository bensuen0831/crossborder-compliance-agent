"""Typed policy payloads in the existing MetadataVersion authority and Rule AST."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.compliance_profiles import EffectiveConfig
from crossborder_compliance.domain.contracts import RiskLevel
from crossborder_compliance.domain.decision_contracts import FactValue, Score, UnitDecimal
from crossborder_compliance.domain.localized_metadata import StableDisplayCode, StableMetadataCode
from crossborder_compliance.domain.rule_ast import (
    FieldType,
    MissingRuleFact,
    evaluate,
    parse_ast,
    typed_value,
)
from crossborder_compliance.domain.rules import Contract


class PolicyFact(Contract):
    code: StableMetadataCode
    field_type: FieldType


class TestFact(Contract):
    code: StableMetadataCode
    value: FactValue


class PredicateExample(Contract):
    facts: tuple[TestFact, ...]
    expected: Literal["TRUE", "FALSE", "UNKNOWN"]


class ConditionPolicy(Contract):
    entry_id: UUID
    code: StableDisplayCode
    fields: tuple[PolicyFact, ...] = Field(min_length=1)
    predicate: str
    required_evidence: bool = True
    examples: tuple[PredicateExample, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ast(self):
        schema = {v.code: v.field_type for v in self.fields}
        if len(schema) != len(self.fields):
            raise ValueError("duplicate predicate field")
        ast = parse_ast(self.predicate, schema)
        for example in self.examples:
            values = {
                f.code: typed_value(f.value, schema[f.code], literal=True) for f in example.facts
            }
            try:
                actual = "TRUE" if evaluate(ast, values) else "FALSE"
            except MissingRuleFact:
                actual = "UNKNOWN"
            if actual != example.expected:
                raise ValueError("persisted predicate example failed")
        return self


class ObligationEntry(Contract):
    entry_id: UUID
    code: StableDisplayCode
    jurisdiction_id: UUID
    applicability_config_id: UUID
    required_rule_ids: tuple[UUID, ...] = Field(min_length=1)
    legal_basis_ids: tuple[UUID, ...] = Field(min_length=1)
    legal_effect_code: Literal["REQUIREMENT", "TRANSFER_PROHIBITED", "LOCALIZATION_REQUIRED"] = (
        "REQUIREMENT"
    )
    applicability_conditions: tuple[ConditionPolicy, ...] = ()
    fulfillment_conditions: tuple[ConditionPolicy, ...] = ()
    responsible_party_ids: tuple[UUID, ...] = ()


class DecisionPolicy(EffectiveConfig):
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1)
    permission_scopes: tuple[str, ...] = ()


class ObligationPolicy(DecisionPolicy):
    entries: tuple[ObligationEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def scope(self):
        if len({e.entry_id for e in self.entries}) != len(self.entries):
            raise ValueError("duplicate obligation entry")
        if any(e.jurisdiction_id not in self.jurisdiction_ids for e in self.entries):
            raise ValueError("obligation outside policy jurisdiction")
        if {e.jurisdiction_id for e in self.entries} != set(self.jurisdiction_ids):
            raise ValueError("obligation policy jurisdiction coverage incomplete")
        return self


class ActionPolicy(Contract):
    entry_id: UUID
    code: StableDisplayCode
    sequence: int = Field(ge=1)
    conditions: tuple[ConditionPolicy, ...] = ()
    dependency_entry_ids: tuple[UUID, ...] = ()
    responsible_party_ids: tuple[UUID, ...] = ()


class PathTemplate(Contract):
    entry_id: UUID
    path_code: StableDisplayCode
    obligation_entry_ids: tuple[UUID, ...] = Field(min_length=1)
    mechanism_entry_ids: tuple[UUID, ...] = ()
    capability_ids: tuple[UUID, ...] = ()
    prerequisites: tuple[ConditionPolicy, ...] = ()
    actions: tuple[ActionPolicy, ...] = ()
    priority: int = 0
    prohibiting_obligation_entry_ids: tuple[UUID, ...] | None = None

    @model_validator(mode="after")
    def action_order(self):
        ids = {a.entry_id for a in self.actions}
        if len(ids) != len(self.actions) or len({a.sequence for a in self.actions}) != len(
            self.actions
        ):
            raise ValueError("duplicate action identity/order")
        seen = set()
        for a in sorted(self.actions, key=lambda a: a.sequence):
            if not set(a.dependency_entry_ids) <= seen:
                raise ValueError("action dependency must precede action")
            seen.add(a.entry_id)
        return self


class CompliancePathPolicy(DecisionPolicy):
    obligation_policy_id: UUID
    templates: tuple[PathTemplate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_templates(self):
        if len({t.entry_id for t in self.templates}) != len(self.templates) or len(
            {t.path_code for t in self.templates}
        ) != len(self.templates):
            raise ValueError("duplicate path template")
        return self


class ScoreRange(Contract):
    lower: Decimal
    upper: Decimal
    score: Score

    @model_validator(mode="after")
    def interval(self):
        if not self.lower.is_finite() or not self.upper.is_finite() or self.upper <= self.lower:
            raise ValueError("invalid factor range")
        return self


class RiskFactorPolicy(Contract):
    code: StableDisplayCode
    observation_code: StableMetadataCode
    weight: UnitDecimal
    required: bool = True
    exclude_when_missing: bool = False
    score_ranges: tuple[ScoreRange, ...] = ()

    @model_validator(mode="after")
    def optional_exclusion(self):
        if self.required and self.exclude_when_missing:
            raise ValueError("required factor cannot be excluded")
        ranges = sorted(self.score_ranges, key=lambda v: v.lower)
        if any(a.upper != b.lower for a, b in zip(ranges, ranges[1:])):
            raise ValueError("factor ranges must be contiguous and nonoverlapping")
        return self


class RiskDimensionPolicy(Contract):
    code: StableDisplayCode
    weight: UnitDecimal
    factors: tuple[RiskFactorPolicy, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def weights(self):
        if sum((f.weight for f in self.factors), Decimal(0)) != 1 or len(
            {f.code for f in self.factors}
        ) != len(self.factors):
            raise ValueError("factor weights must sum exactly1 and codes be unique")
        return self


class RiskBand(Contract):
    lower: Score
    upper: Score
    band: RiskLevel


class RiskBandRow(Contract):
    conditions: tuple[ConditionPolicy, ...] = Field(min_length=1)
    band: RiskLevel


class RiskExample(Contract):
    facts: tuple[TestFact, ...]
    expected_score: Score | None
    expected_band: RiskLevel


class RiskPolicy(DecisionPolicy):
    mode: Literal["WEIGHTED", "BAND_ONLY"]
    dimensions: tuple[RiskDimensionPolicy, ...] = ()
    bands: tuple[RiskBand, ...] = ()
    band_rows: tuple[RiskBandRow, ...] = ()
    decimal_scale: int = Field(default=2, ge=0, le=8)
    rounding: Literal["ROUND_HALF_EVEN", "ROUND_HALF_UP", "ROUND_DOWN"] = "ROUND_HALF_EVEN"
    examples: tuple[RiskExample, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_policy(self):
        if self.mode == "WEIGHTED":
            if (
                not self.dimensions
                or self.band_rows
                or sum((d.weight for d in self.dimensions), Decimal(0)) != 1
            ):
                raise ValueError("weighted dimensions must sum exactly1")
            if len({d.code for d in self.dimensions}) != len(self.dimensions):
                raise ValueError("duplicate risk dimension")
            bands = sorted(self.bands, key=lambda b: b.lower)
            if (
                not bands
                or bands[0].lower != 0
                or bands[-1].upper != 100
                or any(b.lower >= b.upper or b.band == RiskLevel.UNKNOWN for b in bands)
                or any(a.upper != b.lower for a, b in zip(bands, bands[1:]))
            ):
                raise ValueError("bands must exhaust0–100 without gaps/overlaps")
        elif not self.band_rows or self.dimensions or self.bands:
            raise ValueError("band-only mode requires a finite decision table only")
        from crossborder_compliance.domain.decision_risk import evaluate_policy_values

        for ex in self.examples:
            score, band, _ = evaluate_policy_values(self, {f.code: f.value for f in ex.facts})
            if (score, band) != (ex.expected_score, ex.expected_band):
                raise ValueError("persisted risk example failed")
        return self


class RankingCriterion(Contract):
    kind: Literal["RISK_SCORE", "RISK_BAND", "TEMPLATE_PRIORITY"]
    direction: Literal["ASC", "DESC"]


class RecommendationPolicy(DecisionPolicy):
    path_policy_id: UUID
    risk_policy_id: UUID
    criteria: tuple[RankingCriterion, ...] = Field(min_length=1)
    review_bands: tuple[RiskLevel, ...] = ()

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.kind for c in self.criteria}) != len(self.criteria):
            raise ValueError("duplicate ranking criterion")
        return self


POLICY_TYPES = {
    "OBLIGATION_POLICY": ObligationPolicy,
    "COMPLIANCE_PATH_POLICY": CompliancePathPolicy,
    "RISK_POLICY": RiskPolicy,
    "RECOMMENDATION_POLICY": RecommendationPolicy,
}
PHASE1J_POLICY_KINDS = frozenset(POLICY_TYPES)
