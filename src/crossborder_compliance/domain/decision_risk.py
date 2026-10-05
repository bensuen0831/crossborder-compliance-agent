"""Pure decimal risk calculation. Only authorized typed inputs and governed policy enter."""

from decimal import Decimal, localcontext

from crossborder_compliance.domain.contracts import RiskLevel
from crossborder_compliance.domain.decision_contracts import RiskDimensionResult, RiskFactorResult
from crossborder_compliance.domain.rule_ast import (
    RuleValidationError,
    evaluate,
    parse_ast,
    typed_value,
)


def band_for(policy, score):
    if score is None:
        return RiskLevel.UNKNOWN
    bands = sorted(policy.bands, key=lambda b: b.lower)
    for i, band in enumerate(bands):
        if band.lower <= score < band.upper or (i == len(bands) - 1 and score == band.upper):
            return band.band
    raise ValueError("score outside governed bands")


def evaluate_policy_values(policy, values, refs=None, evidence_ids=()):
    """No missing input is coerced to false/zero. Ambiguous band rows remain UNKNOWN."""
    refs = refs or {}
    if policy.mode == "BAND_ONLY":
        matched = []
        for row in policy.band_rows:
            states = []
            for c in row.conditions:
                schema = {f.code: f.field_type for f in c.fields}
                ast = parse_ast(c.predicate, schema)
                try:
                    facts = {
                        k: typed_value(v, schema[k], literal=True)
                        for k, v in values.items()
                        if k in schema
                    }
                    states.append(evaluate(ast, facts))
                except RuleValidationError:
                    return None, RiskLevel.UNKNOWN, ()
            if all(states):
                matched.append(row.band)
        return None, matched[0] if len(matched) == 1 else RiskLevel.UNKNOWN, ()
    dimensions = []
    quantum = Decimal(1).scaleb(-policy.decimal_scale)
    with localcontext() as ctx:
        ctx.prec = 50
        for d in policy.dimensions:
            factors = []
            unknown = False
            for f in d.factors:
                raw = values.get(f.observation_code)
                score = None
                if raw is not None and type(raw) is not bool:
                    try:
                        observed = Decimal(str(raw))
                        if not observed.is_finite():
                            raise ValueError("nonfinite risk input")
                        if f.score_ranges:
                            ranges = sorted(f.score_ranges, key=lambda r: r.lower)
                            for n, interval in enumerate(ranges):
                                if interval.lower <= observed < interval.upper or (
                                    n == len(ranges) - 1 and observed == interval.upper
                                ):
                                    score = interval.score
                                    break
                        elif 0 <= observed <= 100:
                            score = observed
                    except (ValueError, ArithmeticError):
                        observed = None
                else:
                    observed = None
                excluded = score is None and not f.required and f.exclude_when_missing
                if score is None and not excluded:
                    unknown = True
                factors.append(
                    RiskFactorResult(
                        code=f.code,
                        observation_code=f.observation_code,
                        observed_value=observed,
                        score=score,
                        weight=f.weight,
                        required=f.required,
                        included=not excluded,
                        fact_refs=refs.get(f.observation_code, ()),
                        evidence_ids=evidence_ids,
                    )
                )
            included = [f for f in factors if f.included]
            denominator = sum((f.weight for f in included), Decimal(0))
            score = None
            if not unknown and denominator:
                score = (
                    sum((f.score * f.weight for f in included), Decimal(0)) / denominator
                ).quantize(quantum, rounding=policy.rounding)
            dimensions.append(
                RiskDimensionResult(
                    code=d.code,
                    factors=tuple(factors),
                    score=score,
                    band=band_for(policy, score),
                    weight=d.weight,
                )
            )
        total = None
        if all(d.score is not None for d in dimensions):
            total = sum((d.score * d.weight for d in dimensions), Decimal(0)).quantize(
                quantum, rounding=policy.rounding
            )
    return total, band_for(policy, total), tuple(dimensions)
