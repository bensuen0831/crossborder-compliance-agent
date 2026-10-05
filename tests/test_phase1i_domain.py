from datetime import date
from uuid import uuid4

import pytest
from phase1i_fixtures import prepared
from pydantic import ValidationError

from crossborder_compliance.domain.compliance_profiles import (
    STANDARD_COMPLIANCE_PIPELINE,
    CapabilityConfig,
    CapabilityInput,
    CapabilityKind,
    CountryCapability,
    ScenarioAdjustmentConfig,
    ScenarioAdjustmentProfile,
    ScenarioExecutionConfiguration,
    effective,
    merge_scenario_profiles,
    resolve_capability,
)
from crossborder_compliance.domain.regulation_applicability import (
    ApplicabilityInput,
    RegulationApplicabilitySkill,
)


def profile(config, tenant=None):
    return ScenarioAdjustmentProfile(
        profile_id=uuid4(),
        version_id=uuid4(),
        tenant_id=tenant or uuid4(),
        version=1,
        lifecycle="ACTIVE",
        provenance={"review": "verified"},
        config=config,
    )


def test_scenario_deterministic_merge_required_conditional_disabled_optional_and_inputs():
    scenario = uuid4()
    a = uuid4()
    b = uuid4()
    optional = uuid4()
    cap = uuid4()
    evidence = uuid4()
    x = profile(
        ScenarioAdjustmentConfig(
            scenario_definition_id=scenario,
            effective_from=date(2025, 1, 1),
            required_inputs=("SCENARIO",),
            optional_inputs=("OPTIONAL",),
            required_skill_ids=(a,),
            conditional_skill_ids=({"skill_id": b, "when_inputs": ["TRANSFER"]},),
            disabled_skill_ids=(optional,),
            required_country_capability_ids=(cap,),
            evidence_requirement_profile_id=evidence,
            risk_dimension_priorities={"SENSITIVITY": 80},
            required_outputs=("APPLICABILITY",),
        )
    )
    y = profile(
        ScenarioAdjustmentConfig(
            scenario_definition_id=scenario,
            effective_from=date(2025, 1, 1),
            required_inputs=("JURISDICTION",),
            scenario_specific_checks={"FORMAL": "REQUIRED"},
        ),
        x.tenant_id,
    )
    available = frozenset({"SCENARIO", "JURISDICTION", "TRANSFER"})
    merged = merge_scenario_profiles((x, y), available)
    assert merged == merge_scenario_profiles((y, x), available)
    assert merged.pipeline == STANDARD_COMPLIANCE_PIPELINE
    assert (
        merged.status == "READY"
        and merged.required_skill_ids == (a,)
        and merged.conditional_skill_ids == (b,)
    )
    assert merged.disabled_skill_ids == (optional,) and merged.required_country_capability_ids == (
        cap,
    )
    assert (
        merged.evidence_requirement_profile_id == evidence
        and merged.risk_dimension_priorities == {"SENSITIVITY": 80}
    )
    missing = merge_scenario_profiles((x, y), frozenset())
    assert missing.status == "REVIEW_REQUIRED" and set(missing.missing_inputs) == {
        "SCENARIO",
        "JURISDICTION",
    }


@pytest.mark.parametrize(
    "field",
    [
        "required_skill_ids",
        "evidence_requirement_profile_id",
        "risk_dimension_priorities",
        "scenario_specific_checks",
    ],
)
def test_scenario_conflicts_are_typed_and_never_silently_choose(field):
    skill = uuid4()
    base = {"scenario_definition_id": uuid4(), "effective_from": "2025-01-01"}
    left = ScenarioAdjustmentConfig(
        **base,
        required_skill_ids=(skill,),
        evidence_requirement_profile_id=uuid4(),
        risk_dimension_priorities={"X": 1},
        scenario_specific_checks={"X": "A"},
    )
    changed = left.model_dump()
    if field == "required_skill_ids":
        changed["required_skill_ids"] = ()
        changed["disabled_skill_ids"] = (skill,)
    elif field == "evidence_requirement_profile_id":
        changed[field] = uuid4()
    elif field == "risk_dimension_priorities":
        changed[field] = {"X": 2}
    else:
        changed[field] = {"X": "B"}
    merged = merge_scenario_profiles(
        (profile(left), profile(ScenarioAdjustmentConfig(**changed))), frozenset()
    )
    assert merged.status == "REVIEW_REQUIRED" and merged.conflict_codes


