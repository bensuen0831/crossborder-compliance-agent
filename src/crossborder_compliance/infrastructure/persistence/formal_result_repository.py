"""Owning extensions of canonical CountryComplianceRepository; no parallel store."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text

from crossborder_compliance.application.decision_services import DecisionRequest
from crossborder_compliance.application.formal_result_services import (
    CALCULATE,
    FormalAuthorityRequest,
)
from crossborder_compliance.domain.compliance_profiles import effective
from crossborder_compliance.domain.decision_contracts import (
    LegalSupport,
    canonical,
    digest,
    result_digest,
    unique,
)
from crossborder_compliance.domain.formal_result_contracts import (
    AUTHORITY_ENVELOPES,
    AuthorityIdentity,
)
from crossborder_compliance.domain.formal_result_engine import (
    PinnedAuthorityPolicy,
    PinnedTemplate,
    PreparedAuthorityInput,
)
from crossborder_compliance.domain.formal_result_policies import FORMAL_RESULT_POLICY_TYPES
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import decision_models as j
from crossborder_compliance.infrastructure.persistence import formal_result_models as a
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.context_temporal import (
    exact_item_detail,
    flow_item_ids,
)
from crossborder_compliance.infrastructure.persistence.decision_repository import (
    authorize,
    pin_ref,
    pins,
)

PREFIX = "PHASE1C0_"


def context_identity(repo, s, project, snapshot):
    snap, pin = repo.snapshot(s, project, snapshot, operation="read")
    run = repo.get(s, c.ContextResolutionRunEntity, pin.context_resolution_run_id)
    if run.project_id != str(project) or run.version != pin.context_resolution_version:
        raise ValueError("exact formal context identity mismatch")
    jurisdictions = s.scalars(
        select(c.JurisdictionContextEntity).where(
            c.JurisdictionContextEntity.tenant_id == repo.tenant,
            c.JurisdictionContextEntity.project_id == str(project),
            c.JurisdictionContextEntity.version == pin.context_resolution_version,
        )
    ).all()
    signature = digest(
        {
            "snapshot": str(snapshot),
            "project_version": snap.project_version_id,
            "run": run.context_resolution_run_id,
            "context": pin.context_resolution_version,
            "inventory": pin.data_inventory_version,
            "flow": pin.data_flow_version,
            "jurisdictions": sorted(
                (
                    x.jurisdiction_context_id,
                    x.jurisdiction_id,
                    x.context_type,
                    x.validation_status,
                    x.review_required,
                )
                for x in jurisdictions
            ),
        }
    )
    return snap, pin, run, jurisdictions, signature


def load_policy(repo, s, pin, when, historical=True):
    definition = repo.get(s, m.MetadataDefinitionEntity, pin.object_id)
    version = repo.get(s, m.MetadataVersionEntity, pin.version_id)
    kind = pin.pin_type.removeprefix(PREFIX)
    states = {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"} if historical else {"ACTIVE"}
    if (
        definition.kind != kind
        or version.definition_id != definition.definition_id
        or version.version_no != pin.version_no
        or version.lifecycle_status not in states
        or not version.approved_by
        or not version.published_at
    ):
        raise ValueError("unpublished/mismatched formal authority policy")
    cfg = FORMAL_RESULT_POLICY_TYPES[kind].model_validate(version.payload_json)
    if not effective(cfg, when):
        raise ValueError("ineffective formal authority policy")
    if (
        not repo.context.permission.system
        and not set(cfg.permission_scopes) <= repo.context.permission.scopes
    ):
        raise LookupError("formal authority policy not found")
    if not s.scalar(
        select(m.AdminPublishRecordEntity).where(
            m.AdminPublishRecordEntity.tenant_id == repo.tenant,
            m.AdminPublishRecordEntity.object_kind == kind,
            m.AdminPublishRecordEntity.version_id == pin.version_id,
        )
    ):
        raise ValueError("formal authority policy lacks durable publication")
    return PinnedAuthorityPolicy(pin=pin_ref(pin).model_copy(update={"kind": kind}), config=cfg)


def initialize(repo, project, snapshot):
    authorize(repo, project, "execute")
    with repo.sessions() as s, s.begin():
        repo.snapshot(s, project, snapshot, True, operation="read")
        snap, ctx, run, jurisdictions, signature = context_identity(repo, s, project, snapshot)
        old = pins(repo, s, snapshot)
        marker = [p for p in old if p.pin_type == PREFIX + "INITIALIZATION"]
        if marker:
            if len(marker) != 1 or marker[0].logical_key != signature:
                raise ValueError("C0 context changed; new snapshot required")
            return {
                "status": "PINNED",
                "pins": tuple(pin_ref(p) for p in old if p.pin_type.startswith(PREFIX)),
            }
        if any(p.pin_type == "PHASE1J_INITIALIZATION" for p in old):
            raise ValueError("J pin closure already sealed; new snapshot required")
        coverage = {UUID(j.jurisdiction_id) for j in jurisdictions if j.jurisdiction_id}
        chosen = []
        for kind, cls in FORMAL_RESULT_POLICY_TYPES.items():
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
                if set(cfg.jurisdiction_ids) != coverage or not effective(
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
                    pin_type=PREFIX + kind,
                    logical_key=definition.definition_id,
                    object_id=definition.definition_id,
                    version_id=version.version_id,
                    version_no=version.version_no,
                )
                selected = load_policy(repo, s, row, snap.analysis_as_of_date, historical=False)
                chosen.append(selected)
                s.add(row)
                if kind == "DOCUMENT_REQUIREMENT_POLICY":
                    for entry in cfg.entries:
                        if not entry.template_binding_id:
                            continue
                        binding = repo.get(s, m.TemplateBindingEntity, entry.template_binding_id)
                        if (
                            binding.binding_ref != str(entry.entry_id)
                            or binding.binding_type != "DOCUMENT_REQUIREMENT"
                            or not repo.date_valid(binding, snap.analysis_as_of_date)
                        ):
                            continue
                        template = repo.get(s, m.TemplateVersionEntity, binding.template_version_id)
                        if template.lifecycle_status != "ACTIVE" or not repo.date_valid(
                            template, snap.analysis_as_of_date
                        ):
                            continue
                        # Reuse the canonical template publication/authorization validator.
                        repo.validate_resource(
                            s,
                            m.TemplateVersionEntity,
                            template.template_version_id,
                            snap.analysis_as_of_date,
                        )
                        s.add(
                            m.AnalysisSnapshotRegistryPinEntity(
                                pin_id=str(uuid4()),
                                tenant_id=repo.tenant,
                                analysis_snapshot_id=str(snapshot),
                                pin_type=PREFIX + "TEMPLATE",
                                logical_key=str(entry.entry_id),
                                object_id=str(entry.template_binding_id),
                                version_id=template.template_version_id,
                                version_no=template.version_no,
                            )
                        )
        # Flush dependencies before the initialization marker seals the set.
        s.flush()
        s.add(
            m.AnalysisSnapshotRegistryPinEntity(
                pin_id=str(uuid4()),
                tenant_id=repo.tenant,
                analysis_snapshot_id=str(snapshot),
                pin_type=PREFIX + "INITIALIZATION",
                logical_key=signature,
                object_id=str(snapshot),
                version_id=str(snapshot),
                version_no=ctx.context_resolution_version,
            )
        )
        s.flush()
        return {
            "status": "PINNED",
            "pins": tuple(
                pin_ref(p) for p in pins(repo, s, snapshot) if p.pin_type.startswith(PREFIX)
            ),
        }


def validated_reference(repo, request, kind, ident):
    if not ident:
        return None
    with repo.sessions() as s:
        model = j.MODELS[kind] if kind in j.MODELS else a.MODELS[kind]
        row = repo.get(s, model, ident)
        if (
            row.project_id,
            row.analysis_snapshot_id,
            row.subject_type,
            row.subject_id,
            row.owner_actor_id,
        ) != (
            str(request.project_id),
            str(request.analysis_snapshot_id),
            request.subject_type,
            str(request.subject_id),
            repo.context.permission.actor_id,
        ):
            raise LookupError("formal authority upstream not found")
    return row


def prepare(repo, request):
    authorize(repo, request.project_id, "read")
    with repo.sessions() as s:
        snap, ctx, run, jurisdictions, signature = context_identity(
            repo, s, request.project_id, request.analysis_snapshot_id
        )
        allpins = pins(repo, s, request.analysis_snapshot_id)
        marker = [p for p in allpins if p.pin_type == PREFIX + "INITIALIZATION"]
        if marker and (len(marker) != 1 or marker[0].logical_key != signature):
            raise ValueError("C0 exact context changed")
        policies = (
            tuple(
                load_policy(repo, s, p, snap.analysis_as_of_date)
                for p in allpins
                if p.pin_type.removeprefix(PREFIX) in FORMAL_RESULT_POLICY_TYPES
                and p.pin_type.startswith(PREFIX)
            )
            if marker
            else ()
        )
        templates = []
        for p in allpins:
            if p.pin_type != PREFIX + "TEMPLATE":
                continue
            binding = repo.get(s, m.TemplateBindingEntity, p.object_id)
            version = repo.validate_resource(
                s, m.TemplateVersionEntity, p.version_id, snap.analysis_as_of_date, historical=True
            )
            if binding.template_version_id != p.version_id or version.version_no != p.version_no:
                raise ValueError("template exact pin mismatch")
            templates.append(
                PinnedTemplate(
                    entry_id=UUID(p.logical_key),
                    binding_id=UUID(p.object_id),
                    version_id=UUID(p.version_id),
                )
            )
        reasons = []
        if run.conflict_count:
            reasons.append("FACT_CONFLICT")
        products = s.scalars(
            select(c.ProductScopeResolutionEntity).where(
                c.ProductScopeResolutionEntity.tenant_id == repo.tenant,
                c.ProductScopeResolutionEntity.project_id == str(request.project_id),
                c.ProductScopeResolutionEntity.version == ctx.product_context_version,
            )
        ).all()
        if any(p.resolution_status == "CONFLICTED" or p.review_required for p in products):
            reasons.insert(0, "PRODUCT_CONTEXT_CONFLICT")
        if any(
            not row.jurisdiction_id or row.validation_status != "VALIDATED" or row.review_required
            for row in jurisdictions
        ):
            reasons.append("JURISDICTION_UNRESOLVED")
        if run.unresolved_count or run.review_required_count:
            if not reasons:
                reasons.append("FACT_CONFLICT")
        item_ids = ()
        flow_ids = ()
        endpoint_contexts = None
        if request.subject_type == "DATA_ITEM":
            row = repo.get(s, b.DataItemEntity, request.subject_id)
            if row.project_id != str(request.project_id):
                raise LookupError("formal item not found")
            detail = exact_item_detail(
                s, repo.tenant, str(request.subject_id), ctx.data_inventory_version
            )
            item_ids = (request.subject_id,)
            if detail.validation_status != "VALIDATED" or detail.review_required:
                reasons.append("FACT_CONFLICT")
        elif request.subject_type == "DATA_FLOW":
            edge = repo.get(s, b.DataFlowEdgeEntity, request.subject_id)
            detail = repo.get(s, c.DataFlowEdgeDetailEntity, request.subject_id)
            if (
                edge.project_id != str(request.project_id)
                or detail.version != ctx.data_flow_version
            ):
                raise LookupError("exact formal flow not found")
            flow_ids = (request.subject_id,)
            item_ids = tuple(
                UUID(v)
                for v in flow_item_ids(
                    s, repo.tenant, str(request.subject_id), ctx.data_inventory_version
                )
            )
            if detail.validation_status != "VALIDATED":
                reasons.append("FACT_CONFLICT")
            endpoint_contexts = []
            for node_id in (edge.source_node_id, edge.target_node_id):
                node = repo.get(s, b.DataFlowNodeEntity, node_id)
                node_detail = repo.get(s, c.DataFlowNodeDetailEntity, node_id)
                if (
                    node.project_id != str(request.project_id)
                    or node_detail.version != ctx.data_flow_version
                ):
                    raise LookupError("exact formal flow endpoint not found")
                endpoint = next(
                    (
                        j
                        for j in jurisdictions
                        if j.jurisdiction_context_id == node_detail.jurisdiction_context_id
                    ),
                    None,
                )
                if (
                    not endpoint
                    or node_detail.validation_status != "VALIDATED"
                    or endpoint.validation_status != "VALIDATED"
                    or endpoint.review_required
                    or not endpoint.jurisdiction_id
                ):
                    reasons.append("JURISDICTION_UNRESOLVED")
                    endpoint_contexts.append(None)
                else:
                    endpoint_contexts.append(UUID(endpoint.jurisdiction_id))
        else:
            scenario = s.scalar(
                select(c.ScenarioContextEntity).where(
                    c.ScenarioContextEntity.tenant_id == repo.tenant,
                    c.ScenarioContextEntity.project_id == str(request.project_id),
                    c.ScenarioContextEntity.scenario_definition_id == str(request.subject_id),
                    c.ScenarioContextEntity.version == ctx.context_resolution_version,
                )
            )
            if not scenario:
                raise LookupError("exact formal scenario not found")
            if scenario.validation_status != "VALIDATED" or scenario.review_required:
                reasons.append("PRODUCT_CONTEXT_CONFLICT")
        sources = unique(
            UUID(j.jurisdiction_id)
            for j in jurisdictions
            if j.context_type == "SOURCE"
            and j.jurisdiction_id
            and j.validation_status == "VALIDATED"
            and not j.review_required
        )
        destinations = unique(
            UUID(j.jurisdiction_id)
            for j in jurisdictions
            if j.context_type == "DESTINATION"
            and j.jurisdiction_id
            and j.validation_status == "VALIDATED"
            and not j.review_required
        )
        if endpoint_contexts is not None:
            sources = (endpoint_contexts[0],) if endpoint_contexts[0] else ()
            destinations = (endpoint_contexts[1],) if endpoint_contexts[1] else ()
        identity = AuthorityIdentity(
            tenant_id=UUID(repo.tenant),
            project_id=request.project_id,
            analysis_snapshot_id=request.analysis_snapshot_id,
            project_version_id=UUID(snap.project_version_id),
            context_version=ctx.context_resolution_version,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            data_item_ids=item_ids,
            data_flow_ids=flow_ids,
            scenario_definition_ids=(request.subject_id,)
            if request.subject_type == "SCENARIO"
            else (),
            jurisdiction_ids=unique(
                UUID(j.jurisdiction_id) for j in jurisdictions if j.jurisdiction_id
            ),
            analysis_as_of_date=snap.analysis_as_of_date,
        )
        pinrefs = tuple(
            sorted(
                (
                    pin_ref(p).model_copy(update={"kind": p.pin_type.removeprefix(PREFIX)})
                    if p.pin_type.startswith(PREFIX)
                    and p.pin_type.removeprefix(PREFIX) in FORMAL_RESULT_POLICY_TYPES
                    else pin_ref(p)
                    for p in allpins
                ),
                key=lambda p: str(p.pin_id),
            )
        )
    obrow = validated_reference(repo, request, "OBLIGATION", request.obligation_result_id)
    validated_reference(repo, request, "FINAL_PATH", request.final_path_result_id)
    validated_reference(repo, request, "CROSS_BORDER", request.cross_border_result_id)
    obligation = None
    original = None
    final = None
    cross = None
    if obrow and not reasons:
        obligation = repo.read_decision("OBLIGATION", request.obligation_result_id)
        obrequest = DecisionRequest.model_validate(obrow.request_json)
        original, _ = repo.prepare_decision(obrequest)
    if request.final_path_result_id and not reasons:
        final = repo.read_decision("FINAL_PATH", request.final_path_result_id)
        if not any(
            ref.kind == "OBLIGATION" and ref.result_id == request.obligation_result_id
            for ref in final.upstream_refs
        ):
            raise ValueError("document final-path obligation closure mismatch")
    if request.cross_border_result_id and not reasons:
        cross = read(repo, "CROSS_BORDER", request.cross_border_result_id)
        expected = {request.obligation_result_id} if request.obligation_result_id else set()
        if {ref.result_id for ref in cross.upstream_refs if ref.kind == "OBLIGATION"} != expected:
            raise ValueError("document cross-border obligation closure mismatch")
    if original:
        # Scenario references belong to the validated applicability input universe
        # even for a DATA_ITEM/DATA_FLOW subject; reuse that owning contract.
        identity = identity.model_copy(
            update={"scenario_definition_ids": original.identity.scenario_definition_ids}
        )
        for policy in policies:
            obpins = [p for p in original.pins if p.kind == "OBLIGATION_POLICY"]
            if len(obpins) != 1 or obpins[0].object_id != policy.config.obligation_policy_id:
                raise ValueError("authority obligation-policy pin closure mismatch")
            if policy.pin.kind == "DOCUMENT_REQUIREMENT_POLICY":
                matches = [p for p in policies if p.pin.kind == "CROSS_BORDER_ASSESSMENT_POLICY"]
                if (
                    len(matches) != 1
                    or matches[0].pin.object_id != policy.config.cross_border_policy_id
                ):
                    raise ValueError("document cross-border policy closure mismatch")
    return PreparedAuthorityInput(
        identity=identity,
        obligation=obligation,
        final_path=final,
        cross_border=cross,
        facts=original.facts if original else (),
        support=original.support if original else LegalSupport(),
        source_jurisdiction_ids=sources,
        destination_jurisdiction_ids=destinations,
        policies=policies,
        pins=pinrefs,
        templates=tuple(templates),
        blocking_reason_codes=unique(reasons),
        evidence_sufficient=bool(
            original
            and obligation.input_sufficiency == "SUFFICIENT"
            and original.support.evidence_ids
            and all(
                not app.review_required
                and app.conflict_status == "CLEAR"
                and app.applicability_status not in {"UNDETERMINED", "INSUFFICIENT_EVIDENCE"}
                for app in original.applicability
            )
        ),
        context_digest=signature,
        prepared_at=datetime.now(UTC),
        actor_ref=repo.context.permission.actor_id,
        request_id=request.idempotency_key,
        correlation_id=str(request.analysis_snapshot_id),
    )


def read(repo, kind, ident):
    with repo.sessions() as s:
        row = repo.get(s, a.MODELS[kind], ident)
        authorize(repo, row.project_id, "read")
        if row.owner_actor_id != repo.context.permission.actor_id:
            raise LookupError("formal authority not found")
        saved = AUTHORITY_ENVELOPES[kind].model_validate(row.result_json)
        request = FormalAuthorityRequest.model_validate(row.request_json)
        if saved.result_id != UUID(row.result_id) or request.stage_kind != kind:
            raise ValueError("formal authority stored identity mismatch")
    current = CALCULATE[kind](prepare(repo, request))
    if result_digest(saved) != result_digest(current):
        raise ValueError("formal authority exact pins/upstream no longer validate")
    return saved


def save(repo, request, result):
    authorize(repo, request.project_id, "execute")
    with repo.sessions() as s, s.begin():
        lock = int(
            digest(
                {
                    "namespace": "FORMAL_RESULT_AUTHORITY",
                    "tenant": repo.tenant,
                    "project": request.project_id,
                }
            )[:15],
            16,
        )
        s.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        current = CALCULATE[request.stage_kind](prepare(repo, request))
        if result_digest(current) != result_digest(result):
            raise ValueError("authority result differs from current authorized computation")
        repo.snapshot(s, request.project_id, request.analysis_snapshot_id, True, operation="read")
        key = s.scalar(
            select(j.DecisionRequestKeyEntity).where(
                j.DecisionRequestKeyEntity.tenant_id == repo.tenant,
                j.DecisionRequestKeyEntity.project_id == str(request.project_id),
                j.DecisionRequestKeyEntity.stage_kind == request.stage_kind,
                j.DecisionRequestKeyEntity.idempotency_key == request.idempotency_key,
            )
        )
        if key:
            if key.input_fingerprint != current.input_digest:
                raise ValueError("formal authority idempotency conflict")
            return AUTHORITY_ENVELOPES[request.stage_kind].model_validate(
                repo.get(s, a.MODELS[request.stage_kind], key.result_id).result_json
            )
        model = a.MODELS[request.stage_kind]
        existing = s.scalar(
            select(model).where(
                model.tenant_id == repo.tenant,
                model.project_id == str(request.project_id),
                model.analysis_snapshot_id == str(request.analysis_snapshot_id),
                model.subject_type == request.subject_type,
                model.subject_id == str(request.subject_id),
                model.input_fingerprint == current.input_digest,
            )
        )
        if existing:
            saved = AUTHORITY_ENVELOPES[request.stage_kind].model_validate(existing.result_json)
            if result_digest(saved) != result_digest(current):
                raise ValueError("CONFLICTED formal authority output")
        else:
            policy = next(
                (
                    p
                    for p in current.pins
                    if p.kind
                    == (
                        "CROSS_BORDER_ASSESSMENT_POLICY"
                        if request.stage_kind == "CROSS_BORDER"
                        else "DOCUMENT_REQUIREMENT_POLICY"
                    )
                ),
                None,
            )
            # Stored result points to the canonical immutable policy version, never a live pointer.
            data = {
                key: getattr(current, key)
                for key in (
                    "context_version",
                    "subject_type",
                    "analysis_as_of_date",
                    "pins_digest",
                    "contract_version",
                    "engine_version",
                )
            }
            data.update(
                result_id=str(current.result_id),
                tenant_id=repo.tenant,
                project_id=str(current.project_id),
                analysis_snapshot_id=str(current.analysis_snapshot_id),
                project_version_id=str(current.project_version_id),
                subject_id=str(current.subject_id),
                jurisdiction_ids=list(map(str, current.jurisdiction_ids)),
                policy_version_id=str(policy.version_id) if policy else None,
                upstream_refs=canonical(current.upstream_refs),
                pins_json=canonical(current.pins),
                provenance_json=canonical(current.provenance),
                input_fingerprint=current.input_digest,
                owner_actor_id=repo.context.permission.actor_id,
                summary_status=current.summary_status,
                request_json=request.model_dump(mode="json"),
                result_json=current.model_dump(mode="json"),
                obligation_result_id=str(request.obligation_result_id)
                if request.obligation_result_id
                else None,
            )
            if request.stage_kind == "DOCUMENT_REQUIREMENT":
                data.update(
                    cross_border_result_id=str(request.cross_border_result_id)
                    if request.cross_border_result_id
                    else None,
                    final_path_result_id=str(request.final_path_result_id)
                    if request.final_path_result_id
                    else None,
                )
            s.add(model(**data))
            s.flush()
            saved = current
        s.add(
            j.DecisionRequestKeyEntity(
                request_key_id=str(uuid4()),
                tenant_id=repo.tenant,
                project_id=str(request.project_id),
                stage_kind=request.stage_kind,
                idempotency_key=request.idempotency_key,
                input_fingerprint=current.input_digest,
                result_id=str(saved.result_id),
            )
        )
        s.flush()
        return saved
