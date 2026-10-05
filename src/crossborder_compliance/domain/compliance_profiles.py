"""Versioned country/scenario configuration over the existing metadata authority."""

from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.localized_metadata import (
    LocalizedDisplayMetadata,
    StableDisplayCode,
    StableMetadataCode,
)
from crossborder_compliance.domain.rules import Contract

STANDARD_COMPLIANCE_PIPELINE = (
    "REQUIREMENT_SCENARIO",
    "FORMAL_CONTEXT",
    "DATA_FLOW",
    "JURISDICTION",
    "KNOWLEDGE_SCOPE",
    "EVIDENCE",
    "SUFFICIENCY",
    "CLASSIFICATION",
    "APPLICABILITY",
    "OBLIGATION",
    "CANDIDATE_PATH",
    "RISK",
    "RECOMMENDATION",
    "FINAL_PATH",
)
PHASE1I_CONFIG_KINDS = frozenset(
    {
        "COUNTRY_PROFILE",
        "SCENARIO_ADJUSTMENT",
        "COUNTRY_CAPABILITY",
        "APPLICABILITY_CONFIG",
        "RULE_PACK",
    }
)


class CapabilityKind(StrEnum):
    CLASSIFICATION = "CLASSIFICATION"
    CROSS_BORDER = "CROSS_BORDER"
    LOCALIZATION = "LOCALIZATION"
    FILING = "FILING"
    IMPACT_ASSESSMENT = "IMPACT_ASSESSMENT"
    CONTRACT = "CONTRACT"
    REGULATOR = "REGULATOR"


