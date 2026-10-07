"""Pure owning decisions, closed formal inputs and validated governed predicates."""

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import model_validator

from crossborder_compliance.domain.decision_contracts import (
    ENVELOPE_TYPES,
    LegalSupport,
    PinRef,
    digest,
    result_digest,
    unique,
)
from crossborder_compliance.domain.decision_engine import AuthorizedFact, condition_result
from crossborder_compliance.domain.formal_result_contracts import (
    AUTHORITY_ENVELOPES,
    AuthorityIdentity,
    AuthorityProvenance,
    AuthorityRef,
    CrossBorderAssessmentDTOv2,
    RequiredDocumentDTOv2,
)
from crossborder_compliance.domain.formal_result_policies import (
    FORMAL_RESULT_POLICY_TYPES,
    CrossBorderAssessmentPolicy,
    DocumentRequirementPolicy,
)
from crossborder_compliance.domain.rules import Contract

ObligationResult = ENVELOPE_TYPES["OBLIGATION"]
FinalPathResult = ENVELOPE_TYPES["FINAL_PATH"]
CrossBorderResult = AUTHORITY_ENVELOPES["CROSS_BORDER"]


class PinnedAuthorityPolicy(Contract):
    pin: PinRef
    config: CrossBorderAssessmentPolicy | DocumentRequirementPolicy

    @model_validator(mode="after")
    def exact_type(self):
        if type(self.config) is not FORMAL_RESULT_POLICY_TYPES.get(self.pin.kind):
            raise ValueError("authority policy pin/config mismatch")
        return self


class PinnedTemplate(Contract):
    entry_id: UUID
    binding_id: UUID
    version_id: UUID


class PreparedAuthorityInput(Contract):
    identity: AuthorityIdentity
    obligation: ObligationResult | None
    final_path: FinalPathResult | None = None
    cross_border: CrossBorderResult | None = None
    facts: tuple[AuthorizedFact, ...]
    support: LegalSupport
    source_jurisdiction_ids: tuple[UUID, ...]
    destination_jurisdiction_ids: tuple[UUID, ...]
    policies: tuple[PinnedAuthorityPolicy, ...]
    pins: tuple[PinRef, ...]
    templates: tuple[PinnedTemplate, ...] = ()
    blocking_reason_codes: tuple[str, ...] = ()
    evidence_sufficient: bool
    context_digest: str
    prepared_at: datetime
    actor_ref: str
    request_id: str
    correlation_id: str

    @model_validator(mode="after")
    def authorized_scope(self):
        i = self.identity
        for r in (self.obligation, self.final_path, self.cross_border):
            if r and any(
                getattr(r, k) != getattr(i, k)
                for k in (
                    "tenant_id",
                    "project_id",
                    "analysis_snapshot_id",
                    "project_version_id",
                    "context_version",
                    "subject_type",
                    "subject_id",
                )
            ):
                raise ValueError("authority upstream scope mismatch")
        if any(p.pin not in self.pins for p in self.policies):
            raise ValueError("authority policy not pinned")
        if len({f.code for f in self.facts}) != len(self.facts):
            raise ValueError("ambiguous authority fact")
        return self

    def policy(self, kind):
        found = [p for p in self.policies if p.pin.kind == kind]
        return found[0] if len(found) == 1 else None


def input_digest(x, kind):
    # Cross-border legality never depends on a later implementation/path status.
    data = {
        "identity": x.identity,
        "obligation": result_digest(x.obligation) if x.obligation else None,
        "facts": x.facts,
        "support": x.support,
        "source": x.source_jurisdiction_ids,
        "destination": x.destination_jurisdiction_ids,
        "pins": x.pins,
        "blocking": x.blocking_reason_codes,
        "evidence": x.evidence_sufficient,
        "context": x.context_digest,
    }
    if kind == "DOCUMENT_REQUIREMENT":
        data.update(
            final=result_digest(x.final_path) if x.final_path else None,
            cross_border=result_digest(x.cross_border) if x.cross_border else None,
            templates=x.templates,
        )
    return digest(data)


