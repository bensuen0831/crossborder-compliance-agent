"""Prepare authorized Phase 1E facts; canonical RuleHit/Classification persistence."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from crossborder_compliance.domain.classification import (
    ClassificationOutcome,
    ClassificationResult,
    ClassificationScheme,
)
from crossborder_compliance.domain.rule_ast import typed_value
from crossborder_compliance.domain.rules import RuleFactContext, RuleHit
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.classification_evidence import (
    ExistingClassificationEvidence,
)
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.rule_governance import as_rule


class PostgresFormalClassificationRepository:
    def __init__(self, sessions, context: RepositoryContext):
        self.sessions, self.context = sessions, context
        self.tenant = str(context.tenant_id)

    def authorize(self, project_id, operation="execute"):
        scopes = self.context.permission.scopes
        if not self.context.permission.system and (
            f"classification:{operation}" not in scopes
            or f"project:{project_id}:classify" not in scopes
        ):
            raise LookupError("classification resource not found")

    def scoped(self, session, model, pk, ident):
        row = session.scalar(select(model).where(pk == str(ident), model.tenant_id == self.tenant))
        if row is None:
            raise LookupError("classification resource not found")
        return row

    def prepare(self, project_id, snapshot_id, data_item_id, scheme_version_id):
        facts, scheme, rules = self._prepare(
            project_id, snapshot_id, data_item_id, scheme_version_id
        )
        ids, types, packs = ExistingClassificationEvidence(self.sessions, self.context).references(
            project_id, snapshot_id, data_item_id
        )
        facts = facts.model_copy(
            update={
                "evidence_ids": tuple(
                    sorted(set(facts.evidence_ids) | {UUID(v) for v in ids}, key=str)
                ),
                "evidence_types": tuple(sorted(set(facts.evidence_types) | set(types))),
                "evidence_pack_ids": tuple(UUID(v) for v in packs),
            }
        )
        return facts, scheme, rules

    def pin_configuration(self, project_id, snapshot_id, scheme_version_id):
        """Explicit analysis initialization; execution never silently selects new versions."""
        _, scheme, rules = self._prepare(
            project_id, snapshot_id, None, scheme_version_id, initialize=True
        )
        return {
            "status": "PINNED",
            "scheme_version_id": str(scheme.scheme_version_id),
            "rule_version_ids": [str(rule.rule_version_id) for rule in rules],
        }

    def _prepare(
        self, project_id, snapshot_id, data_item_id, scheme_version_id, *, initialize=False
    ):
        self.authorize(project_id)
        with self.sessions() as s, s.begin():
            snapshot = s.scalar(
                select(b.AnalysisSnapshotEntity)
                .where(
                    b.AnalysisSnapshotEntity.analysis_snapshot_id == str(snapshot_id),
                    b.AnalysisSnapshotEntity.tenant_id == self.tenant,
                )
                .with_for_update()
            )
            if snapshot is None:
                raise LookupError("classification resource not found")
            project = self.scoped(
                s,
                b.ProjectVersionEntity,
                b.ProjectVersionEntity.project_version_id,
                snapshot.project_version_id,
            )
            if project.project_id != str(project_id):
                raise LookupError("classification resource not found")
            pin = s.scalar(
                select(c.AnalysisSnapshotContextPinEntity).where(
                    c.AnalysisSnapshotContextPinEntity.tenant_id == self.tenant,
                    c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == str(snapshot_id),
                    c.AnalysisSnapshotContextPinEntity.project_id == str(project_id),
                )
            )
            if pin is None:
                raise ValueError("snapshot must pin formal Phase 1E context")
            version = self.scoped(
                s,
                m.ClassificationSchemeVersionEntity,
                m.ClassificationSchemeVersionEntity.scheme_version_id,
                scheme_version_id,
            )
            config = version.applicability_json.get("phase1h")
            if not config:
                raise ValueError("classification scheme has no V1 definition")
            scheme = ClassificationScheme.model_validate(
                {
                    **config,
                    "scheme_id": version.scheme_id,
                    "scheme_version_id": version.scheme_version_id,
                    "tenant_id": self.tenant,
                    "version": version.version_no,
                    "lifecycle": version.lifecycle_status,
                }
            )
            if version.lifecycle_status not in {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"}:
                raise ValueError("classification scheme is not published")
            published = s.scalar(
                select(m.AdminPublishRecordEntity).where(
                    m.AdminPublishRecordEntity.tenant_id == self.tenant,
                    m.AdminPublishRecordEntity.object_kind == "CLASSIFICATION",
                    m.AdminPublishRecordEntity.version_id == version.scheme_version_id,
                )
            )
            if published is None:
                raise ValueError("classification scheme has no durable publication")
            jurisdictions = set(
                s.scalars(
                    select(c.JurisdictionContextEntity.jurisdiction_id).where(
                        c.JurisdictionContextEntity.tenant_id == self.tenant,
                        c.JurisdictionContextEntity.project_id == str(project_id),
                        c.JurisdictionContextEntity.version == pin.context_resolution_version,
                        c.JurisdictionContextEntity.validation_status == "VALIDATED",
                        c.JurisdictionContextEntity.review_required.is_(False),
                    )
                ).all()
            )
            eligible = {str(v) for v in scheme.jurisdiction_ids} & jurisdictions
            if len(eligible) != 1:
                raise ValueError("classification requires one resolved scheme jurisdiction")
            jurisdiction = UUID(next(iter(eligible)))
            pins = s.scalars(
                select(m.AnalysisSnapshotRegistryPinEntity).where(
                    m.AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant,
                    m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(snapshot_id),
                    m.AnalysisSnapshotRegistryPinEntity.pin_type.in_(
                        ["CLASSIFICATION_V1", "RULE_V1"]
                    ),
                )
            ).all()
            scheme_pins = [p for p in pins if p.pin_type == "CLASSIFICATION_V1"]
            if scheme_pins and not any(p.version_id == str(scheme_version_id) for p in scheme_pins):
                raise ValueError("snapshot is pinned to another scheme version")
            if not scheme_pins:
                if not initialize:
                    raise ValueError(
                        "classification configuration must be explicitly pinned before execution"
                    )
                if (
                    version.lifecycle_status != "ACTIVE"
                    or (
                        version.effective_from
                        and snapshot.analysis_as_of_date < version.effective_from
                    )
                    or (
                        version.effective_to and snapshot.analysis_as_of_date > version.effective_to
                    )
                ):
                    raise ValueError("new snapshot requires effective ACTIVE scheme")
                self.add_pin(
                    s,
                    snapshot_id,
                    "CLASSIFICATION_V1",
                    version.scheme_id,
                    version.scheme_version_id,
                    version.version_no,
                )
                rows = s.scalars(
                    select(m.RuleVersionEntity)
                    .join(
                        m.RuleDefinitionEntity,
                        m.RuleDefinitionEntity.active_version_id
                        == m.RuleVersionEntity.rule_version_id,
                    )
                    .where(
                        m.RuleDefinitionEntity.tenant_id == self.tenant,
                        m.RuleVersionEntity.tenant_id == self.tenant,
                        m.RuleVersionEntity.lifecycle_status == "ACTIVE",
                        m.RuleVersionEntity.runtime_contract_json.is_not(None),
                    )
                ).all()
                # The scheme marker pins even an empty set; later publication cannot enlarge it.
                rows = [
                    r for r in rows if jurisdiction in as_rule(r).contract.scope.jurisdiction_ids
                ]
                rows = [
                    r
                    for r in rows
                    if any(
                        action.scheme_version_id == scheme.scheme_version_id
                        for action in as_rule(r).contract.actions
                    )
                ]
                rows = [
                    r
                    for r in rows
                    if as_rule(r).contract.effective_from <= snapshot.analysis_as_of_date
                    and (
                        as_rule(r).contract.effective_to is None
                        or snapshot.analysis_as_of_date <= as_rule(r).contract.effective_to
                    )
                ]
                for row in rows:
                    self.add_pin(
                        s,
                        snapshot_id,
                        "RULE_V1",
                        row.rule_definition_id,
                        row.rule_version_id,
                        row.version_no,
                    )
            else:
                rows = [
                    self.scoped(
                        s, m.RuleVersionEntity, m.RuleVersionEntity.rule_version_id, p.version_id
                    )
                    for p in pins
                    if p.pin_type == "RULE_V1"
                ]
            rules = tuple(as_rule(r) for r in rows)
            if initialize:
                return (
                    RuleFactContext(
                        tenant_id=UUID(self.tenant),
                        project_id=project_id,
                        analysis_snapshot_id=snapshot_id,
                        context_version=pin.context_resolution_version,
                        data_item_id=None,
                        jurisdiction_id=jurisdiction,
                        as_of=snapshot.analysis_as_of_date,
                        values={},
                        fact_refs={},
                    ),
                    scheme,
                    rules,
                )
            values, refs, confidence, review = {}, {}, 1.0, False
            if data_item_id is not None:
                item = self.scoped(s, b.DataItemEntity, b.DataItemEntity.data_item_id, data_item_id)
                detail = self.scoped(
                    s,
                    c.DataItemResolutionDetailEntity,
                    c.DataItemResolutionDetailEntity.data_item_id,
                    data_item_id,
                )
                if (
                    item.project_id != str(project_id)
                    or detail.version != pin.data_inventory_version
                ):
                    raise LookupError("classification resource not found")
                if detail.validation_status != "VALIDATED":
                    raise ValueError("classification requires validated formal DataItem")
                confidence, review = detail.confidence, detail.review_required
                values.update({"data_name": item.name, "canonical_type": item.canonical_type_ref})
                refs.update({key: (UUID(item.data_item_id),) for key in values})
            facts = s.scalars(
                select(c.BusinessFactEntity).where(
                    c.BusinessFactEntity.tenant_id == self.tenant,
                    c.BusinessFactEntity.project_id == str(project_id),
                    c.BusinessFactEntity.version == pin.context_resolution_version,
                    c.BusinessFactEntity.validation_status == "VALIDATED",
                    c.BusinessFactEntity.conflict_status == "NONE",
                )
            ).all()
            for fact in facts:
                key = fact.fact_type.lower()
                if key in values:
                    raise ValueError("ambiguous formal fact field")
                values[key], refs[key] = fact.normalized_value_json, (UUID(fact.fact_id),)
                confidence = min(confidence, fact.confidence)
                review |= fact.review_required
            # Evidence is linked to this exact DataItem's existing authorized trace chain.
            evidence = self.document_evidence(s, project_id, data_item_id)
            scenarios = s.scalars(
                select(m.MetadataDefinitionEntity.code)
                .join(
                    c.ScenarioContextEntity,
                    c.ScenarioContextEntity.scenario_definition_id
                    == m.MetadataDefinitionEntity.definition_id,
                )
                .where(
                    m.MetadataDefinitionEntity.tenant_id == self.tenant,
                    c.ScenarioContextEntity.tenant_id == self.tenant,
                    c.ScenarioContextEntity.project_id == str(project_id),
                    c.ScenarioContextEntity.version == pin.context_resolution_version,
                    c.ScenarioContextEntity.validation_status == "VALIDATED",
                    c.ScenarioContextEntity.review_required.is_(False),
                )
            ).all()
            product_context = s.scalar(
                select(c.ProductContextEntity).where(
                    c.ProductContextEntity.tenant_id == self.tenant,
                    c.ProductContextEntity.project_id == str(project_id),
                    c.ProductContextEntity.version == pin.product_context_version,
                    c.ProductContextEntity.review_required.is_(False),
                )
            )
            product_ids = product_context.effective_scope_json if product_context else []
            products = s.scalars(
                select(m.MetadataDefinitionEntity.code).where(
                    m.MetadataDefinitionEntity.tenant_id == self.tenant,
                    m.MetadataDefinitionEntity.definition_id.in_(product_ids),
                    m.MetadataDefinitionEntity.kind == "PRODUCT",
                )
            ).all()

            def codes(field):
                value = values.get(field)
                if type(value) is str:
                    return (value,)
                if type(value) is list and all(type(v) is str for v in value):
                    return tuple(value)
                return ()

            schemas = {}
            for rule in rules:
                for key, field in rule.contract.fields.items():
                    if key in schemas and schemas[key] != field:
                        raise ValueError("rule field schemas disagree")
                    schemas[key] = field
            prepared = {
                key: typed_value(value, schemas[key], literal=True)
                for key, value in values.items()
                if key in schemas
            }
            context = RuleFactContext(
                tenant_id=UUID(self.tenant),
                project_id=project_id,
                analysis_snapshot_id=snapshot_id,
                context_version=pin.context_resolution_version,
                data_item_id=data_item_id,
                jurisdiction_id=jurisdiction,
                as_of=snapshot.analysis_as_of_date,
                values=prepared,
                fact_refs={key: refs[key] for key in prepared},
                evidence_ids=tuple(UUID(e.evidence_id) for e in evidence),
                evidence_types=tuple(e.evidence_type for e in evidence),
                confidence=confidence,
                review_required=review,
            )
            context = context.model_copy(
                update={
                    "scenario_codes": tuple(scenarios),
                    "product_codes": tuple(products),
                    "industry_codes": codes("industry_codes"),
                    "data_category_codes": codes("data_category_codes"),
                }
            )
            return context, scheme, rules

    def add_pin(self, s, snapshot, kind, object_id, version_id, version):
        s.add(
            m.AnalysisSnapshotRegistryPinEntity(
                pin_id=str(uuid4()),
                tenant_id=self.tenant,
                analysis_snapshot_id=str(snapshot),
                pin_type=kind,
                logical_key=object_id,
                object_id=object_id,
                version_id=version_id,
                version_no=version,
            )
        )

    def save(self, outcome: ClassificationOutcome):
        result = outcome.result
        if not outcome.rule_hits:
            return outcome
        principal = outcome.rule_hits[0]
        self.authorize(principal.project_id)
        key = (
            principal.tenant_id,
            principal.project_id,
            principal.analysis_snapshot_id,
            principal.data_item_id,
            principal.context_version,
        )
        if str(principal.tenant_id) != self.tenant or any(
            (h.tenant_id, h.project_id, h.analysis_snapshot_id, h.data_item_id, h.context_version)
            != key
            for h in outcome.rule_hits
        ):
            raise LookupError("classification resource not found")
        if result is not None and (
            (
                result.tenant_id,
                result.project_id,
                result.analysis_snapshot_id,
                result.data_item_id,
                result.context_version,
            )
            != key
            or not set(result.rule_hit_ids)
            <= {h.rule_hit_id for h in outcome.rule_hits if h.matched}
        ):
            raise LookupError("classification resource not found")
        with self.sessions() as s, s.begin():
            self.scoped(
                s,
                b.AnalysisSnapshotEntity,
                b.AnalysisSnapshotEntity.analysis_snapshot_id,
                principal.analysis_snapshot_id,
            )
            # Serializing on the snapshot makes identical executions persist one formal result.
            s.scalar(
                select(b.AnalysisSnapshotEntity)
                .where(
                    b.AnalysisSnapshotEntity.analysis_snapshot_id
                    == str(principal.analysis_snapshot_id),
                    b.AnalysisSnapshotEntity.tenant_id == self.tenant,
                )
                .with_for_update()
            )
            if result is not None:
                existing = s.scalar(
                    select(b.ClassificationResultEntity).where(
                        b.ClassificationResultEntity.tenant_id == self.tenant,
                        b.ClassificationResultEntity.analysis_snapshot_id
                        == str(result.analysis_snapshot_id),
                        b.ClassificationResultEntity.project_id == str(result.project_id),
                        b.ClassificationResultEntity.subject_id == str(result.data_item_id),
                        b.ClassificationResultEntity.scheme_version_id
                        == str(result.scheme_version_id),
                        b.ClassificationResultEntity.formal_provenance_json.is_not(None),
                    )
                )
                if existing is not None:
                    saved = ClassificationResult.model_validate(existing.formal_provenance_json)
                    if not set(saved.evidence_ids) <= set(result.evidence_ids):
                        raise LookupError("classification resource not found")
                    rows = s.scalars(
                        select(b.RuleHitEntity).where(
                            b.RuleHitEntity.tenant_id == self.tenant,
                            b.RuleHitEntity.rule_hit_id.in_([str(v) for v in saved.rule_hit_ids]),
                        )
                    ).all()
                    return ClassificationOutcome(
                        status=saved.status,
                        reason_codes=saved.reason_codes,
                        result=saved,
                        rule_hits=tuple(
                            RuleHit.model_validate(row.formal_provenance_json) for row in rows
                        ),
                    )
            for hit in outcome.rule_hits:
                s.add(
                    b.RuleHitEntity(
                        rule_hit_id=str(hit.rule_hit_id),
                        tenant_id=self.tenant,
                        rule_version_ref=str(hit.rule_version_id),
                        subject_type="DATA_ITEM",
                        subject_id=str(principal.data_item_id),
                        evidence_json={"ids": [str(v) for v in hit.evidence_ids]},
                        formal_provenance_json=hit.model_dump(mode="json"),
                    )
                )
            s.flush()
            if result is None:
                return outcome
            s.add(
                b.ClassificationResultEntity(
                    classification_result_id=str(result.classification_result_id),
                    tenant_id=self.tenant,
                    subject_type="DATA_ITEM",
                    subject_id=str(result.data_item_id),
                    scheme_id=str(result.scheme_id),
                    scheme_version_id=str(result.scheme_version_id),
                    level_id=str(result.level_id) if result.level_id else None,
                    jurisdiction_id=str(result.jurisdiction_id),
                    confidence=result.confidence,
                    review_required=result.review_required,
                    project_id=str(result.project_id),
                    analysis_snapshot_id=str(result.analysis_snapshot_id),
                    formal_provenance_json=result.model_dump(mode="json"),
                    status=result.status,
                )
            )
            s.flush()
            for category in result.category_ids:
                s.add(
                    b.ClassificationResultCategoryEntity(
                        classification_result_category_id=str(uuid4()),
                        tenant_id=self.tenant,
                        classification_result_id=str(result.classification_result_id),
                        category_id=str(category),
                    )
                )
            return outcome

    def get_result(self, result_id):
        with self.sessions() as s:
            row = self.scoped(
                s,
                b.ClassificationResultEntity,
                b.ClassificationResultEntity.classification_result_id,
                result_id,
            )
            if not row.formal_provenance_json or not row.project_id:
                raise LookupError("classification resource not found")
            self.authorize(row.project_id, "read")
            result = dict(row.formal_provenance_json)
            project, snapshot, item = row.project_id, row.analysis_snapshot_id, row.subject_id
            visible = {ref.evidence_id for ref in self.document_evidence(s, project, item)}
        ids, _, _ = ExistingClassificationEvidence(self.sessions, self.context).references(
            project, snapshot, item
        )
        visible.update(ids)
        if not set(result["evidence_ids"]) <= visible:
            raise LookupError("classification resource not found")
        return result

    def document_evidence(self, session, project_id, item_id):
        if item_id is None:
            return []
        trace_ids = session.scalars(
            select(c.DataItemSourceTraceLinkEntity.source_trace_ref_id).where(
                c.DataItemSourceTraceLinkEntity.tenant_id == self.tenant,
                c.DataItemSourceTraceLinkEntity.data_item_id == str(item_id),
            )
        ).all()
        return session.scalars(
            select(b.EvidenceReferenceEntity)
            .join(
                b.SourceTraceRefEntity,
                b.SourceTraceRefEntity.source_trace_ref_id
                == b.EvidenceReferenceEntity.source_trace_ref_id,
            )
            .join(
                b.DocumentVersionEntity,
                b.DocumentVersionEntity.document_version_id
                == b.SourceTraceRefEntity.document_version_id,
            )
            .join(
                b.DocumentEntity,
                b.DocumentEntity.document_id == b.DocumentVersionEntity.document_id,
            )
            .where(
                b.EvidenceReferenceEntity.tenant_id == self.tenant,
                b.SourceTraceRefEntity.tenant_id == self.tenant,
                b.DocumentVersionEntity.tenant_id == self.tenant,
                b.DocumentEntity.tenant_id == self.tenant,
                b.DocumentEntity.project_id == str(project_id),
                b.EvidenceReferenceEntity.source_trace_ref_id.in_(trace_ids),
                b.EvidenceReferenceEntity.validation_status == "VALID",
                b.EvidenceReferenceEntity.status == "ACTIVE",
            )
        ).all()
