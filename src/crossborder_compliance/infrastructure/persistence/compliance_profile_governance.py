"""Phase1I validation inside the existing generic metadata lifecycle transaction."""

from sqlalchemy import select

from crossborder_compliance.domain.compliance_profiles import CONFIG_TYPES, PHASE1I_CONFIG_KINDS
from crossborder_compliance.domain.decision_policies import POLICY_TYPES, PHASE1J_POLICY_KINDS
from crossborder_compliance.domain.localized_metadata import validate_localized_payload
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import retrieval_models as g

OWNED_CONFIG_KINDS = PHASE1I_CONFIG_KINDS | PHASE1J_POLICY_KINDS


def validate_decision_policy(session, definition, payload):
    config = POLICY_TYPES[definition.kind].model_validate(payload)
    tenant = definition.tenant_id
    def identities(cfg):
        items = [("OBLIGATION:" + str(e.jurisdiction_id) + ":" + e.code, e.entry_id) for e in getattr(cfg, "entries", ())]
        items.extend(("PATH:" + t.path_code, t.entry_id) for t in getattr(cfg, "templates", ()))
        items.extend(("ACTION:" + t.path_code + ":" + a.code, a.entry_id) for t in getattr(cfg, "templates", ()) for a in t.actions)
        if len({k for k, _ in items}) != len(items) or len({v for _, v in items}) != len(items):
            raise ValueError("ambiguous stable policy entry identity")
        return dict(items)
    current = identities(config)
    previous = session.scalars(select(m.MetadataVersionEntity).where(m.MetadataVersionEntity.tenant_id == tenant, m.MetadataVersionEntity.definition_id == definition.definition_id, m.MetadataVersionEntity.lifecycle_status.in_(("APPROVED", "ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED")))).all()
    for version in previous:
        old = identities(POLICY_TYPES[definition.kind].model_validate(version.payload_json))
        if any(current[k] != old[k] for k in current.keys() & old.keys()) or any(k != old_key for k, v in current.items() for old_key, old_v in old.items() if v == old_v):
            raise ValueError("stable policy entry identity cannot be reassigned")
    for ident in config.jurisdiction_ids:
        if scoped(session, b.JurisdictionEntity, ident, tenant).status != "ACTIVE":
            raise ValueError("disabled policy jurisdiction")
    if definition.kind == "OBLIGATION_POLICY":
        for entry in config.entries:
            d = metadata_ref(session, entry.applicability_config_id, tenant, "APPLICABILITY_CONFIG")
            v = scoped(session, m.MetadataVersionEntity, d.active_version_id, tenant)
            parent = CONFIG_TYPES["APPLICABILITY_CONFIG"].model_validate(v.payload_json)
            if parent.jurisdiction_id != entry.jurisdiction_id or not set(entry.required_rule_ids) <= set(parent.required_rule_ids) or not set(entry.legal_basis_ids) <= set(parent.legal_basis_ids):
                raise ValueError("obligation binding outside canonical applicability")
            for ident in entry.legal_basis_ids:
                basis = scoped(session, b.LegalBasisItemEntity, ident, tenant)
                if basis.jurisdiction_id != str(entry.jurisdiction_id):
                    raise ValueError("obligation legal-basis jurisdiction mismatch")
            for ident in entry.responsible_party_ids:
                scoped(session, b.ProjectPartyEntity, ident, tenant)
    if definition.kind == "COMPLIANCE_PATH_POLICY":
        d = metadata_ref(session, config.obligation_policy_id, tenant, "OBLIGATION_POLICY")
        v = scoped(session, m.MetadataVersionEntity, d.active_version_id, tenant)
        parent = POLICY_TYPES["OBLIGATION_POLICY"].model_validate(v.payload_json)
        if set(parent.jurisdiction_ids) != set(config.jurisdiction_ids):
            raise ValueError("policy dependency jurisdiction coverage mismatch")
        allowed = {e.entry_id for e in parent.entries}
        if any(not set(t.obligation_entry_ids) <= allowed for t in config.templates):
            raise ValueError("path references unknown obligation entries")
        if any(t.prohibiting_obligation_entry_ids is not None and not set(t.prohibiting_obligation_entry_ids) <= allowed for t in config.templates):
            raise ValueError("path restriction references unknown legal obligation")
        for template in config.templates:
            for ident in template.capability_ids:
                metadata_ref(session, ident, tenant, "COUNTRY_CAPABILITY")
            for action in template.actions:
                for ident in action.responsible_party_ids:
                    scoped(session, b.ProjectPartyEntity, ident, tenant)
    if definition.kind == "RECOMMENDATION_POLICY":
        for ident, kind in ((config.path_policy_id, "COMPLIANCE_PATH_POLICY"), (config.risk_policy_id, "RISK_POLICY")):
            d = metadata_ref(session, ident, tenant, kind)
            v = scoped(session, m.MetadataVersionEntity, d.active_version_id, tenant)
            dependency = POLICY_TYPES[kind].model_validate(v.payload_json)
            if set(dependency.jurisdiction_ids) != set(config.jurisdiction_ids):
                raise ValueError("policy dependency jurisdiction coverage mismatch")
            if kind == "RISK_POLICY" and dependency.mode == "BAND_ONLY" and any(c.kind == "RISK_SCORE" for c in config.criteria):
                raise ValueError("band-only risk cannot supply numeric ranking")
    return {"payload_json": config.model_dump(mode="json"), "effective_from": config.effective_from, "effective_to": config.effective_to}


def scoped(session, model, ident, tenant):
    pk = list(model.__table__.primary_key)[0]
    row = session.scalar(select(model).where(pk == str(ident), model.tenant_id == tenant))
    if row is None:
        raise LookupError("profile reference not found")
    return row