class EffectiveConfig(Contract):
    localized_display: LocalizedDisplayMetadata | None = None
    localized_code_labels: dict[StableDisplayCode, LocalizedDisplayMetadata] = Field(
        default_factory=dict
    )
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def interval(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("invalid configuration effective interval")
        return self


class CountryProfileConfig(EffectiveConfig):
    jurisdiction_id: UUID
    capability_ids: tuple[UUID, ...] = ()
    rule_pack_ids: tuple[UUID, ...] = ()
    knowledge_collection_ids: tuple[UUID, ...] = ()
    prompt_config_ids: tuple[UUID, ...] = ()
    template_scope_ids: tuple[UUID, ...] = ()
    applicability_config_ids: tuple[UUID, ...] = ()
    permission_scopes: tuple[str, ...] = ()


class CapabilityConfig(EffectiveConfig):
    kind: CapabilityKind
    availability: Literal["CONFIGURED", "NOT_APPLICABLE", "REVIEW_REQUIRED"] = "CONFIGURED"
    data_specific: bool = True
    required_inputs: tuple[StableMetadataCode, ...] = ()
    rule_pack_ids: tuple[UUID, ...] = ()
    knowledge_collection_ids: tuple[UUID, ...] = ()
    template_scope_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[StableDisplayCode, ...] = Field(
        default=("CAPABILITY_CONFIGURED",), min_length=1
    )


class ClassificationCapability(CapabilityConfig):
    kind: Literal[CapabilityKind.CLASSIFICATION] = CapabilityKind.CLASSIFICATION


class CrossBorderCapability(CapabilityConfig):
    kind: Literal[CapabilityKind.CROSS_BORDER] = CapabilityKind.CROSS_BORDER


class LocalizationCapability(CapabilityConfig):
    kind: Literal[CapabilityKind.LOCALIZATION] = CapabilityKind.LOCALIZATION


class FilingCapability(CapabilityConfig):
    kind: Literal[CapabilityKind.FILING] = CapabilityKind.FILING


class ImpactAssessmentCapability(CapabilityConfig):
    kind: Literal[CapabilityKind.IMPACT_ASSESSMENT] = CapabilityKind.IMPACT_ASSESSMENT


class ContractCapability(CapabilityConfig):
    kind: Literal[CapabilityKind.CONTRACT] = CapabilityKind.CONTRACT


class RegulatorCapability(CapabilityConfig):
    kind: Literal[CapabilityKind.REGULATOR] = CapabilityKind.REGULATOR


class ConditionalSkill(Contract):
    skill_id: UUID
    when_inputs: tuple[StableMetadataCode, ...] = Field(min_length=1)


class ScenarioAdjustmentConfig(EffectiveConfig):
    scenario_definition_id: UUID
    required_inputs: tuple[StableMetadataCode, ...] = ()
    optional_inputs: tuple[StableMetadataCode, ...] = ()
    required_skill_ids: tuple[UUID, ...] = ()
    conditional_skill_ids: tuple[ConditionalSkill, ...] = ()
    disabled_skill_ids: tuple[UUID, ...] = ()
    required_country_capability_ids: tuple[UUID, ...] = ()
    knowledge_scope_bindings: tuple[UUID, ...] = ()
    rule_scope_bindings: tuple[UUID, ...] = ()
    template_scope_bindings: tuple[UUID, ...] = ()
    evidence_requirement_profile_id: UUID | None = None
    risk_dimension_priorities: dict[StableDisplayCode, int] = Field(default_factory=dict)
    required_outputs: tuple[StableMetadataCode, ...] = ()
    optional_outputs: tuple[StableMetadataCode, ...] = ()
    scenario_specific_checks: dict[StableMetadataCode, StableMetadataCode] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def safe_adjustment(self):
        if set(self.required_skill_ids) & set(self.disabled_skill_ids):
            raise ValueError("required skills cannot be disabled")
        if any(
            type(v) is not int or not 0 <= v <= 100 for v in self.risk_dimension_priorities.values()
        ):
            raise ValueError("risk priorities are bounded configuration, not risk results")
        return self


class PublishedVersion(Contract):
    profile_id: UUID
    version_id: UUID
    tenant_id: UUID
    version: int = Field(ge=1)
    lifecycle: Literal["ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"]
    provenance: dict[str, str] = Field(min_length=1)


class CountryComplianceProfile(PublishedVersion):
    config: CountryProfileConfig


class ScenarioAdjustmentProfile(PublishedVersion):
    config: ScenarioAdjustmentConfig


class CountryCapability(PublishedVersion):
    config: CapabilityConfig


class RulePackConfig(EffectiveConfig):
    rule_definition_ids: tuple[UUID, ...] = Field(min_length=1)


class ApplicabilityConfig(EffectiveConfig):
    jurisdiction_id: UUID
    knowledge_version_id: UUID
    regulatory_structure_node_ids: tuple[UUID, ...] = Field(min_length=1)
    legal_basis_ids: tuple[UUID, ...] = Field(min_length=1)
    required_rule_ids: tuple[UUID, ...] = Field(min_length=1)
    match_mode: Literal["ALL", "ANY"] = "ALL"
    matched_status: Literal["APPLICABLE", "CONDITIONALLY_APPLICABLE", "REVIEW_REQUIRED"] = (
        "APPLICABLE"
    )
    nonmatched_status: Literal["NOT_APPLICABLE", "REVIEW_REQUIRED"] = "NOT_APPLICABLE"
    requires_classification: bool = True
    scenario_definition_ids: tuple[UUID, ...] = ()
    reason_code: StableDisplayCode


CONFIG_TYPES = {
    "COUNTRY_PROFILE": CountryProfileConfig,
    "SCENARIO_ADJUSTMENT": ScenarioAdjustmentConfig,
    "COUNTRY_CAPABILITY": CapabilityConfig,
    "APPLICABILITY_CONFIG": ApplicabilityConfig,
    "RULE_PACK": RulePackConfig,
}


class ScenarioExecutionConfiguration(Contract):
    status: Literal["READY", "REVIEW_REQUIRED"]
    pipeline: tuple[str, ...] = STANDARD_COMPLIANCE_PIPELINE
    profile_versions: tuple[tuple[UUID, UUID, int], ...] = ()
    required_inputs: tuple[StableMetadataCode, ...] = ()
    optional_inputs: tuple[StableMetadataCode, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    required_skill_ids: tuple[UUID, ...] = ()
    conditional_skill_ids: tuple[UUID, ...] = ()
    disabled_skill_ids: tuple[UUID, ...] = ()
    required_country_capability_ids: tuple[UUID, ...] = ()
    knowledge_scope_bindings: tuple[UUID, ...] = ()
    rule_scope_bindings: tuple[UUID, ...] = ()
    template_scope_bindings: tuple[UUID, ...] = ()
    evidence_requirement_profile_id: UUID | None = None
    risk_dimension_priorities: dict[StableDisplayCode, int] = Field(default_factory=dict)
    required_outputs: tuple[StableMetadataCode, ...] = ()
    optional_outputs: tuple[StableMetadataCode, ...] = ()
    scenario_specific_checks: dict[StableMetadataCode, StableMetadataCode] = Field(
        default_factory=dict
    )
    conflict_codes: tuple[StableDisplayCode, ...] = ()

    @model_validator(mode="after")
    def fixed_pipeline(self):
        if self.pipeline != STANDARD_COMPLIANCE_PIPELINE:
            raise ValueError("scenario configuration cannot change the standard pipeline")
        return self


def effective(config: EffectiveConfig, when: date) -> bool:
    return config.effective_from <= when and (
        config.effective_to is None or when <= config.effective_to
    )


def merge_scenario_profiles(
    profiles: tuple[ScenarioAdjustmentProfile, ...], inputs: frozenset[str]
):
    ordered = sorted(profiles, key=lambda p: (str(p.profile_id), str(p.version_id)))
    fields = (
        "required_inputs",
        "optional_inputs",
        "required_skill_ids",
        "disabled_skill_ids",
        "required_country_capability_ids",
        "knowledge_scope_bindings",
        "rule_scope_bindings",
        "template_scope_bindings",
        "required_outputs",
        "optional_outputs",
    )
    values = {
        name: tuple(sorted({v for p in ordered for v in getattr(p.config, name)}, key=str))
        for name in fields
    }
    conditional = {
        c.skill_id
        for p in ordered
        for c in p.config.conditional_skill_ids
        if set(c.when_inputs) <= inputs
    }
    enabled = set(values["required_skill_ids"]) | conditional
    disabled = set(values["disabled_skill_ids"])
    conflicts = []
    if enabled & disabled:
        conflicts.append("REQUIRED_DISABLED_SKILL_CONFLICT")
    evidence_profiles = {
        p.config.evidence_requirement_profile_id
        for p in ordered
        if p.config.evidence_requirement_profile_id
    }
    if len(evidence_profiles) > 1:
        conflicts.append("EVIDENCE_PROFILE_CONFLICT")
    maps = {}
    for field in ("risk_dimension_priorities", "scenario_specific_checks"):
        merged = {}
        for p in ordered:
            for key, value in getattr(p.config, field).items():
                if key in merged and merged[key] != value:
                    conflicts.append(field.upper() + "_CONFLICT")
                else:
                    merged[key] = value
        maps[field] = dict(sorted(merged.items()))
    missing = tuple(sorted(set(values["required_inputs"]) - inputs))
    values["required_skill_ids"] = (
        tuple(sorted(set(values["required_skill_ids"]) - disabled, key=str))
        if not conflicts
        else values["required_skill_ids"]
    )
    return ScenarioExecutionConfiguration(
        status="REVIEW_REQUIRED" if conflicts or missing else "READY",
        profile_versions=tuple((p.profile_id, p.version_id, p.version) for p in ordered),
        conditional_skill_ids=tuple(sorted(conditional - disabled, key=str)),
        missing_inputs=missing,
        evidence_requirement_profile_id=next(iter(evidence_profiles))
        if len(evidence_profiles) == 1
        else None,
        conflict_codes=tuple(sorted(set(conflicts))),
        **values,
        **maps,
    )


class CapabilityInput(Contract):
    kind: CapabilityKind
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    jurisdiction_id: UUID
    data_item_id: UUID | None = None
    available_inputs: tuple[str, ...] = ()
    classification_result_ids: tuple[UUID, ...] = ()
    rule_hit_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()


class CapabilityResult(Contract):
    kind: CapabilityKind
    status: Literal[
        "CONFIGURED",
        "NOT_APPLICABLE",
        "INSUFFICIENT_INPUT",
        "CAPABILITY_NOT_CONFIGURED",
        "REVIEW_REQUIRED",
    ]
    country_profile_id: UUID | None = None
    country_profile_version_id: UUID | None = None
    capability_version_id: UUID | None = None
    reason_codes: tuple[StableDisplayCode, ...]
    classification_result_ids: tuple[UUID, ...] = ()
    rule_hit_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    legal_obligation: Literal[False] = False


def resolve_capability(
    profile: CountryComplianceProfile | None,
    capabilities: tuple[CountryCapability, ...],
    request: CapabilityInput,
    *,
    no_data: Literal["NOT_APPLICABLE", "INSUFFICIENT_INPUT"] = "NOT_APPLICABLE",
):
    if profile and (
        profile.tenant_id != request.tenant_id
        or profile.config.jurisdiction_id != request.jurisdiction_id
    ):
        raise LookupError("country profile not found")
    matches = [
        c
        for c in capabilities
        if c.config.kind == request.kind
        and profile
        and c.profile_id in profile.config.capability_ids
    ]
    if any(c.tenant_id != request.tenant_id for c in matches):
        raise LookupError("country capability not found")
    status = "CAPABILITY_NOT_CONFIGURED"
    reason = "CAPABILITY_NOT_CONFIGURED"
    selected = matches[0] if len(matches) == 1 else None
    if len(matches) > 1:
        status, reason = "REVIEW_REQUIRED", "CAPABILITY_BINDING_CONFLICT"
    elif selected:
        status, reason = selected.config.availability, selected.config.reason_codes[0]
        if selected.config.data_specific and request.data_item_id is None:
            status, reason = no_data, "NO_FORMAL_DATA_ITEM"
        elif not set(selected.config.required_inputs) <= set(request.available_inputs):
            status, reason = "INSUFFICIENT_INPUT", "MISSING_CAPABILITY_INPUT"
        elif (
            request.kind == CapabilityKind.CLASSIFICATION
            and status == "CONFIGURED"
            and not request.classification_result_ids
        ):
            status, reason = "INSUFFICIENT_INPUT", "MISSING_PHASE1H_CLASSIFICATION"
    return CapabilityResult(
        kind=request.kind,
        status=status,
        reason_codes=(reason,),
        country_profile_id=profile.profile_id if profile else None,
        country_profile_version_id=profile.version_id if profile else None,
        capability_version_id=selected.version_id if selected else None,
        classification_result_ids=request.classification_result_ids,
        rule_hit_ids=request.rule_hit_ids,
        evidence_ids=request.evidence_ids,
    )
