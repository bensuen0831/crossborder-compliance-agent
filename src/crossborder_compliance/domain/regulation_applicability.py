"""Typed applicability over canonical regulation references and existing formal outputs."""

from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from crossborder_compliance.domain.classification import ClassificationResult
from crossborder_compliance.domain.compliance_profiles import (
    ApplicabilityConfig,
    CountryComplianceProfile,
    ScenarioExecutionConfiguration,
)
from crossborder_compliance.domain.retrieval import (
    ActionableFallbackGuidanceContext,
    KnowledgeSufficiencyResult,
)
from crossborder_compliance.domain.rules import Contract, RuleHit

ApplicabilityStatus = Literal[
    "APPLICABLE",
    "NOT_APPLICABLE",
    "CONDITIONALLY_APPLICABLE",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTED",
    "REVIEW_REQUIRED",
]


class CanonicalLegalReference(Contract):
    """Read projection of existing KnowledgeVersion/LegalBasis; never another legal store."""

    knowledge_document_id: UUID
    knowledge_version_id: UUID
    jurisdiction_id: UUID
    regulatory_structure_node_ids: tuple[UUID, ...]
    legal_basis_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    official_sources: tuple[str, ...]
    citation_locators: tuple[str, ...]
    effective_from: date | None
    effective_to: date | None
    validation_status: Literal["VALIDATED", "MISSING_LEGAL_BASIS", "SOURCE_NOT_EFFECTIVE"]