def metadata_ref(session, ident, tenant, kind):
    row = scoped(session, m.MetadataDefinitionEntity, ident, tenant)
    if row.kind != kind:
        raise ValueError("profile reference kind mismatch")
    return row


def validate_payload(session, definition, payload):
    validate_localized_payload(payload)
    if definition.kind in PHASE1J_POLICY_KINDS:
        return validate_decision_policy(session, definition, payload)
    if definition.kind not in PHASE1I_CONFIG_KINDS:
        return {}
    config = CONFIG_TYPES[definition.kind].model_validate(payload)
    tenant = definition.tenant_id
    if hasattr(config, "jurisdiction_id"):
        jurisdiction = scoped(session, b.JurisdictionEntity, config.jurisdiction_id, tenant)
        if jurisdiction.status != "ACTIVE":
            raise ValueError("disabled profile jurisdiction")
    for field, model in (
        ("knowledge_collection_ids", m.KnowledgeCollectionEntity),
        ("prompt_config_ids", m.PromptVersionEntity),
        ("template_scope_ids", m.TemplateVersionEntity),
        ("knowledge_scope_bindings", m.KnowledgeBindingEntity),
        ("rule_scope_bindings", m.RuleBindingEntity),
        ("template_scope_bindings", m.TemplateBindingEntity),
    ):
        for ident in getattr(config, field, ()):
            scoped(session, model, ident, tenant)
    for field, kind in (
        ("capability_ids", "COUNTRY_CAPABILITY"),
        ("required_country_capability_ids", "COUNTRY_CAPABILITY"),
        ("rule_pack_ids", "RULE_PACK"),
        ("applicability_config_ids", "APPLICABILITY_CONFIG"),
        ("required_skill_ids", "SKILL"),
        ("disabled_skill_ids", "SKILL"),
        ("scenario_definition_ids", "SCENARIO"),
    ):
        for ident in getattr(config, field, ()):
            metadata_ref(session, ident, tenant, kind)
    if hasattr(config, "scenario_definition_id"):
        metadata_ref(session, config.scenario_definition_id, tenant, "SCENARIO")
        for condition in config.conditional_skill_ids:
            metadata_ref(session, condition.skill_id, tenant, "SKILL")
        if config.evidence_requirement_profile_id:
            policy = g.POLICY_MODELS["sufficiency"]
            if not session.scalar(
                select(policy).where(
                    policy.tenant_id == tenant,
                    policy.policy_id == str(config.evidence_requirement_profile_id),
                )
            ):
                raise LookupError("evidence requirement policy not found")
    for field in ("rule_definition_ids", "required_rule_ids"):
        for ident in getattr(config, field, ()):
            scoped(session, m.RuleDefinitionEntity, ident, tenant)
    if definition.kind == "APPLICABILITY_CONFIG":
        version = scoped(
            session, k.KnowledgeDocumentVersionEntity, config.knowledge_version_id, tenant
        )
        if version.lifecycle not in {"APPROVED", "ACTIVE"} or not version.approved_by:
            raise ValueError("applicability source requires approved canonical knowledge")
        for ident in config.regulatory_structure_node_ids:
            node = scoped(session, b.RegulatoryStructureNodeEntity, ident, tenant)
            if node.regulation_version_ref != str(
                config.knowledge_version_id
            ) or node.jurisdiction_id != str(config.jurisdiction_id):
                raise ValueError("wrong canonical regulation structure")
            extension = session.scalar(
                select(k.KnowledgeStructureNodeEntity).where(
                    k.KnowledgeStructureNodeEntity.tenant_id == tenant,
                    k.KnowledgeStructureNodeEntity.regulatory_structure_node_id == str(ident),
                    k.KnowledgeStructureNodeEntity.knowledge_version_id
                    == str(config.knowledge_version_id),
                )
            )
            if extension is None:
                raise ValueError("regulatory node needs canonical knowledge extension")
        for ident in config.legal_basis_ids:
            basis = scoped(session, b.LegalBasisItemEntity, ident, tenant)
            if (
                basis.jurisdiction_id != str(config.jurisdiction_id)
                or basis.regulatory_structure_node_id
                not in {str(v) for v in config.regulatory_structure_node_ids}
                or not basis.official_source
                or not basis.citation_locator
            ):
                raise ValueError("wrong canonical legal basis")
    return {
        "payload_json": config.model_dump(mode="json"),
        "effective_from": config.effective_from,
        "effective_to": config.effective_to,
    }


def lock_definition(session, definition):
    if definition.kind in OWNED_CONFIG_KINDS:
        return session.scalar(
            select(m.MetadataDefinitionEntity)
            .where(
                m.MetadataDefinitionEntity.definition_id == definition.definition_id,
                m.MetadataDefinitionEntity.tenant_id == definition.tenant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    return definition


def transition_validation(session, row, actor, target):
    if target in {"PENDING_REVIEW", "APPROVED", "ACTIVE"}:
        validate_localized_payload(row.payload_json)
    definition = scoped(session, m.MetadataDefinitionEntity, row.definition_id, row.tenant_id)
    if definition.kind not in OWNED_CONFIG_KINDS:
        return row
    lock_definition(session, definition)
    row = session.scalar(
        select(m.MetadataVersionEntity)
        .where(
            m.MetadataVersionEntity.version_id == row.version_id,
            m.MetadataVersionEntity.tenant_id == row.tenant_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if target in {"PENDING_REVIEW", "APPROVED", "ACTIVE"}:
        validate_payload(session, definition, row.payload_json)
    if target == "APPROVED" and actor == row.created_by:
        raise ValueError("independent Phase1I configuration review required")
    if target == "ACTIVE" and not row.approved_by:
        raise ValueError("Phase1I configuration must retain approved review")
    return row