def upstream_refs(x, kind):
    parents = [x.obligation]
    if kind == "DOCUMENT_REQUIREMENT":
        parents.extend((x.cross_border, x.final_path))
    return tuple(
        AuthorityRef(kind=p.stage_kind, result_id=p.result_id, content_digest=result_digest(p))
        for p in parents
        if p
    )


def envelope(x, kind, items, status, reasons, review=False):
    fingerprint = input_digest(x, kind)
    pins_digest = digest(x.pins)
    refs = upstream_refs(x, kind)
    return AUTHORITY_ENVELOPES[kind](
        **x.identity.model_dump(),
        result_id=uuid5(NAMESPACE_URL, kind + fingerprint),
        stage_kind=kind,
        upstream_refs=refs,
        items=items,
        input_sufficiency="SUFFICIENT" if x.evidence_sufficient else "INSUFFICIENT_EVIDENCE",
        conflict_state="CONFLICTED"
        if any(c in x.blocking_reason_codes for c in ("FACT_CONFLICT", "PRODUCT_CONTEXT_CONFLICT"))
        else "CLEAR",
        review_required=review,
        reason_codes=reasons,
        confidence=confidence(x, review, kind),
        pins=x.pins,
        input_digest=fingerprint,
        pins_digest=pins_digest,
        ordinary_status=status,
        provenance=AuthorityProvenance(
            origins=refs,
            context_fact_refs=unique(v for f in x.facts for v in f.fact_refs),
            retrieval_run_ids=x.support.retrieval_run_ids,
            pins=x.pins,
            computation_timestamp=x.prepared_at,
            actor_ref=x.actor_ref,
            request_id=x.request_id,
            correlation_id=x.correlation_id,
        ),
    )


def confidence(x, review, kind="CROSS_BORDER"):
    parents = (
        (x.obligation,) if kind == "CROSS_BORDER" else (x.obligation, x.cross_border, x.final_path)
    )
    return 0 if review else min((r.confidence for r in parents if r is not None), default=0)


def upstream_review(x):
    if x.blocking_reason_codes:
        return x.blocking_reason_codes
    if not x.evidence_sufficient:
        return ("EVIDENCE_INSUFFICIENT",)
    if x.obligation is None:
        return ("CAPABILITY_NOT_CONFIGURED",)
    if x.obligation.conflict_state == "CONFLICTED":
        return ("FACT_CONFLICT",)
    if x.obligation.review_required or x.obligation.input_sufficiency != "SUFFICIENT":
        return ("EVIDENCE_INSUFFICIENT",)
    return ()


