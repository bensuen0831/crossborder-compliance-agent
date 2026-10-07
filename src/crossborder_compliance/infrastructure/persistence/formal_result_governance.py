"""C0 validation hooks within canonical metadata review/publish transactions."""

from sqlalchemy import select

from crossborder_compliance.domain.decision_policies import ObligationPolicy
from crossborder_compliance.domain.formal_result_policies import FORMAL_RESULT_POLICY_TYPES
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b


def validate_formal_policy(session, definition, payload):
    from crossborder_compliance.infrastructure.persistence.compliance_profile_governance import (
        metadata_ref,
        scoped,
    )

    cfg = FORMAL_RESULT_POLICY_TYPES[definition.kind].model_validate(payload)
    tenant = definition.tenant_id
    for ident in cfg.jurisdiction_ids:
        scoped(session, b.JurisdictionEntity, ident, tenant)
    parent = metadata_ref(session, cfg.obligation_policy_id, tenant, "OBLIGATION_POLICY")
    version = scoped(session, m.MetadataVersionEntity, parent.active_version_id, tenant)
    if version.lifecycle_status != "ACTIVE" or not version.published_at:
        raise ValueError("published obligation policy required")
    obligation = ObligationPolicy.model_validate(version.payload_json)
    if set(obligation.jurisdiction_ids) != set(cfg.jurisdiction_ids):
        raise ValueError("formal policy jurisdiction coverage mismatch")
    known = {e.entry_id for e in obligation.entries}
    if definition.kind == "CROSS_BORDER_ASSESSMENT_POLICY":
        if not {p.requirement_id for p in cfg.prerequisites} <= known:
            raise ValueError("unknown transfer prerequisite")
    else:
        cross = metadata_ref(
            session, cfg.cross_border_policy_id, tenant, "CROSS_BORDER_ASSESSMENT_POLICY"
        )
        cross_version = scoped(session, m.MetadataVersionEntity, cross.active_version_id, tenant)
        if cross_version.lifecycle_status != "ACTIVE" or not cross_version.published_at:
            raise ValueError("published cross-border policy required")
        cross_cfg = FORMAL_RESULT_POLICY_TYPES[cross.kind].model_validate(
            cross_version.payload_json
        )
        if cross_cfg.obligation_policy_id != cfg.obligation_policy_id or set(
            cross_cfg.jurisdiction_ids
        ) != set(cfg.jurisdiction_ids):
            raise ValueError("document policy dependency closure mismatch")
        for entry in cfg.entries:
            if not set(entry.trigger_obligation_entry_ids) <= known:
                raise ValueError("unknown document legal trigger")
            if entry.template_binding_id:
                scoped(session, m.TemplateBindingEntity, entry.template_binding_id, tenant)
        current = {e.document_type_code: e.entry_id for e in cfg.entries}
        for old in session.scalars(
            select(m.MetadataVersionEntity).where(
                m.MetadataVersionEntity.tenant_id == tenant,
                m.MetadataVersionEntity.definition_id == definition.definition_id,
                m.MetadataVersionEntity.lifecycle_status.in_(
                    ("APPROVED", "ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED")
                ),
            )
        ):
            prior = {
                e.document_type_code: e.entry_id
                for e in FORMAL_RESULT_POLICY_TYPES[definition.kind]
                .model_validate(old.payload_json)
                .entries
            }
            if any(current[k] != prior[k] for k in current.keys() & prior.keys()) or any(
                k != old_k
                for k, v in current.items()
                for old_k, old_v in prior.items()
                if v == old_v
            ):
                raise ValueError("document requirement identity cannot be reassigned")
    return {
        "payload_json": cfg.model_dump(mode="json"),
        "effective_from": cfg.effective_from,
        "effective_to": cfg.effective_to,
    }
