"""Pure formal decisions in frozen semantic order; no infrastructure or model provider."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from crossborder_compliance.domain.contracts import RiskLevel
from crossborder_compliance.domain.decision_contracts import (
    ENVELOPE_TYPES,
    Action,
    CandidateCompliancePathDTOv2,
    CapabilityDependency,
    ComplianceObligationDTOv2,
    ComplianceRecommendationDTOv2,
    Condition,
    DecisionProvenance,
    ExcludedCandidate,
    FactValue,
    FinalCompliancePathDTOv2,
    LegalSupport,
    PinRef,
    RankingOutcome,
    RiskAssessmentDTOv2,
    StageRef,
    digest,
    result_digest,
    unique,
)
from crossborder_compliance.domain.decision_policies import (
    POLICY_TYPES,
    CompliancePathPolicy,
    ObligationPolicy,
    RecommendationPolicy,
    RiskPolicy,
)
from crossborder_compliance.domain.decision_risk import evaluate_policy_values
from crossborder_compliance.domain.localized_metadata import StableMetadataCode
from crossborder_compliance.domain.regulation_applicability import RegulationApplicabilityResult
from crossborder_compliance.domain.rule_ast import (
    RuleValidationError,
    evaluate,
    parse_ast,
    typed_value,
)
from crossborder_compliance.domain.rules import Contract, RuleHit


class DecisionIdentity(Contract):
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    project_version_id: UUID
    context_version: int = Field(ge=1)
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    data_item_ids: tuple[UUID, ...] = ()
    data_flow_ids: tuple[UUID, ...] = ()
    scenario_definition_ids: tuple[UUID, ...] = ()
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1)
    analysis_as_of_date: date


class AuthorizedFact(Contract):
    code: StableMetadataCode
    value: FactValue
    fact_refs: tuple[UUID, ...] = Field(min_length=1)
    evidence_ids: tuple[UUID, ...]


class PinnedDecisionPolicy(Contract):
    pin: PinRef
    config: ObligationPolicy | CompliancePathPolicy | RiskPolicy | RecommendationPolicy

    @model_validator(mode="after")
    def kind(self):
        if (
            self.pin.kind not in POLICY_TYPES
            or type(self.config) is not POLICY_TYPES[self.pin.kind]
        ):
            raise ValueError("policy pin kind mismatch")
        return self


class PreparedDecisionInput(Contract):
    identity: DecisionIdentity
    applicability: tuple[RegulationApplicabilityResult, ...]
    rule_hits: tuple[RuleHit, ...]
    facts: tuple[AuthorizedFact, ...]
    authorized_evidence_ids: tuple[UUID, ...]
    support: LegalSupport
    policies: tuple[PinnedDecisionPolicy, ...]
    pins: tuple[PinRef, ...]
    capabilities: tuple[CapabilityDependency, ...]
    prepared_at: datetime
    actor_ref: str
    request_id: str
    correlation_id: str

    @model_validator(mode="after")
    def scope(self):
        i = self.identity
        for a in self.applicability:
            if (
                a.tenant_id,
                a.project_id,
                a.analysis_snapshot_id,
                a.subject_type,
                a.subject_id,
                a.context_version,
                a.analysis_as_of_date,
            ) != (
                i.tenant_id,
                i.project_id,
                i.analysis_snapshot_id,
                i.subject_type,
                i.subject_id,
                i.context_version,
                i.analysis_as_of_date,
            ):
                raise ValueError("applicability scope mismatch")
            if a.jurisdiction_id not in i.jurisdiction_ids:
                raise ValueError("applicability jurisdiction mismatch")
        for h in self.rule_hits:
            if (h.tenant_id, h.project_id, h.analysis_snapshot_id, h.context_version) != (
                i.tenant_id,
                i.project_id,
                i.analysis_snapshot_id,
                i.context_version,
            ):
                raise ValueError("RuleHit scope mismatch")
            if h.data_item_id and h.data_item_id not in i.data_item_ids:
                raise ValueError("RuleHit subject mismatch")
        if any(not set(f.evidence_ids) <= set(self.authorized_evidence_ids) for f in self.facts):
            raise ValueError("fact evidence outside authorized inputs")
        if not set(self.support.evidence_ids) <= set(self.authorized_evidence_ids):
            raise ValueError("support evidence outside authorized inputs")
        if len({f.code for f in self.facts}) != len(self.facts):
            raise ValueError("ambiguous fact key")
        if any(p.pin not in self.pins for p in self.policies):
            raise ValueError("unbound policy")
        return self

    def policy(self, kind):
        matches = [p for p in self.policies if p.pin.kind == kind]
        return matches[0] if len(matches) == 1 else None


def input_digest(inputs):
    data = inputs.model_dump(mode="python")
    for key in ("prepared_at", "actor_ref", "request_id", "correlation_id"):
        data.pop(key)
    # Existing presentation payloads do not participate in formal decision semantics.
    for policy in data["policies"]:
        policy["config"].pop("localized_display", None)
        policy["config"].pop("localized_code_labels", None)
    data["facts"] = sorted(data["facts"], key=lambda f: f["code"])
    for key in ("pins", "policies", "capabilities", "applicability", "rule_hits"):
        data[key] = sorted(data[key], key=digest)
    return digest(data)


def ref(envelope):
    return StageRef(
        kind=envelope.stage_kind,
        result_id=envelope.result_id,
        content_digest=result_digest(envelope),
    )


def merge_support(supports):
    return LegalSupport(
        **{
            key: unique(v for s in supports for v in getattr(s, key))
            for key in LegalSupport.model_fields
        }
    )


def condition_result(policy, inputs):
    schema = {f.code: f.field_type for f in policy.fields}
    ast = parse_ast(policy.predicate, schema)
    chosen = [f for f in inputs.facts if f.code in ast.referenced_fields]
    try:
        values = {f.code: typed_value(f.value, schema[f.code], literal=True) for f in chosen}
        state = "TRUE" if evaluate(ast, values) else "FALSE"
    except RuleValidationError:
        state = "UNKNOWN"
    evidence = unique(e for f in chosen for e in f.evidence_ids)
    if policy.required_evidence and not evidence:
        state = "UNKNOWN"
    return Condition(
        entry_id=policy.entry_id,
        code=policy.code,
        predicate_digest=digest(policy.predicate),
        evaluation=state,
        fact_refs=unique(r for f in chosen for r in f.fact_refs),
        evidence_ids=evidence,
    )


def _envelope(
    stage, inputs, items, parents=(), ordinary="UNDETERMINED", missing=False, conflict=False
):
    identity = inputs.identity.model_dump(mode="python")
    for parent in parents:
        if any(getattr(parent, key) != value for key, value in identity.items()):
            raise ValueError("upstream decision scope mismatch")
        if set(parent.pins) != set(inputs.pins):
            raise ValueError("upstream decision pin mismatch")
    policy_kind = {
        "OBLIGATION": "OBLIGATION_POLICY",
        "CANDIDATE_PATH": "COMPLIANCE_PATH_POLICY",
        "RISK": "RISK_POLICY",
        "RECOMMENDATION": "RECOMMENDATION_POLICY",
        "FINAL_PATH": "RECOMMENDATION_POLICY",
    }[stage]
    policy = inputs.policy(policy_kind)
    missing = (
        missing
        or policy is None
        or not set(inputs.identity.jurisdiction_ids) <= set(policy.config.jurisdiction_ids)
    )
    coverage = set(inputs.identity.jurisdiction_ids) <= {
        a.jurisdiction_id for a in inputs.applicability
    }
    bad_app = any(
        a.applicability_status in {"INSUFFICIENT_EVIDENCE", "CONFLICTED", "REVIEW_REQUIRED"}
        for a in inputs.applicability
    )
    insufficient = (
        missing
        or not coverage
        or any(a.applicability_status == "INSUFFICIENT_EVIDENCE" for a in inputs.applicability)
        or any(p.input_sufficiency != "SUFFICIENT" for p in parents)
    )
    conflict = (
        conflict
        or any(
            a.conflict_status == "CONFLICTED" or a.applicability_status == "CONFLICTED"
            for a in inputs.applicability
        )
        or any(p.conflict_state == "CONFLICTED" for p in parents)
    )
    review = (
        insufficient
        or conflict
        or bad_app
        or any(a.review_required for a in inputs.applicability)
        or any(i.review_required for i in items)
        or any(p.review_required for p in parents)
    )
    kinds = [p.pin.kind for p in inputs.policies]
    conflict = conflict or len(set(kinds)) != len(kinds)
    review = review or conflict
    sources = (
        tuple(sorted((ref(p) for p in parents), key=lambda r: str(r.result_id)))
        if parents
        else tuple(
            sorted(
                (
                    StageRef(
                        kind="APPLICABILITY",
                        result_id=a.applicability_result_id,
                        content_digest=digest(a),
                    )
                    for a in inputs.applicability
                ),
                key=lambda r: str(r.result_id),
            )
        )
    )
    pins = tuple(sorted(inputs.pins, key=lambda p: (p.kind, str(p.object_id))))
    signature = digest({"stage": stage, "input": input_digest(inputs), "parents": sources})
    reasons = [ordinary]
    if insufficient:
        reasons.append("INSUFFICIENT_EVIDENCE")
    if not coverage:
        reasons.append("JURISDICTION_COVERAGE_INCOMPLETE")
    if conflict:
        reasons.append("CONFLICTED")
    if review:
        reasons.append("REVIEW_REQUIRED")
    origins = unique((*sources, *(o for p in parents for o in p.provenance.origins)))
    provenance = DecisionProvenance(
        origins=origins,
        context_fact_refs=inputs.support.fact_refs,
        retrieval_run_ids=inputs.support.retrieval_run_ids,
        pins=pins,
        computation_timestamp=inputs.prepared_at,
        actor_ref=inputs.actor_ref,
        request_id=inputs.request_id,
        correlation_id=inputs.correlation_id,
    )
    confidence = (
        Decimal(0)
        if insufficient or conflict
        else min((Decimal(str(a.confidence)) for a in inputs.applicability), default=Decimal(0))
    )
    return ENVELOPE_TYPES[stage](
        result_id=uuid5(NAMESPACE_URL, signature),
        stage_kind=stage,
        **inputs.identity.model_dump(),
        upstream_refs=sources,
        items=tuple(items),
        input_sufficiency="INSUFFICIENT_EVIDENCE" if insufficient else "SUFFICIENT",
        conflict_state="CONFLICTED" if conflict else "CLEAR",
        review_required=review,
        reason_codes=unique(reasons),
        confidence=confidence,
        pins=pins,
        input_digest=signature,
        pins_digest=digest(pins),
        provenance=provenance,
        ordinary_status=ordinary,
    )


def obligations(inputs):
    policy = inputs.policy("OBLIGATION_POLICY")
    if policy is None:
        return _envelope("OBLIGATION", inputs, (), missing=True)
    items = []
    missing = any(
        a.applicability_status in {"APPLICABLE", "CONDITIONALLY_APPLICABLE"}
        and a.applicability_config_id
        not in {e.applicability_config_id for e in policy.config.entries}
        for a in inputs.applicability
    )
    conflict = False
    for entry in policy.config.entries:
        apps = [
            a
            for a in inputs.applicability
            if a.jurisdiction_id == entry.jurisdiction_id
            and a.applicability_config_id == entry.applicability_config_id
        ]
        hits = [h for h in inputs.rule_hits if h.rule_id in entry.required_rule_ids]
        groups = {r: {h.matched for h in hits if h.rule_id == r} for r in entry.required_rule_ids}
        contradictory = any(len(g) > 1 for g in groups.values())
        conflict = conflict or contradictory
        conditions = tuple(condition_result(c, inputs) for c in entry.applicability_conditions)
        fulfilled = tuple(condition_result(c, inputs) for c in entry.fulfillment_conditions)
        legal = "UNDETERMINED"
        if len(apps) == 1:
            app = apps[0]
            if app.applicability_status == "NOT_APPLICABLE":
                legal = "NOT_APPLICABLE"
            elif (
                app.applicability_status in {"APPLICABLE", "CONDITIONALLY_APPLICABLE"}
                and not contradictory
                and all(groups.values())
            ):
                if any(False in g for g in groups.values()) or any(
                    c.evaluation == "FALSE" for c in conditions
                ):
                    legal = "NOT_APPLICABLE"
                elif any(c.evaluation == "UNKNOWN" for c in conditions):
                    legal = "UNDETERMINED"
                elif (
                    set(entry.legal_basis_ids) <= set(app.legal_basis_ids)
                    and set(app.evidence_ids) <= set(inputs.authorized_evidence_ids)
                    and app.evidence_ids
                ):
                    legal = (
                        "CONDITIONAL"
                        if app.applicability_status == "CONDITIONALLY_APPLICABLE"
                        else "REQUIRED"
                    )
        missing = missing or legal == "UNDETERMINED"
        support = merge_support(
            (
                inputs.support,
                LegalSupport(
                    applicability_result_ids=unique(a.applicability_result_id for a in apps),
                    rule_hit_ids=unique(h.rule_hit_id for h in hits if h.matched),
                    rule_version_ids=unique(h.rule_version_id for h in hits if h.matched),
                    legal_basis_ids=entry.legal_basis_ids,
                ),
            )
        )
        if legal in {"UNDETERMINED", "NOT_APPLICABLE"}:
            # Do not assert unsupported legal basis as the source of a positive obligation.
            support = support.model_copy(
                update={"legal_basis_ids": unique(b for a in apps for b in a.legal_basis_ids)}
            )
        fulfillment = "NOT_APPLICABLE" if legal == "NOT_APPLICABLE" else "UNKNOWN"
        if legal in {"REQUIRED", "CONDITIONAL"} and fulfilled:
            fulfillment = (
                "UNKNOWN"
                if any(c.evaluation == "UNKNOWN" for c in fulfilled)
                else "UNMET"
                if any(c.evaluation == "FALSE" for c in fulfilled)
                else "SATISFIED"
            )
        items.append(
            ComplianceObligationDTOv2(
                obligation_id=uuid5(
                    policy.pin.version_id, str(entry.entry_id) + input_digest(inputs)
                ),
                requirement_id=entry.entry_id,
                obligation_code=entry.code,
                jurisdiction_ids=(entry.jurisdiction_id,),
                support=support,
                reason_codes=("FORMAL_OBLIGATION_" + legal,),
                review_required=legal == "UNDETERMINED" or contradictory,
                policy_version_ref=policy.pin.version_id,
                legal_effect=legal,
                fulfillment_state=fulfillment,
                conditions=conditions + fulfilled,
                responsible_party_ids=entry.responsible_party_ids,
                legal_effect_code=entry.legal_effect_code,
            )
        )
    status = (
        "NOT_APPLICABLE"
        if items and all(i.legal_effect == "NOT_APPLICABLE" for i in items)
        else "OBLIGATIONS_IDENTIFIED"
    )
    return _envelope(
        "OBLIGATION",
        inputs,
        sorted(items, key=lambda i: str(i.requirement_id)),
        ordinary=status,
        missing=missing,
        conflict=conflict,
    )


def candidates(inputs, obligation):
    policy = inputs.policy("COMPLIANCE_PATH_POLICY")
    if policy is None:
        return _envelope("CANDIDATE_PATH", inputs, (), (obligation,), missing=True)
    by_entry = {o.requirement_id: o for o in obligation.items}
    caps = {c.capability_id: c for c in inputs.capabilities}
    items = []
    for template in sorted(policy.config.templates, key=lambda t: t.path_code):
        covered = [by_entry[e] for e in template.obligation_entry_ids if e in by_entry]
        required = [o for o in obligation.items if o.legal_effect in {"REQUIRED", "CONDITIONAL"}]
        all_covered = {o.obligation_id for o in required} <= {o.obligation_id for o in covered}
        prerequisites = tuple(condition_result(c, inputs) for c in template.prerequisites)
        legal = "VIABLE"
        restrictions = template.prohibiting_obligation_entry_ids
        if any(
            o.legal_effect == "REQUIRED"
            and o.legal_effect_code == "TRANSFER_PROHIBITED"
            and (restrictions is None or o.requirement_id in restrictions)
            for o in covered
        ):
            legal = "LEGALLY_PROHIBITED"
        elif (
            obligation.summary_status in {"CONFLICTED", "INSUFFICIENT_EVIDENCE", "REVIEW_REQUIRED"}
            or len(covered) != len(template.obligation_entry_ids)
            or any(o.legal_effect == "UNDETERMINED" for o in covered)
            or any(c.evaluation == "UNKNOWN" for c in prerequisites)
        ):
            legal = "UNDETERMINED"
        elif (
            not all_covered
            or any(o.legal_effect == "CONDITIONAL" for o in covered)
            or any(c.evaluation == "FALSE" for c in prerequisites)
        ):
            legal = "CONDITIONAL"
        dependencies = tuple(
            caps.get(
                i,
                CapabilityDependency(
                    capability_id=i, version_id=None, availability="CAPABILITY_NOT_CONFIGURED"
                ),
            )
            for i in template.capability_ids
        )
        availability = "AVAILABLE"
        for state in ("UNKNOWN", "UNAVAILABLE", "CAPABILITY_NOT_CONFIGURED"):
            if any(c.availability == state for c in dependencies):
                availability = state
                break
        steps = tuple(
            Action(
                entry_id=a.entry_id,
                action_code=a.code,
                sequence=a.sequence,
                responsible_party_ids=a.responsible_party_ids,
                conditions=tuple(condition_result(c, inputs) for c in a.conditions),
                dependency_entry_ids=a.dependency_entry_ids,
                obligation_ids=unique(o.obligation_id for o in covered),
            )
            for a in sorted(template.actions, key=lambda a: a.sequence)
        )
        if legal != "LEGALLY_PROHIBITED":
            states = [c.evaluation for a in steps for c in a.conditions]
            if "UNKNOWN" in states:
                legal = "UNDETERMINED"
            elif "FALSE" in states and legal == "VIABLE":
                legal = "CONDITIONAL"
        items.append(
            CandidateCompliancePathDTOv2(
                candidate_path_id=uuid5(
                    policy.pin.version_id, template.path_code + obligation.input_digest
                ),
                path_code=template.path_code,
                template_entry_id=template.entry_id,
                jurisdiction_ids=policy.config.jurisdiction_ids,
                support=merge_support(o.support for o in covered),
                reason_codes=("FORMAL_PATH_" + legal, availability),
                review_required=legal == "UNDETERMINED",
                policy_version_ref=policy.pin.version_id,
                obligation_ids=unique(o.obligation_id for o in covered),
                prerequisites=prerequisites,
                unmet_requirement_ids=unique(
                    o.requirement_id for o in required if o.fulfillment_state != "SATISFIED"
                ),
                mechanism_entry_ids=template.mechanism_entry_ids,
                capability_dependencies=dependencies,
                legal_viability=legal,
                operational_availability=availability,
                steps=steps,
                template_priority=template.priority,
            )
        )
    status = (
        "NOT_APPLICABLE"
        if obligation.ordinary_status == "NOT_APPLICABLE"
        else "CANDIDATES_IDENTIFIED"
        if any(i.legal_viability in {"VIABLE", "CONDITIONAL"} for i in items)
        else "NO_VIABLE_PATH"
    )
    return _envelope(
        "CANDIDATE_PATH",
        inputs,
        items,
        (obligation,),
        ordinary=status,
        missing=any(i.legal_viability == "UNDETERMINED" for i in items),
    )


def risks(inputs, candidate):
    policy = inputs.policy("RISK_POLICY")
    if policy is None:
        return _envelope("RISK", inputs, (), (candidate,), missing=True)
    facts = {f.code: f.value for f in inputs.facts}
    refs = {f.code: f.fact_refs for f in inputs.facts}
    score, band, dimensions = evaluate_policy_values(
        policy.config, facts, refs, inputs.authorized_evidence_ids
    )
    band_conditions = (
        tuple(
            condition_result(c, inputs) for row in policy.config.band_rows for c in row.conditions
        )
        if policy.config.mode == "BAND_ONLY"
        else ()
    )
    if any(c.evaluation == "UNKNOWN" for c in band_conditions):
        score, band = None, RiskLevel.UNKNOWN
    factors = [f for d in dimensions for f in d.factors]
    coverage = (
        Decimal(sum(f.score is not None for f in factors)) / Decimal(len(factors))
        if factors
        else Decimal(1)
        if band != RiskLevel.UNKNOWN
        else Decimal(0)
    )
    items = [
        RiskAssessmentDTOv2(
            risk_assessment_id=uuid5(policy.pin.version_id, str(c.candidate_path_id)),
            candidate_path_id=c.candidate_path_id,
            jurisdiction_ids=c.jurisdiction_ids,
            support=c.support,
            reason_codes=("FORMAL_RISK_" + band.value,),
            review_required=band == RiskLevel.UNKNOWN,
            policy_version_ref=policy.pin.version_id,
            dimensions=dimensions,
            band_conditions=band_conditions,
            score=score,
            risk_level=band,
            coverage=coverage,
            input_sufficiency="UNKNOWN" if band == RiskLevel.UNKNOWN else "SUFFICIENT",
            score_mode=policy.config.mode,
            decimal_scale=policy.config.decimal_scale,
            rounding=policy.config.rounding,
        )
        for c in candidate.items
    ]
    return _envelope(
        "RISK",
        inputs,
        items,
        (candidate,),
        ordinary="ASSESSED" if items else "NOT_APPLICABLE",
        missing=bool(items) and band == RiskLevel.UNKNOWN,
    )


def recommendation(inputs, candidate, risk):
    policy = inputs.policy("RECOMMENDATION_POLICY")
    if policy is None:
        return _envelope("RECOMMENDATION", inputs, (), (candidate, risk), missing=True)
    risk_by_candidate = {r.candidate_path_id: r for r in risk.items}
    ranks, excluded, conditional = [], [], []
    bands = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
    eligible = []
    for c in candidate.items:
        if c.legal_viability == "CONDITIONAL":
            conditional.append(c.candidate_path_id)
        if c.legal_viability != "VIABLE" or c.operational_availability != "AVAILABLE":
            excluded.append(
                ExcludedCandidate(
                    candidate_path_id=c.candidate_path_id,
                    reason_codes=(c.legal_viability, c.operational_availability),
                )
            )
            continue
        r = risk_by_candidate.get(c.candidate_path_id)
        if (
            r is None
            or r.input_sufficiency != "SUFFICIENT"
            or r.review_required
            or r.risk_level == RiskLevel.UNKNOWN
            or r.jurisdiction_ids != c.jurisdiction_ids
        ):
            excluded.append(
                ExcludedCandidate(
                    candidate_path_id=c.candidate_path_id, reason_codes=("INCOMPARABLE_RISK",)
                )
            )
            continue
        values = []
        for criterion in policy.config.criteria:
            v = (
                r.score
                if criterion.kind == "RISK_SCORE"
                else Decimal(bands[r.risk_level])
                if criterion.kind == "RISK_BAND"
                else Decimal(c.template_priority)
            )
            if v is None:
                values = None
                break
            values.append(v if criterion.direction == "ASC" else -v)
        if values is None:
            excluded.append(
                ExcludedCandidate(
                    candidate_path_id=c.candidate_path_id, reason_codes=("MISSING_RANKING_INPUT",)
                )
            )
            continue
        eligible.append((c, r))
        ranks.append(
            RankingOutcome(candidate_path_id=c.candidate_path_id, criterion_values=tuple(values))
        )
    comparable = (
        len(
            {
                (r.policy_version_ref, r.score_mode, r.coverage, r.jurisdiction_ids)
                for _, r in eligible
            }
        )
        <= 1
    )
    selected, tied = None, ()
    status = "CONDITIONAL_ALTERNATIVES" if conditional else "NO_RECOMMENDATION"
    review = not comparable
    if (
        ranks
        and comparable
        and candidate.summary_status
        not in {"CONFLICTED", "INSUFFICIENT_EVIDENCE", "REVIEW_REQUIRED"}
        and risk.summary_status not in {"CONFLICTED", "INSUFFICIENT_EVIDENCE", "REVIEW_REQUIRED"}
    ):
        best = min(r.criterion_values for r in ranks)
        tied = unique(r.candidate_path_id for r in ranks if r.criterion_values == best)
        if len(tied) > 1:
            status, review = "TIED", True
        else:
            selected = tied[0]
            tied = ()
            status = "RECOMMENDED"
            if risk_by_candidate[selected].risk_level in policy.config.review_bands:
                status, selected, review = "NO_RECOMMENDATION", None, True
    if candidate.ordinary_status == "NOT_APPLICABLE":
        status, selected = "NOT_APPLICABLE", None
    item = ComplianceRecommendationDTOv2(
        recommendation_id=uuid5(policy.pin.version_id, candidate.input_digest + risk.input_digest),
        jurisdiction_ids=inputs.identity.jurisdiction_ids,
        support=merge_support(c.support for c in candidate.items),
        reason_codes=(status,),
        review_required=review,
        policy_version_ref=policy.pin.version_id,
        status=status,
        selected_candidate_id=selected,
        rankings=tuple(sorted(ranks, key=lambda r: (r.criterion_values, str(r.candidate_path_id)))),
        excluded_candidates=tuple(excluded),
        alternative_candidate_ids=unique(
            c.candidate_path_id for c in candidate.items if c.candidate_path_id != selected
        ),
        tied_candidate_ids=tied,
        risk_assessment_ids=unique(r.risk_assessment_id for r in risk.items),
    )
    return _envelope(
        "RECOMMENDATION",
        inputs,
        (item,),
        (candidate, risk),
        ordinary=status,
        missing=not comparable,
    )


def final_path(inputs, obligation, candidate, risk, recommended):
    policy = inputs.policy("RECOMMENDATION_POLICY")
    if policy is None or not recommended.items:
        return _envelope(
            "FINAL_PATH", inputs, (), (obligation, candidate, risk, recommended), missing=True
        )
    advice = recommended.items[0]
    selected = advice.selected_candidate_id
    unresolved = unique(
        code
        for p in (obligation, candidate, risk, recommended)
        for code in p.reason_codes
        if code in {"CONFLICTED", "INSUFFICIENT_EVIDENCE", "REVIEW_REQUIRED", "TIED"}
    )
    if unresolved:
        selected = None
    chosen = next((c for c in candidate.items if c.candidate_path_id == selected), None)
    residual = next((r for r in risk.items if r.candidate_path_id == selected), None)
    status = (
        "PROPOSED"
        if chosen
        else "NOT_APPLICABLE"
        if obligation.ordinary_status == "NOT_APPLICABLE"
        else "NO_VIABLE_PATH"
        if candidate.ordinary_status == "NO_VIABLE_PATH" and not unresolved
        else "UNDETERMINED"
    )
    if chosen and (
        chosen.unmet_requirement_ids or any(c.evaluation != "TRUE" for c in chosen.prerequisites)
    ):
        status = "CONDITIONAL_PROPOSAL"
    item = FinalCompliancePathDTOv2(
        final_path_id=uuid5(policy.pin.version_id, recommended.input_digest),
        jurisdiction_ids=inputs.identity.jurisdiction_ids,
        support=merge_support(o.support for o in obligation.items),
        reason_codes=(status,),
        review_required=bool(unresolved),
        policy_version_ref=policy.pin.version_id,
        status=status,
        selected_candidate_path_id=selected,
        obligation_ids=unique(
            o.obligation_id
            for o in obligation.items
            if o.legal_effect in {"REQUIRED", "CONDITIONAL"}
        ),
        required_conditions=tuple(c for o in obligation.items for c in o.conditions)
        + (chosen.prerequisites if chosen else ()),
        actions=chosen.steps if chosen else (),
        unmet_requirement_ids=chosen.unmet_requirement_ids
        if chosen
        else unique(
            o.requirement_id for o in obligation.items if o.fulfillment_state != "SATISFIED"
        ),
        residual_risk_ref=ref(risk).model_copy(update={"item_id": residual.risk_assessment_id})
        if residual
        else None,
        alternative_candidate_ids=advice.alternative_candidate_ids,
        unresolved_codes=unresolved,
        review_status="PENDING" if unresolved else "NOT_REQUIRED",
    )
    return _envelope(
        "FINAL_PATH", inputs, (item,), (obligation, candidate, risk, recommended), ordinary=status
    )