def cross_border_assessment(x):
    policy = x.policy("CROSS_BORDER_ASSESSMENT_POLICY")
    cfg = policy.config if policy else None
    reasons = upstream_review(x)
    if not reasons and not (x.source_jurisdiction_ids and x.destination_jurisdiction_ids):
        reasons = ("JURISDICTION_UNRESOLVED",)
    if not reasons and cfg is None:
        reasons = ("CAPABILITY_NOT_CONFIGURED",)
    support = x.support
    if not reasons and not (
        support.applicability_result_ids
        and support.rule_hit_ids
        and support.legal_basis_ids
        and support.evidence_ids
    ):
        reasons = ("EVIDENCE_INSUFFICIENT",)
    status = "REVIEW_REQUIRED"
    localization = False
    required = {}
    chosen = ()
    if not reasons:
        established = [
            o for o in x.obligation.items if o.legal_effect == "REQUIRED" and not o.review_required
        ]
        prohibited = [o for o in established if o.legal_effect_code == "TRANSFER_PROHIBITED"]
        localized = [o for o in established if o.legal_effect_code == "LOCALIZATION_REQUIRED"]
        localization = bool(localized)
        if prohibited or localized:
            status = "TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED"
            chosen = tuple(prohibited + localized)
            reasons = tuple(
                code
                for yes, code in (
                    (bool(prohibited), "LEGAL_PROHIBITION"),
                    (bool(localized), "LOCALIZATION_REQUIRED"),
                )
                if yes
            )
        else:
            uncertain = [
                o
                for o in x.obligation.items
                if o.legal_effect in {"UNDETERMINED", "CONDITIONAL"}
                and o.legal_effect_code in {"TRANSFER_PROHIBITED", "LOCALIZATION_REQUIRED"}
            ]
            if uncertain:
                reasons = ("PREREQUISITE_NOT_MET",)
            elif (
                cfg.non_transfer_condition
                and condition_result(cfg.non_transfer_condition, x).evaluation != "FALSE"
            ):
                if condition_result(cfg.non_transfer_condition, x).evaluation == "TRUE":
                    status = "NOT_APPLICABLE"
                    reasons = ("NON_TRANSFER_SCOPE",)
                else:
                    reasons = ("EVIDENCE_INSUFFICIENT",)
            else:
                permission = condition_result(cfg.transfer_legally_possible, x)
                by_requirement = {o.requirement_id: o for o in x.obligation.items}
                chosen = tuple(
                    by_requirement[p.requirement_id]
                    for p in cfg.prerequisites
                    if p.requirement_id in by_requirement
                )
                if permission.evaluation != "TRUE":
                    reasons = (
                        "EVIDENCE_INSUFFICIENT"
                        if permission.evaluation == "UNKNOWN"
                        else "PREREQUISITE_NOT_MET",
                    )
                elif len(chosen) != len(cfg.prerequisites) or any(
                    o.review_required
                    or o.legal_effect in {"UNDETERMINED", "CONDITIONAL"}
                    or (o.legal_effect != "NOT_APPLICABLE" and o.fulfillment_state == "UNKNOWN")
                    for o in chosen
                ):
                    reasons = ("PREREQUISITE_NOT_MET",)
                else:
                    unmet = [
                        o
                        for o in chosen
                        if o.legal_effect != "NOT_APPLICABLE" and o.fulfillment_state != "SATISFIED"
                    ]
                    required = {
                        p.kind: True
                        for p in cfg.prerequisites
                        if by_requirement[p.requirement_id].legal_effect != "NOT_APPLICABLE"
                    }
                    status = "CONDITIONAL_TRANSFER_ALLOWED" if unmet else "DIRECT_TRANSFER_ALLOWED"
                    reasons = (
                        (
                            (
                                "APPROVAL_PENDING"
                                if any(
                                    p.kind == "APPROVAL"
                                    and by_requirement[p.requirement_id] in unmet
                                    for p in cfg.prerequisites
                                )
                                else "PREREQUISITE_NOT_MET"
                            ),
                        )
                        if unmet
                        else ("TRANSFER_PREREQUISITES_SATISFIED",)
                    )
    review = status == "REVIEW_REQUIRED"
    fingerprint = input_digest(x, "CROSS_BORDER")
    item = CrossBorderAssessmentDTOv2(
        cross_border_assessment_id=uuid5(NAMESPACE_URL, "assessment" + fingerprint),
        project_id=x.identity.project_id,
        analysis_snapshot_id=x.identity.analysis_snapshot_id,
        subject_type=x.identity.subject_type,
        subject_id=x.identity.subject_id,
        data_item_ids=x.identity.data_item_ids,
        data_flow_ids=x.identity.data_flow_ids,
        source_jurisdiction_ids=x.source_jurisdiction_ids,
        destination_jurisdiction_ids=x.destination_jurisdiction_ids,
        status=status,
        reason_codes=reasons,
        localization_required=localization,
        filing_required=required.get("FILING", False),
        assessment_required=required.get("ASSESSMENT", False),
        approval_required=required.get("APPROVAL", False),
        obligation_ids=unique(o.obligation_id for o in chosen),
        applicability_result_ids=support.applicability_result_ids,
        rule_hit_ids=support.rule_hit_ids,
        legal_basis_ids=support.legal_basis_ids,
        evidence_ids=support.evidence_ids,
        policy_version_id=policy.pin.version_id if policy else None,
        review_required=review,
        confidence=confidence(x, review),
        input_digest=fingerprint,
        pins_digest=digest(x.pins),
    )
    return envelope(x, "CROSS_BORDER", (item,), status, reasons, review)


