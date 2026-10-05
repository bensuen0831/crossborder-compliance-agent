"""Focused helpers of PostgresCountryComplianceRepository, not another repository layer."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, text

from crossborder_compliance.application.country_compliance_services import ApplicabilityRequest
from crossborder_compliance.application.decision_services import DecisionRequest, calculate
from crossborder_compliance.domain.compliance_profiles import effective
from crossborder_compliance.domain.decision_contracts import (
    ENVELOPE_TYPES,
    CapabilityDependency,
    LegalSupport,
    PinRef,
    canonical,
    digest,
    result_digest,
    unique,
)
from crossborder_compliance.domain.decision_engine import (
    AuthorizedFact,
    DecisionIdentity,
    PinnedDecisionPolicy,
    PreparedDecisionInput,
)
from crossborder_compliance.domain.decision_policies import POLICY_TYPES
from crossborder_compliance.domain.retrieval import RAGContextPack
from crossborder_compliance.infrastructure.persistence import applicability_models as i
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import decision_models as j
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b


def authorize(repo, project, operation):
    if not repo.context.permission.system and (
        f"decision:{operation}" not in repo.context.permission.scopes
        or f"project:{project}:comply" not in repo.context.permission.scopes
    ):
        raise LookupError("decision resource not found")


def scope(repo, session, project, snapshot):
    snap, ctx = repo.snapshot(session, project, snapshot, operation="read")
    jurisdictions = session.scalars(
        select(c.JurisdictionContextEntity).where(
            c.JurisdictionContextEntity.tenant_id == repo.tenant,
            c.JurisdictionContextEntity.project_id == str(project),
            c.JurisdictionContextEntity.version == ctx.context_resolution_version,
        )
    ).all()
    if not jurisdictions or any(
        v.validation_status != "VALIDATED" or v.review_required for v in jurisdictions
    ):
        raise ValueError("unresolved required jurisdiction coverage")
    facts = session.scalars(
        select(c.BusinessFactEntity).where(
            c.BusinessFactEntity.tenant_id == repo.tenant,
            c.BusinessFactEntity.project_id == str(project),
            c.BusinessFactEntity.version == ctx.context_resolution_version,
        )
    ).all()
    signatures = [
        {
            "id": f.fact_id,
            "code": f.fact_type,
            "value": f.normalized_value_json,
            "validation": f.validation_status,
            "review": f.review_required,
            "confidence": str(f.confidence),
        }
        for f in facts
    ]
    context_digest = digest(
        {
            "project_version": snap.project_version_id,
            "context_version": ctx.context_resolution_version,
            "jurisdictions": sorted(v.jurisdiction_id for v in jurisdictions),
            "facts": sorted(signatures, key=lambda f: f["id"]),
        }
    )
    return snap, ctx, unique(UUID(v.jurisdiction_id) for v in jurisdictions), facts, context_digest


def pins(repo, session, snapshot):
    return session.scalars(
        select(m.AnalysisSnapshotRegistryPinEntity).where(
            m.AnalysisSnapshotRegistryPinEntity.tenant_id == repo.tenant,
            m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(snapshot),
        )
    ).all()


def pin_ref(row):
    return PinRef(
        pin_id=row.pin_id,
        kind=row.pin_type,
        object_id=row.object_id,
        version_id=row.version_id,
        version_no=row.version_no,
    )


def load_policy(repo, session, pin, when, historical=True):
    definition = repo.get(session, m.MetadataDefinitionEntity, pin.object_id)
    version = repo.get(session, m.MetadataVersionEntity, pin.version_id)
    kind = pin.pin_type.removeprefix("PHASE1J_")
    allowed = {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"} if historical else {"ACTIVE"}
    if (
        definition.kind != kind
        or version.definition_id != pin.object_id
        or version.version_no != pin.version_no
        or version.lifecycle_status not in allowed
        or not version.approved_by
        or not version.published_at
    ):
        raise ValueError("unpublished or mismatched decision policy")
    config = POLICY_TYPES[kind].model_validate(version.payload_json)
    if not effective(config, when):
        raise ValueError("ineffective decision policy")
    if (
        not repo.context.permission.system
        and not set(config.permission_scopes) <= repo.context.permission.scopes
    ):
        raise LookupError("decision policy not found")
    if not session.scalar(
        select(m.AdminPublishRecordEntity).where(
            m.AdminPublishRecordEntity.tenant_id == repo.tenant,
            m.AdminPublishRecordEntity.object_kind == kind,
            m.AdminPublishRecordEntity.version_id == pin.version_id,
        )
    ):
        raise ValueError("missing durable decision-policy publication")
    return PinnedDecisionPolicy(pin=pin_ref(pin).model_copy(update={"kind": kind}), config=config)


def validate_closure(policies):
    by_kind = {p.pin.kind: p for p in policies}
    for kind, attributes in {
        "COMPLIANCE_PATH_POLICY": (("obligation_policy_id", "OBLIGATION_POLICY"),),
        "RECOMMENDATION_POLICY": (
            ("path_policy_id", "COMPLIANCE_PATH_POLICY"),
            ("risk_policy_id", "RISK_POLICY"),
        ),
    }.items():
        if kind not in by_kind:
            continue
        for field, target in attributes:
            if (
                target not in by_kind
                or getattr(by_kind[kind].config, field) != by_kind[target].pin.object_id
            ):
                raise ValueError("decision policy dependency closure mismatch")


def initialize(repo, project, snapshot):
    authorize(repo, project, "execute")
    with repo.sessions() as s, s.begin():
        repo.snapshot(s, project, snapshot, True, operation="read")
        snap, context, jurisdictions, _, context_digest = scope(repo, s, project, snapshot)
        existing = pins(repo, s, snapshot)
        marker = [p for p in existing if p.pin_type == "PHASE1J_INITIALIZATION"]
        if marker:
            if marker[0].logical_key != context_digest:
                raise ValueError("formal context changed; new snapshot required")
            return {
                "status": "PINNED",
                "pins": [pin_ref(p) for p in existing if p.pin_type.startswith("PHASE1J_")],
            }
        if not set(map(str, jurisdictions)) <= {
            p.logical_key for p in existing if p.pin_type == "PHASE1I_CONFIGURATION"
        }:
            raise ValueError("explicit Phase1I initialization required first")
        selected = []
        for kind, cls in POLICY_TYPES.items():
            rows = s.execute(
                select(m.MetadataDefinitionEntity, m.MetadataVersionEntity)
                .join(
                    m.MetadataVersionEntity,
                    m.MetadataDefinitionEntity.active_version_id
                    == m.MetadataVersionEntity.version_id,
                )
                .where(
                    m.MetadataDefinitionEntity.tenant_id == repo.tenant,
                    m.MetadataVersionEntity.tenant_id == repo.tenant,
                    m.MetadataDefinitionEntity.kind == kind,
                    m.MetadataDefinitionEntity.status == "ACTIVE",
                    m.MetadataVersionEntity.lifecycle_status == "ACTIVE",
                )
            ).all()
            for definition, version in rows:
                cfg = cls.model_validate(version.payload_json)
                if set(cfg.jurisdiction_ids) != set(jurisdictions) or not effective(
                    cfg, snap.analysis_as_of_date
                ):
                    continue
                if (
                    not repo.context.permission.system
                    and not set(cfg.permission_scopes) <= repo.context.permission.scopes
                ):
                    continue
                row = m.AnalysisSnapshotRegistryPinEntity(
                    pin_id=str(uuid4()),
                    tenant_id=repo.tenant,
                    analysis_snapshot_id=str(snapshot),
                    pin_type="PHASE1J_" + kind,
                    logical_key=definition.definition_id,
                    object_id=definition.definition_id,
                    version_id=version.version_id,
                    version_no=version.version_no,
                )
                policy = load_policy(repo, s, row, snap.analysis_as_of_date, historical=False)
                selected.append((row, policy))
        if len({p.pin.kind for _, p in selected}) == len(selected):
            validate_closure([p for _, p in selected])
        for row, _ in selected:
            s.add(row)
        for original in existing:
            if original.pin_type.startswith("PHASE1J_"):
                raise ValueError("incomplete existing J initialization")
            s.add(
                m.AnalysisSnapshotRegistryPinEntity(
                    pin_id=str(uuid4()),
                    tenant_id=repo.tenant,
                    analysis_snapshot_id=str(snapshot),
                    pin_type="PHASE1J_DEPENDENCY",
                    logical_key=original.pin_id,
                    object_id=original.object_id,
                    version_id=original.version_id,
                    version_no=original.version_no,
                )
            )
        s.add(
            m.AnalysisSnapshotRegistryPinEntity(
                pin_id=str(uuid4()),
                tenant_id=repo.tenant,
                analysis_snapshot_id=str(snapshot),
                pin_type="PHASE1J_INITIALIZATION",
                logical_key=context_digest,
                object_id=str(snapshot),
                version_id=str(snapshot),
                version_no=context.context_resolution_version,
            )
        )
        s.flush()
        return {
            "status": "PINNED",
            "pins": [
                pin_ref(p) for p in pins(repo, s, snapshot) if p.pin_type.startswith("PHASE1J_")
            ],
        }


def _loaded(repo, session, kind, ident, operation="read"):
    row = repo.get(session, j.MODELS[kind], ident)
    authorize(repo, row.project_id, operation)
    if row.owner_actor_id != repo.context.permission.actor_id:
        raise LookupError("decision resource not found")
    result = ENVELOPE_TYPES[kind].model_validate(row.result_json)
    if result.stage_kind != kind or str(result.result_id) != row.result_id:
        raise ValueError("stored stage identity mismatch")
    return row, result


def prepare(repo, request, operation="execute", memo=None):
    authorize(repo, request.project_id, operation)
    memo = memo if memo is not None else {}
    applications, prepared = [], []
    for ident in sorted(request.applicability_result_ids, key=str):
        saved = repo.read(ident)
        with repo.sessions() as s:
            row = repo.get(s, i.RegulationApplicabilityResultEntity, ident)
            original = ApplicabilityRequest.model_validate(row.request_json)
        applications.append(saved)
        prepared.append(repo.prepare(original, operation="read"))
    with repo.sessions() as s:
        snap, ctx, jurisdictions, facts, context_digest = scope(
            repo, s, request.project_id, request.analysis_snapshot_id
        )
        allpins = pins(repo, s, request.analysis_snapshot_id)
        jpins = [p for p in allpins if p.pin_type.startswith("PHASE1J_")]
        marker = [p for p in jpins if p.pin_type == "PHASE1J_INITIALIZATION"]
        if len(marker) != 1 or marker[0].logical_key != context_digest:
            raise ValueError("explicit unchanged J initialization required")
        deps = {
            p.logical_key: (p.object_id, p.version_id, p.version_no)
            for p in jpins
            if p.pin_type == "PHASE1J_DEPENDENCY"
        }
        expected = {
            p.pin_id: (p.object_id, p.version_id, p.version_no)
            for p in allpins
            if not p.pin_type.startswith("PHASE1J_")
        }
        if deps != expected:
            raise ValueError("upstream pin closure changed; new snapshot required")
        expected_configs = set()
        for pin in allpins:
            if pin.pin_type != "PHASE1I_APPLICABILITY_CONFIG":
                continue
            _, cfg = repo.published(s, pin, "APPLICABILITY_CONFIG", snap.analysis_as_of_date)
            if request.subject_type == "SCENARIO" and (
                cfg.requires_classification
                or (
                    cfg.scenario_definition_ids
                    and request.subject_id not in cfg.scenario_definition_ids
                )
            ):
                continue
            expected_configs.add(UUID(pin.object_id))
        if {a.applicability_config_id for a in applications} != expected_configs or len(
            applications
        ) != len(expected_configs):
            raise ValueError("required applicability configuration coverage cannot be narrowed")
        policies = tuple(
            load_policy(repo, s, p, snap.analysis_as_of_date)
            for p in jpins
            if p.pin_type.removeprefix("PHASE1J_") in POLICY_TYPES
        )
        if len({p.pin.kind for p in policies}) == len(policies):
            validate_closure(policies)
        pinrefs = tuple(
            sorted((p.pin for p in policies), key=lambda p: (p.kind, str(p.object_id)))
        ) + tuple(
            sorted(
                (
                    pin_ref(p)
                    for p in jpins
                    if p.pin_type in {"PHASE1J_INITIALIZATION", "PHASE1J_DEPENDENCY"}
                ),
                key=lambda p: str(p.pin_id),
            )
        )
        for p in policies:
            entries = getattr(p.config, "entries", ())
            actions = [a for t in getattr(p.config, "templates", ()) for a in t.actions]
            for item in (*entries, *actions):
                for ident in getattr(item, "responsible_party_ids", ()):
                    if repo.get(s, b.ProjectPartyEntity, ident).project_id != str(
                        request.project_id
                    ):
                        raise LookupError("decision party outside project")
        identity = DecisionIdentity(
            tenant_id=UUID(repo.tenant),
            project_id=request.project_id,
            analysis_snapshot_id=request.analysis_snapshot_id,
            project_version_id=UUID(snap.project_version_id),
            context_version=ctx.context_resolution_version,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            data_item_ids=unique(v for a in applications for v in a.data_item_ids),
            data_flow_ids=unique(v for a in applications for v in a.data_flow_ids),
            scenario_definition_ids=unique(
                v for a in applications for v in a.scenario_definition_ids
            ),
            jurisdiction_ids=jurisdictions,
            analysis_as_of_date=snap.analysis_as_of_date,
        )
    evidence_ids = unique(e for p in prepared for e in p.evidence_ids)
    pack_citation_ids = unique(
        item.citation_id
        for p in prepared
        for item in RAGContextPack.model_validate(
            repo.country_evidence(UUID(p.sufficiency.retrieval_run_id), operation="read")[
                "rag_context_pack"
            ]
        ).evidence_pack.items
    )
    with repo.sessions() as s:
        citation_ids = unique(
            UUID(v)
            for v in s.scalars(
                select(b.CitationEntity.citation_id).where(
                    b.CitationEntity.tenant_id == repo.tenant,
                    b.CitationEntity.citation_id.in_(pack_citation_ids),
                    b.CitationEntity.evidence_id.in_(tuple(map(str, evidence_ids))),
                )
            )
        )
    by_code = {}
    for f in facts:
        if f.validation_status != "VALIDATED" or f.review_required:
            continue
        key = f.fact_type.lower()
        value = f.normalized_value_json
        if type(value) is float:
            value = Decimal(str(value))
        if key in by_code:
            raise ValueError("ambiguous formal fact code")
        by_code[key] = AuthorizedFact(
            code=key, value=value, fact_refs=(UUID(f.fact_id),), evidence_ids=evidence_ids
        )
    capabilities = {}
    for jurisdiction in jurisdictions:
        resolved = repo.resolve_profile(
            request.project_id, request.analysis_snapshot_id, jurisdiction, operation="read"
        )
        configured = (
            {c.profile_id for c in resolved.capabilities} if resolved.status == "READY" else set()
        )
        for cap in resolved.capabilities:
            capabilities[cap.profile_id] = CapabilityDependency(
                capability_id=cap.profile_id,
                version_id=cap.version_id,
                availability="AVAILABLE" if cap.profile_id in configured else "UNKNOWN",
            )
    support = LegalSupport(
        applicability_result_ids=unique(a.applicability_result_id for a in applications),
        rule_hit_ids=unique(h.rule_hit_id for p in prepared for h in p.rule_hits if h.matched),
        rule_version_ids=unique(
            h.rule_version_id for p in prepared for h in p.rule_hits if h.matched
        ),
        legal_basis_ids=unique(v for a in applications for v in a.legal_basis_ids),
        evidence_ids=evidence_ids,
        evidence_pack_ids=unique(v for a in applications for v in a.evidence_pack_ids),
        retrieval_run_ids=unique(UUID(p.sufficiency.retrieval_run_id) for p in prepared),
        knowledge_version_ids=unique(a.regulation_version_ref for a in applications),
        structure_node_ids=unique(v for a in applications for v in a.regulatory_structure_node_ids),
        citation_locators=unique(
            v for p in prepared for v in p.canonical_legal_reference.citation_locators
        ),
        fact_refs=unique(
            UUID(f.fact_id)
            for f in facts
            if f.validation_status == "VALIDATED" and not f.review_required
        ),
    )
    support = support.model_copy(update={"citation_ids": citation_ids})
    hits = {}
    for p in prepared:
        for hit in p.rule_hits:
            if hit.rule_hit_id in hits and digest(hits[hit.rule_hit_id]) != digest(hit):
                raise ValueError("contradictory canonical RuleHit payloads")
            hits[hit.rule_hit_id] = hit
    inputs = PreparedDecisionInput(
        identity=identity,
        applicability=tuple(applications),
        rule_hits=tuple(hits.values()),
        facts=tuple(sorted(by_code.values(), key=lambda f: f.code)),
        authorized_evidence_ids=evidence_ids,
        support=support,
        policies=policies,
        pins=pinrefs,
        capabilities=tuple(sorted(capabilities.values(), key=lambda c: str(c.capability_id))),
        prepared_at=datetime.now(timezone.utc),
        actor_ref=repo.context.permission.actor_id,
        request_id=request.idempotency_key,
        correlation_id=str(request.analysis_snapshot_id),
    )
    parents = {}
    for upstream in request.upstream_refs:
        key = (upstream.kind, upstream.result_id)
        if key not in memo:
            memo[key] = read(repo, upstream.kind, upstream.result_id, memo)
        parents[upstream.kind] = memo[key]
    if any(
        tuple(r.result_id for r in p.provenance.origins if r.kind == "APPLICABILITY")
        != tuple(sorted(request.applicability_result_ids, key=str))
        for p in parents.values()
    ):
        # Compare sets below: provenance ordering is canonical but not a legal ranking.
        if any(
            {r.result_id for r in p.provenance.origins if r.kind == "APPLICABILITY"}
            != set(request.applicability_result_ids)
            for p in parents.values()
        ):
            raise ValueError("upstream applicability provenance mismatch")
    return inputs, parents


def read(repo, stage, ident, memo=None):
    with repo.sessions() as s:
        row, saved = _loaded(repo, s, stage, ident)
        request = DecisionRequest.model_validate(row.request_json)
        if request.stage_kind != stage:
            raise ValueError("stored request stage mismatch")
    inputs, parents = prepare(repo, request, "read", memo)
    current = calculate(stage, inputs, parents)
    if result_digest(saved) != result_digest(current):
        raise ValueError("saved decision no longer revalidates")
    return saved


def save(repo, request, result):
    authorize(repo, request.project_id, "execute")
    with repo.sessions() as s, s.begin():
        # H revalidation locks the snapshot in its own transaction. Serialize J
        # writers within the request-key project scope (including different
        # snapshots), then acquire the shared row lock after H has returned.
        lock_key = int(
            digest(
                {
                    "namespace": "PHASE1J",
                    "tenant": repo.tenant,
                    "project": request.project_id,
                }
            )[:15],
            16,
        )
        s.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        inputs, parents = prepare(repo, request)
        repo.snapshot(s, request.project_id, request.analysis_snapshot_id, True, operation="read")
        _, _, _, _, current_context = scope(
            repo, s, request.project_id, request.analysis_snapshot_id
        )
        current_pins = pins(repo, s, request.analysis_snapshot_id)
        if not any(
            p.pin_type == "PHASE1J_INITIALIZATION" and p.logical_key == current_context
            for p in current_pins
        ):
            raise ValueError("formal context changed during evaluation; new snapshot required")
        actual = {
            (
                p.pin_type.removeprefix("PHASE1J_")
                if p.pin_type.removeprefix("PHASE1J_") in POLICY_TYPES
                else p.pin_type,
                p.object_id,
                p.version_id,
                p.version_no,
                p.pin_id,
            )
            for p in current_pins
            if p.pin_type.startswith("PHASE1J_")
        }
        expected = {
            (p.kind, str(p.object_id), str(p.version_id), p.version_no, str(p.pin_id))
            for p in inputs.pins
        }
        if actual != expected:
            raise ValueError("decision pins changed during evaluation")
        current = calculate(request.stage_kind, inputs, parents)
        if result_digest(result) != result_digest(current):
            raise ValueError("decision result differs from authorized computation")
        model = j.MODELS[request.stage_kind]
        alias = s.scalar(
            select(j.DecisionRequestKeyEntity).where(
                j.DecisionRequestKeyEntity.tenant_id == repo.tenant,
                j.DecisionRequestKeyEntity.project_id == str(request.project_id),
                j.DecisionRequestKeyEntity.stage_kind == request.stage_kind,
                j.DecisionRequestKeyEntity.idempotency_key == request.idempotency_key,
            )
        )
        if alias and alias.input_fingerprint != result.input_digest:
            raise ValueError("idempotency key fingerprint mismatch")
        existing = s.scalar(
            select(model).where(
                model.tenant_id == repo.tenant,
                model.project_id == str(request.project_id),
                model.analysis_snapshot_id == str(request.analysis_snapshot_id),
                model.subject_type == request.subject_type,
                model.subject_id == str(request.subject_id),
                model.input_fingerprint == result.input_digest,
            )
        )
        if existing:
            _, saved = _loaded(repo, s, request.stage_kind, existing.result_id, "execute")
            if result_digest(saved) != result_digest(result):
                raise ValueError("concurrent competing formal result")
            result = saved
        else:
            p = inputs.policy(
                {
                    "OBLIGATION": "OBLIGATION_POLICY",
                    "CANDIDATE_PATH": "COMPLIANCE_PATH_POLICY",
                    "RISK": "RISK_POLICY",
                    "RECOMMENDATION": "RECOMMENDATION_POLICY",
                    "FINAL_PATH": "RECOMMENDATION_POLICY",
                }[request.stage_kind]
            )
            data = {k: getattr(result, k) for k in (*j.SCOPE, "result_id", "analysis_as_of_date")}
            data = {k: str(v) if isinstance(v, UUID) else v for k, v in data.items()}
            for kind in j.PARENTS[request.stage_kind]:
                data[kind.lower() + "_result_id"] = str(parents[kind].result_id)
            s.add(
                model(
                    **data,
                    jurisdiction_ids=canonical(result.jurisdiction_ids),
                    policy_version_id=str(p.pin.version_id) if p else None,
                    upstream_refs=canonical(result.upstream_refs),
                    pins_json=canonical(result.pins),
                    provenance_json=canonical(result.provenance),
                    input_fingerprint=result.input_digest,
                    pins_digest=result.pins_digest,
                    contract_version=result.contract_version,
                    engine_version=result.engine_version,
                    owner_actor_id=repo.context.permission.actor_id,
                    summary_status=result.summary_status,
                    request_json=request.model_dump(mode="json"),
                    result_json=canonical(result),
                )
            )
            s.flush()
            if request.stage_kind == "OBLIGATION":
                for ident in request.applicability_result_ids:
                    s.add(
                        j.ObligationApplicabilityLinkEntity(
                            link_id=str(uuid4()),
                            tenant_id=repo.tenant,
                            obligation_result_id=str(result.result_id),
                            applicability_result_id=str(ident),
                        )
                    )
        if alias is None:
            s.add(
                j.DecisionRequestKeyEntity(
                    request_key_id=str(uuid4()),
                    tenant_id=repo.tenant,
                    project_id=str(request.project_id),
                    stage_kind=request.stage_kind,
                    idempotency_key=request.idempotency_key,
                    input_fingerprint=result.input_digest,
                    result_id=str(result.result_id),
                )
            )
        return result