def test_scenario_cannot_supply_custom_pipeline_or_disable_own_required_skill():
    skill = uuid4()
    for bad in (
        {"pipeline": ["APPLICABILITY", "EVIDENCE"]},
        {"required_skill_ids": [skill], "disabled_skill_ids": [skill]},
    ):
        with pytest.raises(ValidationError):
            ScenarioAdjustmentConfig(
                scenario_definition_id=uuid4(), effective_from="2025-01-01", **bad
            )
    c = ScenarioAdjustmentConfig(
        scenario_definition_id=uuid4(), effective_from="2025-01-01", effective_to="2026-01-01"
    )
    assert effective(c, date(2026, 1, 1)) and not effective(c, date(2026, 1, 2))


@pytest.mark.parametrize("kind", list(CapabilityKind))
def test_every_generic_capability_discovery_binding_and_no_obligation(kind):
    inputs = prepared()
    cap = CountryCapability(
        profile_id=uuid4(),
        version_id=uuid4(),
        tenant_id=inputs.tenant_id,
        version=1,
        lifecycle="ACTIVE",
        provenance={"approved_by": "reviewer"},
        config=CapabilityConfig(kind=kind, effective_from="2025-01-01"),
    )
    country = inputs.country_profile.model_copy(
        update={
            "config": inputs.country_profile.config.model_copy(
                update={"capability_ids": (cap.profile_id,)}
            )
        }
    )
    request = CapabilityInput(
        kind=kind,
        tenant_id=inputs.tenant_id,
        project_id=inputs.project_id,
        analysis_snapshot_id=inputs.analysis_snapshot_id,
        jurisdiction_id=inputs.jurisdiction_id,
        data_item_id=inputs.subject_id,
        classification_result_ids=tuple(c.classification_result_id for c in inputs.classifications),
    )
    result = resolve_capability(country, (cap,), request)
    assert (
        result.status == "CONFIGURED"
        and result.legal_obligation is False
        and result.capability_version_id == cap.version_id
    )
    assert resolve_capability(country, (), request).status == "CAPABILITY_NOT_CONFIGURED"
    assert (
        resolve_capability(
            country, (cap,), request.model_copy(update={"data_item_id": None})
        ).status
        == "NOT_APPLICABLE"
    )
    assert (
        resolve_capability(
            country,
            (cap,),
            request.model_copy(update={"data_item_id": None}),
            no_data="INSUFFICIENT_INPUT",
        ).status
        == "INSUFFICIENT_INPUT"
    )
    if kind == CapabilityKind.CLASSIFICATION:
        assert (
            resolve_capability(
                country, (cap,), request.model_copy(update={"classification_result_ids": ()})
            ).status
            == "INSUFFICIENT_INPUT"
        )


@pytest.mark.parametrize("state", ["NOT_APPLICABLE", "REVIEW_REQUIRED"])
def test_configured_capability_state_is_retained(state):
    inputs = prepared()
    ident = uuid4()
    cap = CountryCapability(
        profile_id=ident,
        version_id=uuid4(),
        tenant_id=inputs.tenant_id,
        version=1,
        lifecycle="ACTIVE",
        provenance={"review": "pass"},
        config=CapabilityConfig(kind="FILING", availability=state, effective_from="2025-01-01"),
    )
    country = inputs.country_profile.model_copy(
        update={
            "config": inputs.country_profile.config.model_copy(update={"capability_ids": (ident,)})
        }
    )
    request = CapabilityInput(
        kind="FILING",
        tenant_id=inputs.tenant_id,
        project_id=inputs.project_id,
        analysis_snapshot_id=inputs.analysis_snapshot_id,
        jurisdiction_id=inputs.jurisdiction_id,
        data_item_id=inputs.subject_id,
    )
    assert resolve_capability(country, (cap,), request).status == state
    with pytest.raises(LookupError):
        resolve_capability(country, (cap,), request.model_copy(update={"tenant_id": uuid4()}))
    with pytest.raises(LookupError):
        resolve_capability(country, (cap,), request.model_copy(update={"jurisdiction_id": uuid4()}))


@pytest.mark.parametrize("status", ["APPLICABLE", "CONDITIONALLY_APPLICABLE", "REVIEW_REQUIRED"])
def test_rule_backed_positive_applicability_statuses(status):
    inputs = prepared()
    inputs = inputs.model_copy(
        update={"config": inputs.config.model_copy(update={"matched_status": status})}
    )
    result = RegulationApplicabilitySkill().execute(inputs)
    assert (
        result.applicability_status == status
        and result.regulation_version_ref == inputs.config.knowledge_version_id
    )
    assert (
        result.legal_basis_ids
        and result.rule_hit_ids
        and result.evidence_ids
        and result.classification_result_ids
    )
    assert result.legal_obligation is False and result.confidence == 0.95


def test_rule_backed_not_applicable_and_missing_hit_cannot_be_negative_decision():
    inputs = prepared()
    hit = inputs.rule_hits[0].model_copy(update={"matched": False, "triggered_actions": ()})
    result = RegulationApplicabilitySkill().execute(inputs.model_copy(update={"rule_hits": (hit,)}))
    assert result.applicability_status == "NOT_APPLICABLE"
    assert (
        RegulationApplicabilitySkill()
        .execute(inputs.model_copy(update={"rule_hits": ()}))
        .applicability_status
        == "INSUFFICIENT_EVIDENCE"
    )