def regulatory_document_requirements(x):
    policy = x.policy("DOCUMENT_REQUIREMENT_POLICY")
    reasons = upstream_review(x)
    if not reasons and (not x.cross_border or x.cross_border.review_required):
        reasons = ("UPSTREAM_REVIEW_REQUIRED",)
    if not reasons and (
        not x.final_path
        or x.final_path.review_required
        or x.final_path.summary_status in {"UNDETERMINED", "CONFLICTED", "INSUFFICIENT_EVIDENCE"}
    ):
        reasons = ("UPSTREAM_REVIEW_REQUIRED",)
    if not reasons and policy is None:
        reasons = ("CAPABILITY_NOT_CONFIGURED",)
    if reasons:
        return envelope(x, "DOCUMENT_REQUIREMENT", (), "REVIEW_REQUIRED", reasons, True)
    items = []
    fingerprint = input_digest(x, "DOCUMENT_REQUIREMENT")
    for entry in policy.config.entries:
        obligations = tuple(
            o
            for o in x.obligation.items
            if o.requirement_id in entry.trigger_obligation_entry_ids
            and o.legal_effect in {"REQUIRED", "CONDITIONAL"}
        )
        actions = tuple(
            a
            for item in x.final_path.items
            for a in item.actions
            if a.action_code in entry.trigger_path_action_codes
        )
        assessments = tuple(
            a for a in x.cross_border.items if a.status in entry.cross_border_statuses
        )
        triggered = bool(obligations or actions or assessments)
        conditions = (condition_result(entry.condition, x),) if entry.condition else ()
        if triggered and any(c.evaluation == "UNKNOWN" for c in conditions):
            return envelope(
                x, "DOCUMENT_REQUIREMENT", (), "REVIEW_REQUIRED", ("EVIDENCE_INSUFFICIENT",), True
            )
        triggered = triggered and all(c.evaluation == "TRUE" for c in conditions)
        level = entry.requirement_level if triggered else "NOT_APPLICABLE"
        support = x.support
        if triggered and not (support.legal_basis_ids and support.evidence_ids):
            return envelope(
                x, "DOCUMENT_REQUIREMENT", (), "REVIEW_REQUIRED", ("EVIDENCE_INSUFFICIENT",), True
            )
        template = next((t.version_id for t in x.templates if t.entry_id == entry.entry_id), None)
        items.append(
            RequiredDocumentDTOv2(
                document_requirement_id=uuid5(
                    policy.pin.version_id, str(entry.entry_id) + fingerprint
                ),
                document_type_code=entry.document_type_code,
                name=entry.name,
                requirement_level=level,
                trigger_obligation_ids=unique(o.obligation_id for o in obligations)
                if triggered
                else (),
                trigger_cross_border_assessment_ids=unique(
                    a.cross_border_assessment_id for a in assessments
                )
                if triggered
                else (),
                trigger_path_step_ids=unique(a.entry_id for a in actions) if triggered else (),
                requirement_ids=unique(o.requirement_id for o in obligations) if triggered else (),
                legal_basis_ids=support.legal_basis_ids if triggered else (),
                evidence_ids=support.evidence_ids if triggered else (),
                jurisdiction_ids=x.identity.jurisdiction_ids,
                template_version_id=template,
                reason_codes=("GOVERNED_DOCUMENT_REQUIREMENT",)
                if triggered
                else ("NO_GOVERNED_TRIGGER",),
                conditions=conditions,
                review_required=False,
                policy_version_id=policy.pin.version_id,
                input_digest=fingerprint,
                pins_digest=digest(x.pins),
            )
        )
    return envelope(
        x,
        "DOCUMENT_REQUIREMENT",
        tuple(items),
        "REQUIREMENTS_IDENTIFIED",
        ("GOVERNED_DOCUMENT_REQUIREMENTS",),
    )