class ApplicabilityInput(Contract):
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    data_item_ids: tuple[UUID, ...] = ()
    data_flow_ids: tuple[UUID, ...] = ()
    scenario_definition_ids: tuple[UUID, ...] = ()
    jurisdiction_id: UUID
    analysis_as_of_date: date
    context_version: int = Field(ge=1)
    fact_refs: tuple[UUID, ...] = ()
    country_profile: CountryComplianceProfile | None
    scenario_configuration: ScenarioExecutionConfiguration
    applicability_config_id: UUID
    applicability_config_version_id: UUID
    applicability_config_version: int = Field(ge=1)
    config: ApplicabilityConfig
    canonical_legal_reference: CanonicalLegalReference
    classifications: tuple[ClassificationResult, ...] = ()
    rule_hits: tuple[RuleHit, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    evidence_pack_ids: tuple[UUID, ...] = ()
    sufficiency: KnowledgeSufficiencyResult
    fallback_guidance_context: ActionableFallbackGuidanceContext | None = None
    review_required: bool = False

    @model_validator(mode="after")
    def identity(self):
        common = (self.tenant_id, self.project_id, self.analysis_snapshot_id)
        if tuple(str(v) for v in common) != (
            self.sufficiency.tenant_id,
            self.sufficiency.project_id,
            self.sufficiency.analysis_snapshot_id,
        ):
            raise ValueError("sufficiency belongs to another scope")
        evidence_subject = (self.sufficiency.subject_type, self.sufficiency.subject_id)
        exact_subject = evidence_subject == (self.subject_type, str(self.subject_id))
        scenario_project = (
            self.subject_type == "SCENARIO"
            and self.subject_id in self.scenario_definition_ids
            and bool(self.fact_refs)
            and evidence_subject == ("PROJECT", str(self.project_id))
        )
        if not (exact_subject or scenario_project):
            raise ValueError("sufficiency belongs to another subject")
        if str(self.jurisdiction_id) not in self.sufficiency.jurisdiction_ids:
            raise ValueError("sufficiency belongs to another jurisdiction")
        if (
            self.config.jurisdiction_id != self.jurisdiction_id
            or self.canonical_legal_reference.jurisdiction_id != self.jurisdiction_id
        ):
            raise ValueError("wrong regulation jurisdiction")
        if self.config.knowledge_version_id != self.canonical_legal_reference.knowledge_version_id:
            raise ValueError("wrong canonical regulation version")
        if self.country_profile and (
            self.country_profile.tenant_id != self.tenant_id
            or self.country_profile.config.jurisdiction_id != self.jurisdiction_id
        ):
            raise ValueError("wrong country profile scope")
        for c in self.classifications:
            if (
                (c.tenant_id, c.project_id, c.analysis_snapshot_id) != common
                or c.context_version != self.context_version
                or c.jurisdiction_id != self.jurisdiction_id
                or c.data_item_id not in self.data_item_ids
            ):
                raise ValueError("wrong classification snapshot/subject")
        for h in self.rule_hits:
            if (
                h.tenant_id,
                h.project_id,
                h.analysis_snapshot_id,
            ) != common or h.context_version != self.context_version:
                raise ValueError("wrong RuleHit snapshot")
            if h.data_item_id and h.data_item_id not in self.data_item_ids:
                raise ValueError("wrong RuleHit subject")
        return self


class RegulationApplicabilityResult(Contract):
    applicability_result_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    data_item_ids: tuple[UUID, ...]
    data_flow_ids: tuple[UUID, ...]
    scenario_definition_ids: tuple[UUID, ...]
    jurisdiction_id: UUID
    regulation_document_id: UUID
    regulation_version_ref: UUID
    regulatory_structure_node_ids: tuple[UUID, ...]
    applicability_status: ApplicabilityStatus
    reason_codes: tuple[str, ...] = Field(min_length=1)
    analysis_as_of_date: date
    classification_result_ids: tuple[UUID, ...]
    rule_hit_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    evidence_pack_ids: tuple[UUID, ...]
    legal_basis_ids: tuple[UUID, ...]
    country_profile_id: UUID | None
    country_profile_version_id: UUID | None
    country_profile_version: int | None
    scenario_adjustment_profile_versions: tuple[tuple[UUID, UUID, int], ...]
    applicability_config_id: UUID
    applicability_config_version_id: UUID
    applicability_config_version: int
    confidence: float = Field(ge=0, le=1)
    review_required: bool
    conflict_status: Literal["CLEAR", "CONFLICTED"]
    provenance: dict = Field(min_length=1)
    context_version: int
    record_version: int = 1
    generated_by: Literal["RULE_EVIDENCE_APPLICABILITY_V1"] = "RULE_EVIDENCE_APPLICABILITY_V1"
    fallback_guidance_context: ActionableFallbackGuidanceContext | None = None
    legal_obligation: Literal[False] = False


class EvidenceValidationResult(Contract):
    status: Literal["SUFFICIENT", "INSUFFICIENT_EVIDENCE", "CONFLICTED", "REVIEW_REQUIRED"]
    reason_codes: tuple[str, ...]


class EvidenceValidationSkill:
    def execute(self, inputs: ApplicabilityInput) -> EvidenceValidationResult:
        s = inputs.sufficiency
        status = "SUFFICIENT"
        reason = "AUTHORIZED_EVIDENCE_SUFFICIENT"
        if s.status == "CONFLICTED":
            status, reason = "CONFLICTED", "EVIDENCE_CONFLICTED"
        elif s.status != "SUFFICIENT" or not inputs.evidence_ids or not inputs.evidence_pack_ids:
            status, reason = "INSUFFICIENT_EVIDENCE", "EVIDENCE_NOT_SUFFICIENT"
        elif s.review_required:
            status, reason = "REVIEW_REQUIRED", "EVIDENCE_REVIEW_REQUIRED"
        return EvidenceValidationResult(status=status, reason_codes=(reason,))


class LegalBasisValidationResult(Contract):
    status: Literal["VALIDATED", "INSUFFICIENT_EVIDENCE"]
    legal_basis_ids: tuple[UUID, ...]
    reason_codes: tuple[str, ...]


class LegalBasisSkill:
    def execute(self, inputs: ApplicabilityInput) -> LegalBasisValidationResult:
        ref = inputs.canonical_legal_reference
        valid = (
            ref.validation_status == "VALIDATED"
            and bool(ref.legal_basis_ids)
            and set(inputs.config.legal_basis_ids) <= set(ref.legal_basis_ids)
            and set(ref.evidence_ids) <= set(inputs.evidence_ids)
            and bool(ref.official_sources)
            and bool(ref.citation_locators)
        )
        return LegalBasisValidationResult(
            status="VALIDATED" if valid else "INSUFFICIENT_EVIDENCE",
            legal_basis_ids=ref.legal_basis_ids if valid else (),
            reason_codes=("CANONICAL_LEGAL_BASIS" if valid else ref.validation_status,),
        )


class JurisdictionAnalysisBoundary:
    def validate(self, jurisdiction_id: UUID, formal_jurisdiction_ids: tuple[UUID, ...]) -> UUID:
        if jurisdiction_id not in formal_jurisdiction_ids:
            raise LookupError("jurisdiction not in formal context")
        return jurisdiction_id


class DataClassificationSkill:
    def consume(self, inputs: ApplicabilityInput) -> tuple[ClassificationResult, ...]:
        # ApplicabilityInput already validates tenant/project/snapshot/subject/version.
        return inputs.classifications


class KnowledgeScopeValidationBoundary:
    def validate(self, version_id: UUID, allowed_version_ids: tuple[UUID, ...]) -> UUID:
        if version_id not in allowed_version_ids:
            raise LookupError("regulation version outside authorized pinned knowledge scope")
        return version_id


class RegulationApplicabilitySkill:
    """Pure typed single responsibility: no ORM/provider/scope discovery or persistence."""

    def execute(self, inputs: ApplicabilityInput) -> RegulationApplicabilityResult:
        evidence = EvidenceValidationSkill().execute(inputs)
        legal = LegalBasisSkill().execute(inputs)
        status: ApplicabilityStatus = "REVIEW_REQUIRED"
        reasons = []
        config = inputs.config
        refs = inputs.canonical_legal_reference
        if inputs.scenario_configuration.conflict_codes:
            status = "CONFLICTED"
            reasons.extend(inputs.scenario_configuration.conflict_codes)
        elif evidence.status != "SUFFICIENT":
            status = evidence.status
            reasons.extend(evidence.reason_codes)
        elif inputs.country_profile is None:
            reasons.append("COUNTRY_PROFILE_NOT_CONFIGURED")
        elif inputs.scenario_configuration.status != "READY":
            reasons.append("SCENARIO_INPUT_REVIEW_REQUIRED")
        elif config.requires_classification and not inputs.classifications:
            reasons.append("MISSING_PHASE1H_CLASSIFICATION")
        elif legal.status != "VALIDATED":
            status = "INSUFFICIENT_EVIDENCE"
            reasons.extend(legal.reason_codes)
        elif config.scenario_definition_ids and not set(config.scenario_definition_ids) & set(
            inputs.scenario_definition_ids
        ):
            status = "NOT_APPLICABLE"
            reasons.append("SCENARIO_OUTSIDE_CONFIGURATION")
        else:
            hits = {h.rule_id: h for h in inputs.rule_hits}
            signatures = {}
            conflicting = False
            for hit in inputs.rule_hits:
                signature = (
                    hit.rule_version_id,
                    hit.matched,
                    hit.review_required,
                    hit.triggered_actions,
                )
                if hit.rule_id in signatures and signatures[hit.rule_id] != signature:
                    conflicting = True
                signatures[hit.rule_id] = signature
            if conflicting:
                status = "CONFLICTED"
                reasons.append("CONTRADICTORY_PHASE1H_RULEHITS")
            elif not set(config.required_rule_ids) <= set(hits):
                status = "INSUFFICIENT_EVIDENCE"
                reasons.append("MISSING_PINNED_RULEHIT")
            elif (
                inputs.review_required
                or any(h.review_required for h in inputs.rule_hits)
                or any(c.review_required for c in inputs.classifications)
            ):
                reasons.append("FORMAL_INPUT_REVIEW_REQUIRED")
            else:
                matches = [hits[ident].matched for ident in config.required_rule_ids]
                matched = all(matches) if config.match_mode == "ALL" else any(matches)
                status = config.matched_status if matched else config.nonmatched_status
                reasons.append(config.reason_code)
        confidence = min(
            [inputs.sufficiency.confidence, *[c.confidence for c in inputs.classifications]]
        )
        profile = inputs.country_profile
        return RegulationApplicabilityResult(
            tenant_id=inputs.tenant_id,
            project_id=inputs.project_id,
            analysis_snapshot_id=inputs.analysis_snapshot_id,
            subject_type=inputs.subject_type,
            subject_id=inputs.subject_id,
            data_item_ids=inputs.data_item_ids,
            data_flow_ids=inputs.data_flow_ids,
            scenario_definition_ids=inputs.scenario_definition_ids,
            jurisdiction_id=inputs.jurisdiction_id,
            regulation_document_id=refs.knowledge_document_id,
            regulation_version_ref=refs.knowledge_version_id,
            regulatory_structure_node_ids=refs.regulatory_structure_node_ids,
            applicability_status=status,
            reason_codes=tuple(reasons),
            analysis_as_of_date=inputs.analysis_as_of_date,
            classification_result_ids=tuple(
                c.classification_result_id for c in inputs.classifications
            ),
            rule_hit_ids=tuple(h.rule_hit_id for h in inputs.rule_hits),
            evidence_ids=inputs.evidence_ids,
            evidence_pack_ids=inputs.evidence_pack_ids,
            legal_basis_ids=refs.legal_basis_ids,
            country_profile_id=profile.profile_id if profile else None,
            country_profile_version_id=profile.version_id if profile else None,
            country_profile_version=profile.version if profile else None,
            scenario_adjustment_profile_versions=inputs.scenario_configuration.profile_versions,
            applicability_config_id=inputs.applicability_config_id,
            applicability_config_version_id=inputs.applicability_config_version_id,
            applicability_config_version=inputs.applicability_config_version,
            confidence=confidence,
            review_required=status in {"REVIEW_REQUIRED", "CONFLICTED", "INSUFFICIENT_EVIDENCE"},
            conflict_status="CONFLICTED" if status == "CONFLICTED" else "CLEAR",
            context_version=inputs.context_version,
            provenance={
                "official_sources": list(refs.official_sources),
                "citation_locators": list(refs.citation_locators),
                "fact_refs": [str(v) for v in inputs.fact_refs],
                "sufficiency_result_id": inputs.sufficiency.sufficiency_result_id,
                "retrieval_run_id": inputs.sufficiency.retrieval_run_id,
                "scope_revalidated": True,
            },
            fallback_guidance_context=inputs.fallback_guidance_context,
        )