@pytest.mark.parametrize("status", ["PARTIALLY_SUFFICIENT", "INSUFFICIENT", "CONFLICTED"])
def test_phase1g_insufficiency_conflict_never_fabricates_applicability(status):
    inputs = prepared()
    suff = inputs.sufficiency.model_copy(update={"status": status})
    result = RegulationApplicabilitySkill().execute(inputs.model_copy(update={"sufficiency": suff}))
    assert result.applicability_status == (
        "CONFLICTED" if status == "CONFLICTED" else "INSUFFICIENT_EVIDENCE"
    )
    assert result.review_required and result.legal_obligation is False


@pytest.mark.parametrize("missing", ["MISSING_LEGAL_BASIS", "SOURCE_NOT_EFFECTIVE"])
def test_legal_basis_and_expired_canonical_source_gate(missing):
    inputs = prepared()
    refs = inputs.canonical_legal_reference.model_copy(update={"validation_status": missing})
    assert (
        RegulationApplicabilitySkill()
        .execute(inputs.model_copy(update={"canonical_legal_reference": refs}))
        .applicability_status
        == "INSUFFICIENT_EVIDENCE"
    )


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "project_id", "analysis_snapshot_id", "jurisdiction_id", "context_version"],
)
def test_wrong_classification_identity_rejected(field):
    inputs = prepared()
    cls = inputs.classifications[0].model_copy(
        update={field: 2 if field == "context_version" else uuid4()}
    )
    data = inputs.model_dump()
    data["classifications"] = (cls,)
    with pytest.raises(ValidationError):
        ApplicabilityInput.model_validate(data)


def test_no_data_scenario_can_proceed_only_with_independent_formal_inputs_and_evidence():
    inputs = prepared()
    scenario = inputs.scenario_definition_ids[0]
    config = inputs.config.model_copy(update={"requires_classification": False})
    hit = inputs.rule_hits[0].model_copy(update={"data_item_id": None})
    suff = inputs.sufficiency.model_copy(
        update={"subject_type": "PROJECT", "subject_id": str(inputs.project_id)}
    )
    values = inputs.model_dump()
    values.update(
        subject_type="SCENARIO",
        subject_id=scenario,
        data_item_ids=(),
        classifications=(),
        rule_hits=(hit,),
        config=config,
        sufficiency=suff,
    )
    scenario_inputs = ApplicabilityInput.model_validate(values)
    result = RegulationApplicabilitySkill().execute(scenario_inputs)
    assert (
        result.applicability_status == "APPLICABLE"
        and not result.classification_result_ids
        and not result.data_item_ids
    )
    values["fact_refs"] = ()
    with pytest.raises(ValidationError):
        ApplicabilityInput.model_validate(values)
    assert (
        RegulationApplicabilitySkill()
        .execute(
            scenario_inputs.model_copy(
                update={
                    "classifications": (),
                    "config": config.model_copy(update={"requires_classification": True}),
                }
            )
        )
        .applicability_status
        == "REVIEW_REQUIRED"
    )


def test_scenario_conflict_and_input_review_are_conservative():
    inputs = prepared()
    merged = ScenarioExecutionConfiguration(
        status="REVIEW_REQUIRED", conflict_codes=("REQUIRED_DISABLED_SKILL_CONFLICT",)
    )
    assert (
        RegulationApplicabilitySkill()
        .execute(inputs.model_copy(update={"scenario_configuration": merged}))
        .applicability_status
        == "CONFLICTED"
    )
    assert (
        RegulationApplicabilitySkill()
        .execute(inputs.model_copy(update={"review_required": True}))
        .applicability_status
        == "REVIEW_REQUIRED"
    )


def test_contradictory_required_rule_hits_are_conflicted_not_last_writer_wins():
    inputs = prepared()
    original = inputs.rule_hits[0]
    contradictory = original.model_copy(
        update={"rule_hit_id": uuid4(), "matched": False, "triggered_actions": ()}
    )
    for hits in ((original, contradictory), (contradictory, original)):
        result = RegulationApplicabilitySkill().execute(
            inputs.model_copy(update={"rule_hits": hits})
        )
        assert (
            result.applicability_status == "CONFLICTED"
            and "CONTRADICTORY_PHASE1H_RULEHITS" in result.reason_codes
        )


def test_merged_execution_configuration_cannot_reorder_pipeline():
    with pytest.raises(ValidationError):
        ScenarioExecutionConfiguration(status="READY", pipeline=("APPLICABILITY", "EVIDENCE"))
