"""Formal, scheme-specific decisions backed by rule hits and authorized evidence."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from crossborder_compliance.domain.rules import Contract, RuleFactContext, RuleHit


class ClassificationCategory(Contract):
    category_id: UUID
    code: str


class ClassificationLevel(Contract):
    level_id: UUID
    code: str
    rank: int


class ClassificationScheme(Contract):
    scheme_id: UUID
    scheme_version_id: UUID
    tenant_id: UUID
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1)
    version: int = Field(ge=1)
    categories: tuple[ClassificationCategory, ...]
    levels: tuple[ClassificationLevel, ...]
    lifecycle: str


class ClassificationResult(Contract):
    classification_result_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    project_id: UUID
    data_item_id: UUID
    jurisdiction_id: UUID
    scheme_id: UUID
    scheme_version_id: UUID
    category_ids: tuple[UUID, ...]
    level_id: UUID | None
    rule_hit_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    source_fact_refs: tuple[UUID, ...] = Field(min_length=1)
    reason_codes: tuple[str, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    review_required: bool
    status: Literal["CLASSIFIED", "REVIEW_REQUIRED"]
    record_version: int = Field(default=1, ge=1)
    analysis_snapshot_id: UUID
    context_version: int = Field(ge=1)
    generated_by: Literal["SAFE_RULE_ENGINE_V1"] = "SAFE_RULE_ENGINE_V1"

    @model_validator(mode="after")
    def target(self):
        if not self.category_ids and self.level_id is None:
            raise ValueError("formal classification requires a classification target")
        return self


class ClassificationOutcome(Contract):
    status: Literal["CLASSIFIED", "REVIEW_REQUIRED", "NOT_APPLICABLE", "INSUFFICIENT_INPUT"]
    reason_codes: tuple[str, ...]
    result: ClassificationResult | None = None
    rule_hits: tuple[RuleHit, ...] = ()


class ClassificationPolicy(Contract):
    no_data: Literal["NOT_APPLICABLE", "INSUFFICIENT_INPUT"] = "NOT_APPLICABLE"


def classify(scheme: ClassificationScheme, facts: RuleFactContext, hits: tuple[RuleHit, ...]) -> ClassificationOutcome:
    if scheme.tenant_id != facts.tenant_id or facts.jurisdiction_id not in scheme.jurisdiction_ids:
        raise LookupError("scheme not found")
    matches = []
    for hit in hits:
        if (hit.tenant_id, hit.project_id, hit.analysis_snapshot_id, hit.data_item_id, hit.context_version) != (
            facts.tenant_id, facts.project_id, facts.analysis_snapshot_id, facts.data_item_id, facts.context_version):
            raise LookupError("rule hit not found")
        for action in hit.triggered_actions:
            if hit.matched and action.scheme_version_id == scheme.scheme_version_id:
                if not set(action.category_ids) <= {c.category_id for c in scheme.categories}:
                    raise ValueError("rule action category outside scheme")
                if action.level_id and action.level_id not in {v.level_id for v in scheme.levels}:
                    raise ValueError("rule action level outside scheme")
                matches.append((hit, action))
    if not facts.data_item_id or not matches or not facts.evidence_ids:
        return ClassificationOutcome(status="INSUFFICIENT_INPUT", reason_codes=("MISSING_DATA_RULE_OR_EVIDENCE",), rule_hits=hits)
    # All matching provenance is retained. Priority resolves competing levels explicitly.
    top = max(h.priority for h, _ in matches)
    levels = {a.level_id for h, a in matches if h.priority == top and a.level_id}
    if len(levels) > 1:
        return ClassificationOutcome(status="REVIEW_REQUIRED", reason_codes=("CLASSIFICATION_CONFLICT",), rule_hits=hits)
    refs = tuple(sorted({ref for h, _ in matches for ref in h.matched_fact_refs}, key=str))
    if not refs or any(not set(h.evidence_requirement) <= set(facts.evidence_types) for h, _ in matches):
        return ClassificationOutcome(status="INSUFFICIENT_INPUT", reason_codes=("MISSING_VERIFIED_FACT_OR_EVIDENCE",), rule_hits=hits)
    review = facts.review_required or any(h.review_required for h, _ in matches)
    result = ClassificationResult(
        tenant_id=facts.tenant_id, project_id=facts.project_id, data_item_id=facts.data_item_id,
        jurisdiction_id=facts.jurisdiction_id, scheme_id=scheme.scheme_id,
        scheme_version_id=scheme.scheme_version_id,
        category_ids=tuple(sorted({c for _, a in matches for c in a.category_ids}, key=str)),
        level_id=next(iter(levels), None), rule_hit_ids=tuple(dict.fromkeys(h.rule_hit_id for h, _ in matches)),
        evidence_ids=facts.evidence_ids, source_fact_refs=refs,
        reason_codes=tuple(dict.fromkeys(a.reason_code for _, a in matches)),
        confidence=facts.confidence, review_required=review,
        status="REVIEW_REQUIRED" if review else "CLASSIFIED",
        analysis_snapshot_id=facts.analysis_snapshot_id, context_version=facts.context_version)
    return ClassificationOutcome(status=result.status, reason_codes=result.reason_codes, result=result, rule_hits=hits)
