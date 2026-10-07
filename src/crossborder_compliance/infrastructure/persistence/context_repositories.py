from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import distinct, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from crossborder_compliance.domain.context_resolution import (
    BusinessFact, CandidateResolution, ContextConflict, ContextResolutionResult,
    ContextStatistics, ContextValidationStatus, DataFlowEdgeContext, DataFlowNodeContext,
    DataItemDeduplicationResult, DataItemResolutionDetail, DeviceContext,
    JurisdictionContext, JurisdictionResolution, LocationPrecision,
    PartyCandidate, PartyResolution, ProductContext, ProductContextCandidate,
    ProductScopeResolution, ResolutionAction, ScenarioContext, ScenarioResolution,
    SystemContext,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.context_models import (
    AnalysisSnapshotContextPinEntity, BusinessFactEntity,
    BusinessFactResolutionEntity, CandidateResolutionEntity,
    ContextConflictEntity, ContextResolutionRunEntity,
    DataFlowEdgeDetailEntity, DataFlowNodeDetailEntity,
    DataItemCandidateLinkEntity, DataItemDeduplicationResultEntity,
    DataItemFlowLinkDetailEntity, DataItemProductLinkDetailEntity,
    DataItemResolutionDetailEntity, DataItemSourceTraceLinkEntity,
    DeviceContextEntity, JurisdictionContextEntity,
    JurisdictionResolutionEntity, PartyCandidateEntity, PartyResolutionEntity,
    ProductContextCandidateEntity, ProductContextDefinitionLinkEntity, ProductContextEntity,
    ProductScopeResolutionEntity, ScenarioContextEntity, ScenarioResolutionEntity,
    SystemContextEntity,
)
from crossborder_compliance.infrastructure.persistence.document_models import (
    BusinessFactCandidateEntity, BusinessFactSourceLinkEntity,
    CandidateDataFlowEdgeEntity, CandidateDataFlowEdgeSourceLinkEntity,
    CandidateDataFlowNodeEntity, CandidateDataFlowNodeSourceLinkEntity,
    CandidateDataItemEntity, CandidateDataItemSourceLinkEntity,
    DocumentParseRunDetailEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    MetadataDefinitionEntity, MetadataVersionEntity,
)
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity, DataFlowEdgeEntity, DataFlowNodeEntity,
    DataItemEntity, DataItemFlowLinkEntity, DataItemGroupEntity,
    DataItemGroupMemberEntity, DataItemProductLinkEntity, DocumentEntity,
    DocumentParseRunEntity, DocumentVersionEntity, JurisdictionEntity,
    LegalEntityEntity, ProjectEntity, ProjectPartyEntity, ReviewTaskEntity,
    WorkflowRunEntity, SourceTraceRefEntity,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PostgresContextResolutionRepository:
    """Tenant-scoped Phase 1E repository.

    Phase 1B tables remain authoritative for formal DataItem/DataFlow/Party.
    Phase 1E tables only hold resolution/version/provenance/detail context.
    """

    def __init__(self, session_factory: sessionmaker, context: RepositoryContext, *, parse_run_ids: tuple[UUID, ...] | None = None, context_resolution_run_id: UUID | None = None):
        self._sessions = session_factory
        self._context = context
        self.parse_run_ids = parse_run_ids
        self.context_resolution_run_id = context_resolution_run_id

    @property
    def tenant_id(self) -> str:
        return str(self._context.tenant_id)

    def _get(self, session, model, pk, object_id: UUID):
        return session.scalar(select(model).where(pk == str(object_id), model.tenant_id == self.tenant_id))

    def project_exists(self, project_id: UUID) -> bool:
        with self._sessions() as s:
            return self._get(s, ProjectEntity, ProjectEntity.project_id, project_id) is not None

    def metadata_definition(self, definition_id: UUID) -> dict[str, object] | None:
        with self._sessions() as s:
            d = self._get(s, MetadataDefinitionEntity, MetadataDefinitionEntity.definition_id, definition_id)
            if d is None or d.active_version_id is None:
                return None
            v = self._get(s, MetadataVersionEntity, MetadataVersionEntity.version_id, UUID(d.active_version_id))
            if v is None or v.lifecycle_status != "ACTIVE":
                return None
            return {
                "definition_id": d.definition_id, "kind": d.kind, "code": d.code,
                "display_name": d.display_name, "version_id": v.version_id,
                "version_no": v.version_no, "payload": v.payload_json,
            }

    def metadata_definition_by_code(self, *, kind: str, code: str) -> dict[str, object] | None:
        with self._sessions() as s:
            d = s.scalar(select(MetadataDefinitionEntity).where(
                MetadataDefinitionEntity.tenant_id == self.tenant_id,
                MetadataDefinitionEntity.kind == kind,
                MetadataDefinitionEntity.code == code,
            ))
            if d is None or d.active_version_id is None:
                return None
            v = self._get(s, MetadataVersionEntity, MetadataVersionEntity.version_id, UUID(d.active_version_id))
            if v is None or v.lifecycle_status != "ACTIVE":
                return None
            return {
                "definition_id": d.definition_id, "kind": d.kind, "code": d.code,
                "display_name": d.display_name, "version_id": v.version_id,
                "version_no": v.version_no, "payload": v.payload_json,
            }

    def _project_parse_runs(self, project_id: UUID):
        query = (
            select(DocumentParseRunEntity.document_parse_run_id)
            .join(DocumentVersionEntity, DocumentVersionEntity.document_version_id == DocumentParseRunEntity.document_version_id)
            .join(DocumentEntity, DocumentEntity.document_id == DocumentVersionEntity.document_id)
            .where(
                DocumentParseRunEntity.tenant_id == self.tenant_id,
                DocumentEntity.tenant_id == self.tenant_id,
                DocumentEntity.project_id == str(project_id),
            )
        )

        if self.parse_run_ids is not None:
            query = query.where(DocumentParseRunEntity.document_parse_run_id.in_([str(x) for x in self.parse_run_ids]))
        return query

    def _trace_ids(self, session, link_model, fk_col, object_id: str) -> list[str]:
        return list(session.scalars(select(link_model.source_trace_ref_id).where(
            link_model.tenant_id == self.tenant_id, fk_col == object_id
        )))

    def list_candidate_facts(self, project_id: UUID) -> list[dict[str, object]]:
        runs = self._project_parse_runs(project_id)
        with self._sessions() as s:
            rows = s.scalars(select(BusinessFactCandidateEntity).where(
                BusinessFactCandidateEntity.tenant_id == self.tenant_id,
                BusinessFactCandidateEntity.parse_run_id.in_(runs),
            )).all()
            out = []
            for r in rows:
                traces = self._trace_ids(s, BusinessFactSourceLinkEntity, BusinessFactSourceLinkEntity.fact_id, r.fact_id)
                doc_ids = list(s.scalars(
                    select(DocumentEntity.document_id)
                    .join(DocumentVersionEntity, DocumentVersionEntity.document_id == DocumentEntity.document_id)
                    .join(DocumentParseRunEntity, DocumentParseRunEntity.document_version_id == DocumentVersionEntity.document_version_id)
                    .where(DocumentParseRunEntity.document_parse_run_id == r.parse_run_id)
                ))
                out.append({
                    "candidate_id": r.fact_id, "fact_type": r.fact_type,
                    "normalized_value": r.normalized_value_json, "original_value": r.original_value_json,
                    "confidence": r.confidence, "source_trace_ids": traces,
                    "source_document_ids": doc_ids,
                })
            return out

    def structured_fact_inputs(self, project_id: UUID, intake_version_id: UUID,
                               snapshot_id: UUID) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.structured_intake import inputs
        return inputs(self, project_id, intake_version_id, snapshot_id)

    def list_candidate_items(self, project_id: UUID) -> list[dict[str, object]]:
        runs = self._project_parse_runs(project_id)
        with self._sessions() as s:
            rows = s.scalars(select(CandidateDataItemEntity).where(
                CandidateDataItemEntity.tenant_id == self.tenant_id,
                CandidateDataItemEntity.parse_run_id.in_(runs),
            )).all()
            out = []
            for r in rows:
                traces = self._trace_ids(
                    s, CandidateDataItemSourceLinkEntity,
                    CandidateDataItemSourceLinkEntity.candidate_data_item_id, r.candidate_data_item_id
                )
                version_id = s.scalar(select(DocumentParseRunEntity.document_version_id).where(
                    DocumentParseRunEntity.document_parse_run_id == r.parse_run_id
                ))
                out.append({
                    "candidate_id": r.candidate_data_item_id, "raw_name": r.raw_name,
                    "normalized_name": r.normalized_name, "description": r.description,
                    "value_type": r.value_type, "unit": r.unit,
                    "quantity_metadata": r.quantity_metadata_json, "system_ref": r.system_ref,
                    "confidence": r.confidence, "source_trace_ids": traces,
                    "document_version_id": version_id,
                })
            return out

    def list_candidate_flow_nodes(self, project_id: UUID) -> list[dict[str, object]]:
        runs = self._project_parse_runs(project_id)
        with self._sessions() as s:
            rows = s.scalars(select(CandidateDataFlowNodeEntity).where(
                CandidateDataFlowNodeEntity.tenant_id == self.tenant_id,
                CandidateDataFlowNodeEntity.parse_run_id.in_(runs),
            )).all()
            return [{
                "candidate_node_id": r.candidate_node_id, "name": r.name,
                "node_type_candidate": r.node_type_candidate,
                "location_candidate": r.location_candidate, "party_candidate": r.party_candidate,
                "system_candidate": r.system_candidate, "confidence": r.confidence,
                "source_trace_ids": self._trace_ids(
                    s, CandidateDataFlowNodeSourceLinkEntity,
                    CandidateDataFlowNodeSourceLinkEntity.candidate_node_id, r.candidate_node_id
                ),
            } for r in rows]

    def list_candidate_flow_edges(self, project_id: UUID) -> list[dict[str, object]]:
        runs = self._project_parse_runs(project_id)
        with self._sessions() as s:
            rows = s.scalars(select(CandidateDataFlowEdgeEntity).where(
                CandidateDataFlowEdgeEntity.tenant_id == self.tenant_id,
                CandidateDataFlowEdgeEntity.parse_run_id.in_(runs),
            )).all()
            return [{
                "candidate_edge_id": r.candidate_edge_id,
                "source_candidate_node_id": r.source_candidate_node_id,
                "target_candidate_node_id": r.target_candidate_node_id,
                "direction": r.direction, "transfer_type_candidate": r.transfer_type_candidate,
                "data_item_refs": r.data_item_refs_json, "confidence": r.confidence,
                "source_trace_ids": self._trace_ids(
                    s, CandidateDataFlowEdgeSourceLinkEntity,
                    CandidateDataFlowEdgeSourceLinkEntity.candidate_edge_id, r.candidate_edge_id
                ),
            } for r in rows]

    def save_business_fact(self, fact: BusinessFact, candidate_ids: tuple[UUID, ...]) -> None:
        with self._sessions() as s, s.begin():
            s.add(BusinessFactEntity(
                fact_id=str(fact.fact_id), project_id=str(fact.project_id), tenant_id=self.tenant_id,
                fact_type=fact.fact_type, normalized_key=str(fact.normalized_value).strip().casefold(),
                normalized_value_json=fact.normalized_value, original_values_json=list(fact.original_values),
                source_document_ids_json=[str(x) for x in fact.source_document_ids],
                resolution_method=fact.resolution_method, confidence=fact.confidence,
                validation_status=fact.validation_status.value, conflict_status=fact.conflict_status,
                review_required=fact.review_required, version=fact.version,
                structured_provenance_json=[p.model_dump(mode="json")
                                            for p in fact.structured_provenance],
            ))
            s.flush()
            for candidate_id in candidate_ids:
                s.add(BusinessFactResolutionEntity(
                    resolution_id=str(uuid4()), candidate_fact_id=str(candidate_id),
                    business_fact_id=str(fact.fact_id), tenant_id=self.tenant_id,
                    action="ACCEPTED" if len(candidate_ids) == 1 else "MERGED",
                    confidence=fact.confidence, reason_code="NORMALIZED_FACT",
                    source_trace_ids_json=[str(x) for x in fact.source_trace_ids],
                    reviewer_required=fact.review_required, version=fact.version,
                ))

    def save_candidate_resolution(self, resolution: CandidateResolution) -> None:
        with self._sessions() as s, s.begin():
            state = dict(formal_object_type=resolution.formal_object_type,
                formal_object_id=str(resolution.formal_object_id) if resolution.formal_object_id else None,
                action=resolution.action.value, confidence=resolution.confidence,
                resolution_reason_code=resolution.resolution_reason_code,
                source_trace_ids_json=[str(x) for x in resolution.source_trace_ids],
                reviewer_required=resolution.reviewer_required, resolved_by_type=resolution.resolved_by_type)
            existing = s.scalar(select(CandidateResolutionEntity).where(
                CandidateResolutionEntity.tenant_id == self.tenant_id,
                CandidateResolutionEntity.candidate_type == resolution.candidate_type,
                CandidateResolutionEntity.candidate_id == str(resolution.candidate_id),
                CandidateResolutionEntity.version == resolution.version))
            if existing is not None:
                if any(getattr(existing, key) != value for key, value in state.items()):
                    raise ValueError("IMMUTABLE_CANDIDATE_RESOLUTION_REWRITE")
                return
            s.add(CandidateResolutionEntity(resolution_id=str(resolution.resolution_id), tenant_id=self.tenant_id,
                candidate_type=resolution.candidate_type, candidate_id=str(resolution.candidate_id),
                resolved_at=resolution.resolved_at, version=resolution.version, **state))

    def save_conflict(self, conflict: ContextConflict) -> None:
        with self._sessions() as s, s.begin():
            s.add(ContextConflictEntity(
                conflict_id=str(conflict.conflict_id), project_id=str(conflict.project_id),
                tenant_id=self.tenant_id, conflict_type=conflict.conflict_type,
                object_type=conflict.object_type, object_ids_json=[str(x) for x in conflict.object_ids],
                reason_code=conflict.reason_code, details_json=conflict.details,
                source_trace_ids_json=[str(x) for x in conflict.source_trace_ids],
                confidence=conflict.confidence, resolution_status=conflict.resolution_status,
                review_required=conflict.review_required, version=conflict.version,
            ))

    def resolve_conflict(self, conflict_id: UUID, *, resolution: dict[str, object], resolved_by: str, expected_record_version: int) -> dict[str, object]:
        with self._sessions() as s, s.begin():
            conflict = self._get(s, ContextConflictEntity, ContextConflictEntity.conflict_id, conflict_id)
            if conflict is None:
                raise LookupError("context conflict not found")
            if conflict.conflict_type == "PRODUCT_CONTEXT_CONFLICT":
                requested = resolution.get("effective_product_scope")
                if not isinstance(requested, list) or not requested:
                    raise ValueError("PRODUCT_CONTEXT_CONFLICT resolution requires effective_product_scope")
                scope_ids = [UUID(str(x)) for x in requested]
                allowed = {"PRODUCT_DOMAIN","PRODUCT_CATEGORY","PRODUCT_FAMILY","PRODUCT","PRODUCT_TAG"}
                for definition_id in scope_ids:
                    definition = self._get(s, MetadataDefinitionEntity, MetadataDefinitionEntity.definition_id, definition_id)
                    if definition is None or definition.active_version_id is None or definition.kind not in allowed:
                        raise ValueError("effective product scope must reference ACTIVE Product Registry definitions")
                    version = self._get(s, MetadataVersionEntity, MetadataVersionEntity.version_id, UUID(definition.active_version_id))
                    if version is None or version.lifecycle_status != "ACTIVE":
                        raise ValueError("effective product scope must reference ACTIVE Product Registry definitions")
            result = s.execute(
                update(ContextConflictEntity)
                .where(
                    ContextConflictEntity.conflict_id == str(conflict_id),
                    ContextConflictEntity.tenant_id == self.tenant_id,
                    ContextConflictEntity.record_version == expected_record_version,
                )
                .values(
                    resolution_status="RESOLVED", resolution_json=resolution,
                    resolved_by=resolved_by, resolved_at=_now(),
                    record_version=ContextConflictEntity.record_version + 1,
                )
            )
            if result.rowcount != 1:
                raise OptimisticConcurrencyError("context conflict version changed")
            if conflict.conflict_type == "PRODUCT_CONTEXT_CONFLICT":
                scope = [str(x) for x in scope_ids]
                scope_result = s.execute(
                    update(ProductScopeResolutionEntity)
                    .where(
                        ProductScopeResolutionEntity.tenant_id == self.tenant_id,
                        ProductScopeResolutionEntity.conflict_id == str(conflict_id),
                    )
                    .values(
                        effective_product_scope_json=scope,
                        resolution_status="RESOLVED", review_required=False,
                        updated_at=_now(),
                    )
                )
                if scope_result.rowcount != 1:
                    raise LookupError("product scope resolution not found for conflict")
        with self._sessions() as s:
            row = self._get(s, ContextConflictEntity, ContextConflictEntity.conflict_id, conflict_id)
            if row is None:
                raise LookupError("context conflict not found")
            return self._conflict_dict(row)

    def _conflict_dict(self, row: ContextConflictEntity) -> dict[str, object]:
        return {
            "conflict_id": row.conflict_id, "project_id": row.project_id,
            "conflict_type": row.conflict_type, "object_type": row.object_type,
            "object_ids": row.object_ids_json, "reason_code": row.reason_code,
            "details": row.details_json, "source_trace_ids": row.source_trace_ids_json,
            "confidence": row.confidence, "resolution_status": row.resolution_status,
            "review_required": row.review_required, "record_version": row.record_version,
            "version": row.version,
        }

    def list_conflicts(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(ContextConflictEntity).where(
                ContextConflictEntity.tenant_id == self.tenant_id,
                ContextConflictEntity.project_id == str(project_id),
            ).order_by(ContextConflictEntity.created_at)).all()
            return [self._conflict_dict(r) for r in rows]

    def save_product_context_candidate(self, candidate: ProductContextCandidate) -> None:
        with self._sessions() as s, s.begin():
            s.add(ProductContextCandidateEntity(
                product_context_candidate_id=str(candidate.product_context_candidate_id),
                project_id=str(candidate.project_id), tenant_id=self.tenant_id,
                dimension_type=candidate.dimension_type, definition_id=str(candidate.definition_id),
                source=candidate.source, confidence=candidate.confidence,
                source_trace_ids_json=[str(x) for x in candidate.source_trace_ids],
                version=candidate.version,
            ))

    def save_product_context(self, context: ProductContext) -> None:
        with self._sessions() as s, s.begin():
            s.add(ProductContextEntity(
                product_context_id=str(context.product_context_id), project_id=str(context.project_id),
                tenant_id=self.tenant_id, source=context.source, confidence=context.confidence,
                evidence_ids_json=[str(x) for x in context.evidence_ids],
                source_trace_ids_json=[str(x) for x in context.source_trace_ids],
                effective_scope_json=[str(x) for x in context.effective_scope],
                resolution_status=context.resolution_status, review_required=context.review_required,
                version=context.version,
            ))
            s.flush()
            dimensions = {
                "PRODUCT_DOMAIN": context.product_domain_ids, "PRODUCT_CATEGORY": context.product_category_ids,
                "PRODUCT_FAMILY": context.product_family_ids, "PRODUCT": context.product_ids,
                "PRODUCT_TAG": context.product_tag_ids,
            }
            for dimension, ids in dimensions.items():
                for definition_id in ids:
                    s.add(ProductContextDefinitionLinkEntity(
                        product_context_definition_link_id=str(uuid4()),
                        product_context_id=str(context.product_context_id),
                        dimension_type=dimension, definition_id=str(definition_id),
                        tenant_id=self.tenant_id,
                    ))

    def save_product_scope_resolution(self, resolution: ProductScopeResolution) -> None:
        with self._sessions() as s, s.begin():
            s.add(ProductScopeResolutionEntity(
                product_scope_resolution_id=str(resolution.product_scope_resolution_id),
                project_id=str(resolution.project_id), tenant_id=self.tenant_id,
                selected_product_scope_json=[str(x) for x in resolution.selected_product_scope],
                detected_product_context_json=[str(x) for x in resolution.detected_product_context],
                effective_product_scope_json=[str(x) for x in resolution.effective_product_scope],
                conflict_id=str(resolution.conflict_id) if resolution.conflict_id else None,
                resolution_status=resolution.resolution_status,
                review_required=resolution.review_required, version=resolution.version,
            ))

    def save_scenario_context(self, context: ScenarioContext) -> None:
        with self._sessions() as s, s.begin():
            s.add(ScenarioContextEntity(
                scenario_context_id=str(context.scenario_context_id), project_id=str(context.project_id),
                scenario_definition_id=str(context.scenario_definition_id) if context.scenario_definition_id else None,
                tenant_id=self.tenant_id, source=context.source, confidence=context.confidence,
                source_trace_ids_json=[str(x) for x in context.source_trace_ids],
                validation_status=context.validation_status.value,
                review_required=context.review_required, version=context.version,
            ))

    def save_scenario_resolution(self, resolution: ScenarioResolution) -> None:
        with self._sessions() as s, s.begin():
            s.add(ScenarioResolutionEntity(
                scenario_resolution_id=str(resolution.scenario_resolution_id),
                project_id=str(resolution.project_id), tenant_id=self.tenant_id,
                scenario_definition_id=str(resolution.scenario_definition_id),
                action=resolution.action.value, source=resolution.source,
                confidence=resolution.confidence,
                source_trace_ids_json=[str(x) for x in resolution.source_trace_ids],
                review_required=resolution.review_required, version=resolution.version,
            ))

    def save_system_context(self, context: SystemContext) -> None:
        with self._sessions() as s, s.begin():
            s.add(SystemContextEntity(
                system_id=str(context.system_id), project_id=str(context.project_id),
                tenant_id=self.tenant_id, display_name=context.display_name,
                system_type_ref=str(context.system_type_ref) if context.system_type_ref else None,
                product_context_refs_json=[str(x) for x in context.product_context_refs],
                party_refs_json=[str(x) for x in context.party_refs],
                location_refs_json=[str(x) for x in context.location_refs],
                source_trace_ids_json=[str(x) for x in context.source_trace_ids],
                confidence=context.confidence, validation_status=context.validation_status.value,
                version=context.version,
            ))

    def find_system_by_name(self, project_id: UUID, display_name: str) -> dict[str, object] | None:
        with self._sessions() as s:
            row = s.scalar(select(SystemContextEntity).where(
                SystemContextEntity.tenant_id == self.tenant_id,
                SystemContextEntity.project_id == str(project_id),
                func.lower(SystemContextEntity.display_name) == display_name.strip().lower(),
            ).order_by(SystemContextEntity.version.desc()))
            if row is None:
                return None
            return {
                "system_id": row.system_id, "display_name": row.display_name,
                "system_type_ref": row.system_type_ref, "version": row.version,
            }

    def save_device_context(self, context: DeviceContext) -> None:
        with self._sessions() as s, s.begin():
            s.add(DeviceContextEntity(
                device_id=str(context.device_id), project_id=str(context.project_id),
                tenant_id=self.tenant_id, display_name=context.display_name,
                device_type_ref=str(context.device_type_ref) if context.device_type_ref else None,
                system_id=str(context.system_id) if context.system_id else None,
                product_context_refs_json=[str(x) for x in context.product_context_refs],
                source_trace_ids_json=[str(x) for x in context.source_trace_ids],
                confidence=context.confidence, validation_status=context.validation_status.value,
                version=context.version,
            ))

    def save_party_candidate(self, candidate: PartyCandidate) -> None:
        with self._sessions() as s, s.begin():
            s.add(PartyCandidateEntity(
                party_candidate_id=str(candidate.party_candidate_id), project_id=str(candidate.project_id),
                tenant_id=self.tenant_id, display_name=candidate.display_name,
                role_definition_id=str(candidate.role_definition_id) if candidate.role_definition_id else None,
                source_trace_ids_json=[str(x) for x in candidate.source_trace_ids],
                confidence=candidate.confidence,
            ))

    def save_party_resolution(self, resolution: PartyResolution) -> None:
        with self._sessions() as s, s.begin():
            s.add(PartyResolutionEntity(
                party_resolution_id=str(resolution.party_resolution_id),
                party_candidate_id=str(resolution.party_candidate_id),
                project_party_id=str(resolution.project_party_id) if resolution.project_party_id else None,
                legal_entity_id=str(resolution.legal_entity_id) if resolution.legal_entity_id else None,
                tenant_id=self.tenant_id, action=resolution.action.value,
                confidence=resolution.confidence, reason_code=resolution.reason_code,
                source_trace_ids_json=[str(x) for x in resolution.source_trace_ids],
                review_required=resolution.review_required, version=resolution.version,
            ))

    def find_project_party_by_name(self, project_id: UUID, display_name: str) -> dict[str, object] | None:
        with self._sessions() as s:
            row = s.scalar(select(ProjectPartyEntity).where(
                ProjectPartyEntity.tenant_id == self.tenant_id,
                ProjectPartyEntity.project_id == str(project_id),
                func.lower(ProjectPartyEntity.display_name) == display_name.strip().lower(),
            ))
            if row is None:
                return None
            return {
                "project_party_id": row.project_party_id, "legal_entity_id": row.legal_entity_id,
                "display_name": row.display_name,
            }

    def create_formal_data_item(self, *, project_id: UUID, canonical_name: str, description: str | None, source_document_version_id: UUID | None, source_trace_id: UUID, detail: DataItemResolutionDetail) -> UUID:
        with self._sessions() as s, s.begin():
            project = s.scalar(select(ProjectEntity).where(ProjectEntity.tenant_id == self.tenant_id, ProjectEntity.project_id == str(project_id)).with_for_update())
            if project is None:
                raise LookupError("formal inventory project unavailable")
            trace = self._get(s, SourceTraceRefEntity, SourceTraceRefEntity.source_trace_ref_id, source_trace_id)
            source_version = self._get(s, DocumentVersionEntity, DocumentVersionEntity.document_version_id, UUID(trace.document_version_id)) if trace else None
            source_document = self._get(s, DocumentEntity, DocumentEntity.document_id, UUID(source_version.document_id)) if source_version else None
            if source_document is None or source_document.project_id != str(project_id) or (source_document_version_id is not None and source_version.document_version_id != str(source_document_version_id)):
                raise LookupError("formal inventory source outside tenant/project")
            item = s.scalar(select(DataItemEntity).where(
                DataItemEntity.tenant_id == self.tenant_id,
                DataItemEntity.project_id == str(project_id), DataItemEntity.name == canonical_name,
            ))
            if item is None:
                item = DataItemEntity(data_item_id=str(detail.data_item_id), project_id=str(project_id), tenant_id=self.tenant_id,
                    name=canonical_name, canonical_type_ref=detail.value_type, description=description,
                    source_document_version_id=str(source_document_version_id) if source_document_version_id else None,
                    source_trace_ref_id=str(source_trace_id))
                s.add(item)
                s.flush()
            state = dict(display_name=detail.display_name, value_type=detail.value_type, format=detail.format, unit=detail.unit,
                frequency_quantity_json=detail.frequency_quantity_metadata, system_ids_json=[str(x) for x in detail.system_ids],
                device_ids_json=[str(x) for x in detail.device_ids], confidence=detail.confidence,
                validation_status=detail.validation_status.value, review_required=detail.review_required, version=detail.version)
            existing = s.scalar(select(DataItemResolutionDetailEntity).where(
                DataItemResolutionDetailEntity.tenant_id == self.tenant_id,
                DataItemResolutionDetailEntity.data_item_id == item.data_item_id,
                DataItemResolutionDetailEntity.version == detail.version))
            if existing is None:
                s.add(DataItemResolutionDetailEntity(data_item_id=item.data_item_id, tenant_id=self.tenant_id, **state))
            elif any(getattr(existing, key) != value for key, value in state.items()):
                raise ValueError("IMMUTABLE_INVENTORY_VERSION_REWRITE")
            return UUID(item.data_item_id)

    def attach_candidate_to_data_item(self, *, data_item_id: UUID, candidate_id: UUID, source_trace_ids: tuple[UUID, ...], version: int) -> None:
        from crossborder_compliance.infrastructure.persistence.context_temporal import exact_item_detail
        with self._sessions() as s, s.begin():
            exact_item_detail(s, self.tenant_id, data_item_id, version)
            candidate = self._get(s, CandidateDataItemEntity, CandidateDataItemEntity.candidate_data_item_id, candidate_id)
            if candidate is None or candidate.parse_run_id not in s.scalars(self._project_parse_runs(UUID(self._get(s, DataItemEntity, DataItemEntity.data_item_id, data_item_id).project_id))).all():
                raise LookupError("candidate outside formal input universe")
            existing = s.scalar(select(DataItemCandidateLinkEntity).where(
                DataItemCandidateLinkEntity.tenant_id == self.tenant_id,
                DataItemCandidateLinkEntity.data_item_id == str(data_item_id),
                DataItemCandidateLinkEntity.data_inventory_version == version,
                DataItemCandidateLinkEntity.candidate_data_item_id == str(candidate_id)))
            if existing is None:
                item = self._get(s, DataItemEntity, DataItemEntity.data_item_id, data_item_id)
                frozen = s.scalar(select(AnalysisSnapshotContextPinEntity.analysis_snapshot_context_pin_id).where(
                    AnalysisSnapshotContextPinEntity.tenant_id == self.tenant_id,
                    AnalysisSnapshotContextPinEntity.project_id == item.project_id,
                    AnalysisSnapshotContextPinEntity.data_inventory_version == version))
                if frozen is not None:
                    raise ValueError("IMMUTABLE_INVENTORY_PROVENANCE_REWRITE")
                s.add(DataItemCandidateLinkEntity(data_item_candidate_link_id=str(uuid4()), data_item_id=str(data_item_id),
                    candidate_data_item_id=str(candidate_id), tenant_id=self.tenant_id, data_inventory_version=version))
            for trace_id in source_trace_ids:
                if str(trace_id) not in self._trace_ids(s, CandidateDataItemSourceLinkEntity, CandidateDataItemSourceLinkEntity.candidate_data_item_id, str(candidate_id)):
                    raise LookupError("trace outside candidate provenance")
                existing = s.scalar(select(DataItemSourceTraceLinkEntity).where(
                    DataItemSourceTraceLinkEntity.tenant_id == self.tenant_id,
                    DataItemSourceTraceLinkEntity.data_item_id == str(data_item_id),
                    DataItemSourceTraceLinkEntity.data_inventory_version == version,
                    DataItemSourceTraceLinkEntity.source_trace_ref_id == str(trace_id)))
                if existing is None:
                    s.add(DataItemSourceTraceLinkEntity(data_item_source_trace_link_id=str(uuid4()), data_item_id=str(data_item_id),
                        source_trace_ref_id=str(trace_id), tenant_id=self.tenant_id, data_inventory_version=version))

    def save_dedup_result(self, result: DataItemDeduplicationResult) -> None:
        with self._sessions() as s, s.begin():
            s.add(DataItemDeduplicationResultEntity(
                deduplication_result_id=str(result.deduplication_result_id),
                project_id=str(result.project_id), tenant_id=self.tenant_id,
                left_candidate_id=str(result.left_candidate_id),
                right_candidate_id=str(result.right_candidate_id),
                decision=result.decision.value, deterministic_score=result.deterministic_score,
                semantic_candidate_score=result.semantic_candidate_score,
                reason_code=result.reason_code, reviewer_required=result.reviewer_required,
                version=result.version,
            ))

    def ensure_data_group(self, *, project_id: UUID, name: str, grouping_reason: str, data_item_ids: tuple[UUID, ...]) -> UUID:
        with self._sessions() as s, s.begin():
            group = s.scalar(select(DataItemGroupEntity).where(
                DataItemGroupEntity.tenant_id == self.tenant_id,
                DataItemGroupEntity.project_id == str(project_id),
                DataItemGroupEntity.name == name,
            ))
            if group is None:
                group = DataItemGroupEntity(
                    data_item_group_id=str(uuid4()), project_id=str(project_id),
                    tenant_id=self.tenant_id, name=name, grouping_reason=grouping_reason,
                )
                s.add(group)
                s.flush()
            for item_id in data_item_ids:
                exists = s.scalar(select(DataItemGroupMemberEntity).where(
                    DataItemGroupMemberEntity.tenant_id == self.tenant_id,
                    DataItemGroupMemberEntity.data_item_group_id == group.data_item_group_id,
                    DataItemGroupMemberEntity.data_item_id == str(item_id),
                ))
                if exists is None:
                    s.add(DataItemGroupMemberEntity(
                        data_item_group_member_id=str(uuid4()),
                        data_item_group_id=group.data_item_group_id,
                        data_item_id=str(item_id), tenant_id=self.tenant_id,
                    ))
            return UUID(group.data_item_group_id)

    def bind_data_item_product(self, *, data_item_id: UUID, product_domain_definition_id: UUID | None, product_definition_id: UUID | None, relationship_type: str, confidence: float, source_trace_ids: tuple[UUID, ...], version: int) -> UUID:
        from crossborder_compliance.infrastructure.persistence.context_temporal import exact_item_detail
        product_ref = str(product_definition_id or product_domain_definition_id or "")
        if not product_ref:
            raise ValueError("product binding requires registry definition")
        with self._sessions() as s, s.begin():
            exact_item_detail(s, self.tenant_id, data_item_id, version)
            row = s.scalar(select(DataItemProductLinkEntity).where(
                DataItemProductLinkEntity.tenant_id == self.tenant_id,
                DataItemProductLinkEntity.data_item_id == str(data_item_id),
                DataItemProductLinkEntity.product_ref == product_ref,
            ))
            if row is None:
                row = DataItemProductLinkEntity(
                    data_item_product_link_id=str(uuid4()), data_item_id=str(data_item_id),
                    product_ref=product_ref, tenant_id=self.tenant_id,
                )
                s.add(row)
                s.flush()
            state = dict(product_domain_definition_id=str(product_domain_definition_id) if product_domain_definition_id else None,
                product_definition_id=str(product_definition_id) if product_definition_id else None,
                relationship_type=relationship_type, confidence=confidence, evidence_id=None,
                source_trace_ids_json=[str(x) for x in source_trace_ids])
            prior = s.scalar(select(DataItemProductLinkDetailEntity).where(
                DataItemProductLinkDetailEntity.tenant_id == self.tenant_id,
                DataItemProductLinkDetailEntity.data_item_product_link_id == row.data_item_product_link_id,
                DataItemProductLinkDetailEntity.data_inventory_version == version))
            if prior is None:
                s.add(DataItemProductLinkDetailEntity(data_item_product_link_id=row.data_item_product_link_id,
                    tenant_id=self.tenant_id, data_inventory_version=version, **state))
            elif any(getattr(prior, key) != value for key, value in state.items()):
                raise ValueError("IMMUTABLE_PRODUCT_LINK_VERSION_REWRITE")
            return UUID(row.data_item_product_link_id)

    def jurisdiction_exists(self, jurisdiction_id: UUID) -> bool:
        with self._sessions() as s:
            return self._get(s, JurisdictionEntity, JurisdictionEntity.jurisdiction_id, jurisdiction_id) is not None

    def save_jurisdiction_context(self, context: JurisdictionContext) -> None:
        with self._sessions() as s, s.begin():
            s.add(JurisdictionContextEntity(
                jurisdiction_context_id=str(context.jurisdiction_context_id),
                project_id=str(context.project_id), tenant_id=self.tenant_id,
                jurisdiction_id=str(context.jurisdiction_id) if context.jurisdiction_id else None,
                context_type=context.context_type, location_precision=context.location_precision.value,
                source=context.source, confidence=context.confidence,
                latitude=context.latitude, longitude=context.longitude,
                source_trace_ids_json=[str(x) for x in context.source_trace_ids],
                validation_status=context.validation_status.value,
                review_required=context.review_required, version=context.version,
            ))

    def find_jurisdiction_context_by_input(self, project_id: UUID, input_value: str) -> dict[str, object] | None:
        with self._sessions() as s:
            row=s.execute(
                select(JurisdictionContextEntity,JurisdictionResolutionEntity)
                .join(
                    JurisdictionResolutionEntity,
                    JurisdictionResolutionEntity.jurisdiction_context_id==JurisdictionContextEntity.jurisdiction_context_id,
                )
                .where(
                    JurisdictionContextEntity.tenant_id==self.tenant_id,
                    JurisdictionContextEntity.project_id==str(project_id),
                    func.lower(JurisdictionResolutionEntity.input_value)==input_value.strip().lower(),
                    JurisdictionResolutionEntity.action=="ACCEPTED",
                )
                .order_by(JurisdictionContextEntity.version.desc())
            ).first()
            if row is None:
                return None
            context,_=row
            return {
                "jurisdiction_context_id":context.jurisdiction_context_id,
                "jurisdiction_id":context.jurisdiction_id,
                "location_precision":context.location_precision,
                "version":context.version,
            }

    def save_jurisdiction_resolution(self, resolution: JurisdictionResolution) -> None:
        with self._sessions() as s, s.begin():
            s.add(JurisdictionResolutionEntity(
                jurisdiction_resolution_id=str(resolution.jurisdiction_resolution_id),
                project_id=str(resolution.project_id), tenant_id=self.tenant_id,
                input_value=resolution.input_value,
                jurisdiction_context_id=str(resolution.jurisdiction_context_id) if resolution.jurisdiction_context_id else None,
                action=resolution.action.value, confidence=resolution.confidence,
                reason_code=resolution.reason_code,
                source_trace_ids_json=[str(x) for x in resolution.source_trace_ids],
                review_required=resolution.review_required, version=resolution.version,
            ))

    def create_formal_flow_node(self, *, project_id: UUID, node_type: str, display_name: str, jurisdiction_id: UUID | None, detail: DataFlowNodeContext) -> UUID:
        with self._sessions() as s, s.begin():
            node_id = detail.flow_node_id
            s.add(DataFlowNodeEntity(
                flow_node_id=str(node_id), project_id=str(project_id), tenant_id=self.tenant_id,
                node_type=node_type, display_name=display_name,
                jurisdiction_id=str(jurisdiction_id) if jurisdiction_id else None,
            ))
            s.flush()
            s.add(DataFlowNodeDetailEntity(
                flow_node_id=str(node_id), tenant_id=self.tenant_id,
                system_id=str(detail.system_id) if detail.system_id else None,
                party_id=str(detail.party_id) if detail.party_id else None,
                jurisdiction_context_id=str(detail.jurisdiction_context_id) if detail.jurisdiction_context_id else None,
                storage_or_processing_role=detail.storage_or_processing_role,
                source_trace_ids_json=[str(x) for x in detail.source_trace_ids],
                confidence=detail.confidence, validation_status=detail.validation_status.value,
                version=detail.version,
            ))
            return node_id

    def create_formal_flow_edge(self, *, project_id: UUID, source_node_id: UUID, target_node_id: UUID, flow_type: str, detail: DataFlowEdgeContext) -> UUID:
        if source_node_id == target_node_id:
            raise ValueError("self-edge requires explicit future policy and is not accepted by Phase 1E")
        with self._sessions() as s, s.begin():
            for node_id in (source_node_id, target_node_id):
                node = self._get(s, DataFlowNodeEntity, DataFlowNodeEntity.flow_node_id, node_id)
                if node is None or node.project_id != str(project_id):
                    raise LookupError("flow source/destination not found in project scope")
            edge_id = detail.flow_edge_id
            s.add(DataFlowEdgeEntity(
                flow_edge_id=str(edge_id), project_id=str(project_id), tenant_id=self.tenant_id,
                source_node_id=str(source_node_id), target_node_id=str(target_node_id),
                flow_type=flow_type, route_sequence=None, declared_cross_border=None,
            ))
            s.flush()
            s.add(DataFlowEdgeDetailEntity(
                flow_edge_id=str(edge_id), tenant_id=self.tenant_id,
                transfer_type_definition_id=str(detail.transfer_type_ref) if detail.transfer_type_ref else None,
                direction=detail.direction, protocol_json=detail.protocol_metadata,
                frequency_json=detail.frequency_metadata,
                source_trace_ids_json=[str(x) for x in detail.source_trace_ids],
                confidence=detail.confidence, validation_status=detail.validation_status.value,
                version=detail.version,
            ))
            return edge_id

    def link_data_item_flow(self, *, data_item_id: UUID, flow_edge_id: UUID, relationship_type: str, source_trace_ids: tuple[UUID, ...], confidence: float) -> UUID:
        with self._sessions() as s, s.begin():
            item = self._get(s, DataItemEntity, DataItemEntity.data_item_id, data_item_id)
            edge = self._get(s, DataFlowEdgeEntity, DataFlowEdgeEntity.flow_edge_id, flow_edge_id)
            if item is None or edge is None or item.project_id != edge.project_id:
                raise LookupError("data item / flow edge not found in same project scope")
            row = DataItemFlowLinkEntity(
                link_id=str(uuid4()), data_item_id=str(data_item_id), flow_edge_id=str(flow_edge_id),
                purpose=None, volume_band=None, tenant_id=self.tenant_id,
            )
            s.add(row)
            s.flush()
            s.add(DataItemFlowLinkDetailEntity(
                link_id=row.link_id, relationship_type=relationship_type,
                source_trace_ids_json=[str(x) for x in source_trace_ids],
                confidence=confidence, tenant_id=self.tenant_id,
                data_inventory_version=s.get(DataFlowEdgeDetailEntity, str(flow_edge_id)).version,
            ))
            return UUID(row.link_id)

    def formal_data_item_by_candidate(self, candidate_id: UUID) -> UUID | None:
        with self._sessions() as s:
            value = s.scalar(select(DataItemCandidateLinkEntity.data_item_id).where(
                DataItemCandidateLinkEntity.tenant_id == self.tenant_id,
                DataItemCandidateLinkEntity.candidate_data_item_id == str(candidate_id),
            ))
            return UUID(value) if value else None

    def create_review_task(self, *, workflow_run_id: UUID, object_type: str, object_id: UUID, reason: str, idempotency_key: str) -> UUID:
        with self._sessions() as s:
            run = self._get(s, WorkflowRunEntity, WorkflowRunEntity.workflow_run_id, workflow_run_id)
            if run is None:
                raise LookupError("workflow run not found in tenant scope")
            existing = s.scalar(select(ReviewTaskEntity).where(
                ReviewTaskEntity.tenant_id == self.tenant_id,
                ReviewTaskEntity.idempotency_key == idempotency_key,
            ))
            if existing:
                return UUID(existing.review_id)
            review_id = uuid4()
            s.add(ReviewTaskEntity(
                review_id=str(review_id), workflow_run_id=str(workflow_run_id),
                thread_id=str(workflow_run_id), tenant_id=self.tenant_id,
                review_type="CONTEXT_RESOLUTION_REVIEW", object_type=object_type,
                object_id=str(object_id), reason=reason, status="PENDING",
                idempotency_key=idempotency_key,
            ))
            try:
                s.commit()
                return review_id
            except IntegrityError:
                s.rollback()
                existing = s.scalar(select(ReviewTaskEntity).where(
                    ReviewTaskEntity.tenant_id == self.tenant_id,
                    ReviewTaskEntity.idempotency_key == idempotency_key,
                ))
                if existing is None:
                    raise
                return UUID(existing.review_id)

    def start_context_run(self, project_id: UUID) -> dict[str, object]:
        with self._sessions() as s, s.begin():
            project = self._get(s, ProjectEntity, ProjectEntity.project_id, project_id)
            if project is None:
                raise LookupError("project not found")
            version = int(s.scalar(select(func.coalesce(func.max(ContextResolutionRunEntity.version), 0)).where(
                ContextResolutionRunEntity.tenant_id == self.tenant_id,
                ContextResolutionRunEntity.project_id == str(project_id),
            )) or 0) + 1
            run_id = uuid4()
            s.add(ContextResolutionRunEntity(
                context_resolution_run_id=str(run_id), project_id=str(project_id),
                tenant_id=self.tenant_id, version=version,
                product_context_version=version, data_inventory_version=version,
                data_flow_version=version, statistics_json={}, confidence=0.0,
                unresolved_count=0, conflict_count=0, review_required_count=0,
                status="RUNNING",
            ))
            return {"context_resolution_run_id": str(run_id), "version": version}

    def finish_context_run(self, context_resolution_run_id: UUID, *, statistics: dict[str, int], confidence: float) -> None:
        with self._sessions() as s, s.begin():
            row = self._get(s, ContextResolutionRunEntity, ContextResolutionRunEntity.context_resolution_run_id, context_resolution_run_id)
            if row is None:
                raise LookupError("context resolution run not found")
            row.statistics_json = statistics
            row.confidence = confidence
            row.unresolved_count = int(statistics.get("unresolved_count", 0))
            row.conflict_count = int(statistics.get("conflict_count", 0))
            row.review_required_count = int(statistics.get("review_required_count", 0))
            row.status = "COMPLETED"
            row.completed_at = _now()
            row.updated_at = _now()

    def get_business_context(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(BusinessFactEntity).where(
                BusinessFactEntity.tenant_id == self.tenant_id,
                BusinessFactEntity.project_id == str(project_id),
            ).order_by(BusinessFactEntity.fact_type, BusinessFactEntity.version)).all()
            return [{
                "fact_id": r.fact_id, "fact_type": r.fact_type,
                "normalized_value": r.normalized_value_json,
                "original_values": r.original_values_json,
                "source_document_ids": r.source_document_ids_json,
                "resolution_method": r.resolution_method, "confidence": r.confidence,
                "validation_status": r.validation_status, "conflict_status": r.conflict_status,
                "review_required": r.review_required, "version": r.version,
                "structured_provenance": r.structured_provenance_json,
            } for r in rows]

    def get_product_context(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(ProductContextEntity).where(
                ProductContextEntity.tenant_id == self.tenant_id,
                ProductContextEntity.project_id == str(project_id),
            ).order_by(ProductContextEntity.version)).all()
            out = []
            for r in rows:
                links = s.execute(select(
                    ProductContextDefinitionLinkEntity.dimension_type,
                    ProductContextDefinitionLinkEntity.definition_id,
                ).where(
                    ProductContextDefinitionLinkEntity.tenant_id == self.tenant_id,
                    ProductContextDefinitionLinkEntity.product_context_id == r.product_context_id,
                )).all()
                out.append({
                    "product_context_id": r.product_context_id, "source": r.source,
                    "confidence": r.confidence, "evidence_ids": r.evidence_ids_json,
                    "source_trace_ids": r.source_trace_ids_json,
                    "effective_scope": r.effective_scope_json,
                    "resolution_status": r.resolution_status,
                    "review_required": r.review_required, "version": r.version,
                    "definitions": [{"dimension_type": x[0], "definition_id": x[1]} for x in links],
                })
            return out

    def get_scenario_context(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(ScenarioContextEntity).where(
                ScenarioContextEntity.tenant_id == self.tenant_id,
                ScenarioContextEntity.project_id == str(project_id),
            )).all()
            return [{
                "scenario_context_id": r.scenario_context_id,
                "scenario_definition_id": r.scenario_definition_id,
                "source": r.source, "confidence": r.confidence,
                "source_trace_ids": r.source_trace_ids_json,
                "validation_status": r.validation_status,
                "review_required": r.review_required, "version": r.version,
            } for r in rows]

    def get_systems(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(SystemContextEntity).where(
                SystemContextEntity.tenant_id == self.tenant_id,
                SystemContextEntity.project_id == str(project_id),
            )).all()
            return [{
                "system_id": r.system_id, "display_name": r.display_name,
                "system_type_ref": r.system_type_ref, "product_context_refs": r.product_context_refs_json,
                "party_refs": r.party_refs_json, "location_refs": r.location_refs_json,
                "source_trace_ids": r.source_trace_ids_json, "confidence": r.confidence,
                "validation_status": r.validation_status, "version": r.version,
            } for r in rows]

    def get_devices(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(DeviceContextEntity).where(
                DeviceContextEntity.tenant_id == self.tenant_id,
                DeviceContextEntity.project_id == str(project_id),
            )).all()
            return [{
                "device_id": r.device_id, "display_name": r.display_name,
                "device_type_ref": r.device_type_ref, "system_id": r.system_id,
                "product_context_refs": r.product_context_refs_json,
                "source_trace_ids": r.source_trace_ids_json, "confidence": r.confidence,
                "validation_status": r.validation_status, "version": r.version,
            } for r in rows]

    def get_parties(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.execute(
                select(PartyResolutionEntity, PartyCandidateEntity)
                .join(PartyCandidateEntity, PartyCandidateEntity.party_candidate_id == PartyResolutionEntity.party_candidate_id)
                .where(
                    PartyResolutionEntity.tenant_id == self.tenant_id,
                    PartyCandidateEntity.project_id == str(project_id),
                )
            ).all()
            return [{
                "party_resolution_id": resolution.party_resolution_id,
                "party_candidate_id": candidate.party_candidate_id,
                "display_name": candidate.display_name,
                "project_party_id": resolution.project_party_id,
                "legal_entity_id": resolution.legal_entity_id,
                "action": resolution.action, "confidence": resolution.confidence,
                "reason_code": resolution.reason_code,
                "source_trace_ids": resolution.source_trace_ids_json,
                "review_required": resolution.review_required, "version": resolution.version,
            } for resolution, candidate in rows]

    def get_data_items(self, project_id: UUID, *, version: int | None = None) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.execute(
                select(DataItemEntity, DataItemResolutionDetailEntity)
                .join(DataItemResolutionDetailEntity, DataItemResolutionDetailEntity.data_item_id == DataItemEntity.data_item_id)
                .where(DataItemEntity.tenant_id == self.tenant_id, DataItemEntity.project_id == str(project_id),
                    DataItemResolutionDetailEntity.tenant_id == self.tenant_id,
                    *([DataItemResolutionDetailEntity.version == version] if version is not None else []))
            ).all()
            out = []
            for item, detail in rows:
                candidate_ids = list(s.scalars(select(DataItemCandidateLinkEntity.candidate_data_item_id).where(
                    DataItemCandidateLinkEntity.tenant_id == self.tenant_id,
                    DataItemCandidateLinkEntity.data_item_id == item.data_item_id,
                    DataItemCandidateLinkEntity.data_inventory_version == detail.version,
                )))
                trace_ids = list(s.scalars(select(DataItemSourceTraceLinkEntity.source_trace_ref_id).where(
                    DataItemSourceTraceLinkEntity.tenant_id == self.tenant_id,
                    DataItemSourceTraceLinkEntity.data_item_id == item.data_item_id,
                    DataItemSourceTraceLinkEntity.data_inventory_version == detail.version,
                )))
                out.append({
                    "data_item_id": item.data_item_id, "canonical_name": item.name,
                    "display_name": detail.display_name, "description": item.description,
                    "value_type": detail.value_type, "format": detail.format, "unit": detail.unit,
                    "frequency_quantity_metadata": detail.frequency_quantity_json,
                    "system_ids": detail.system_ids_json, "device_ids": detail.device_ids_json,
                    "raw_candidate_ids": candidate_ids, "source_trace_ids": trace_ids,
                    "confidence": detail.confidence, "validation_status": detail.validation_status,
                    "review_required": detail.review_required, "version": detail.version,
                })
            return out

    def get_data_groups(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(DataItemGroupEntity).where(
                DataItemGroupEntity.tenant_id == self.tenant_id,
                DataItemGroupEntity.project_id == str(project_id),
            )).all()
            return [{
                "data_item_group_id": r.data_item_group_id, "name": r.name,
                "grouping_reason": r.grouping_reason,
                "data_item_ids": list(s.scalars(select(DataItemGroupMemberEntity.data_item_id).where(
                    DataItemGroupMemberEntity.tenant_id == self.tenant_id,
                    DataItemGroupMemberEntity.data_item_group_id == r.data_item_group_id,
                ))),
            } for r in rows]

    def get_data_flows(self, project_id: UUID) -> dict[str, list[dict[str, object]]]:
        with self._sessions() as s:
            nodes = s.execute(
                select(DataFlowNodeEntity, DataFlowNodeDetailEntity)
                .join(DataFlowNodeDetailEntity, DataFlowNodeDetailEntity.flow_node_id == DataFlowNodeEntity.flow_node_id)
                .where(DataFlowNodeEntity.tenant_id == self.tenant_id, DataFlowNodeEntity.project_id == str(project_id))
            ).all()
            edges = s.execute(
                select(DataFlowEdgeEntity, DataFlowEdgeDetailEntity)
                .join(DataFlowEdgeDetailEntity, DataFlowEdgeDetailEntity.flow_edge_id == DataFlowEdgeEntity.flow_edge_id)
                .where(DataFlowEdgeEntity.tenant_id == self.tenant_id, DataFlowEdgeEntity.project_id == str(project_id))
            ).all()
            links = s.execute(
                select(DataItemFlowLinkEntity, DataItemFlowLinkDetailEntity)
                .join(DataItemFlowLinkDetailEntity, DataItemFlowLinkDetailEntity.link_id == DataItemFlowLinkEntity.link_id)
                .join(DataFlowEdgeEntity, DataFlowEdgeEntity.flow_edge_id == DataItemFlowLinkEntity.flow_edge_id)
                .where(DataItemFlowLinkEntity.tenant_id == self.tenant_id, DataFlowEdgeEntity.project_id == str(project_id))
            ).all()
            return {
                "nodes": [{
                    "flow_node_id": n.flow_node_id, "node_type": n.node_type,
                    "display_name": n.display_name, "jurisdiction_id": n.jurisdiction_id,
                    "system_id": d.system_id, "party_id": d.party_id,
                    "jurisdiction_context_id": d.jurisdiction_context_id,
                    "storage_or_processing_role": d.storage_or_processing_role,
                    "source_trace_ids": d.source_trace_ids_json, "confidence": d.confidence,
                    "validation_status": d.validation_status, "version": d.version,
                } for n, d in nodes],
                "edges": [{
                    "flow_edge_id": e.flow_edge_id, "source_node_id": e.source_node_id,
                    "target_node_id": e.target_node_id, "flow_type": e.flow_type,
                    "transfer_type_definition_id": d.transfer_type_definition_id,
                    "direction": d.direction, "protocol_metadata": d.protocol_json,
                    "frequency_metadata": d.frequency_json,
                    "source_trace_ids": d.source_trace_ids_json, "confidence": d.confidence,
                    "validation_status": d.validation_status, "version": d.version,
                } for e, d in edges],
                "data_item_links": [{
                    "link_id": l.link_id, "data_item_id": l.data_item_id,
                    "flow_edge_id": l.flow_edge_id, "relationship_type": d.relationship_type,
                    "source_trace_ids": d.source_trace_ids_json, "confidence": d.confidence,
                } for l, d in links],
            }

    def get_jurisdiction_context(self, project_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as s:
            rows = s.scalars(select(JurisdictionContextEntity).where(
                JurisdictionContextEntity.tenant_id == self.tenant_id,
                JurisdictionContextEntity.project_id == str(project_id),
            )).all()
            return [{
                "jurisdiction_context_id": r.jurisdiction_context_id,
                "jurisdiction_id": r.jurisdiction_id, "context_type": r.context_type,
                "location_precision": r.location_precision, "source": r.source,
                "confidence": r.confidence, "latitude": r.latitude, "longitude": r.longitude,
                "source_trace_ids": r.source_trace_ids_json,
                "validation_status": r.validation_status,
                "review_required": r.review_required, "version": r.version,
            } for r in rows]

    def aggregate_statistics(self, project_id: UUID) -> dict[str, int]:
        runs = self._project_parse_runs(project_id)
        with self._sessions() as s:
            raw_field_count = int(s.scalar(select(func.count()).select_from(CandidateDataItemEntity).where(
                CandidateDataItemEntity.tenant_id == self.tenant_id,
                CandidateDataItemEntity.parse_run_id.in_(runs),
            )) or 0)
            normalized = int(s.scalar(select(func.count()).select_from(DataItemEntity).where(
                DataItemEntity.tenant_id == self.tenant_id,
                DataItemEntity.project_id == str(project_id),
            )) or 0)
            groups = int(s.scalar(select(func.count()).select_from(DataItemGroupEntity).where(
                DataItemGroupEntity.tenant_id == self.tenant_id,
                DataItemGroupEntity.project_id == str(project_id),
            )) or 0)
            nodes = int(s.scalar(select(func.count()).select_from(DataFlowNodeEntity).where(
                DataFlowNodeEntity.tenant_id == self.tenant_id,
                DataFlowNodeEntity.project_id == str(project_id),
            )) or 0)
            edges = int(s.scalar(select(func.count()).select_from(DataFlowEdgeEntity).where(
                DataFlowEdgeEntity.tenant_id == self.tenant_id,
                DataFlowEdgeEntity.project_id == str(project_id),
            )) or 0)
            conflicts = int(s.scalar(select(func.count()).select_from(ContextConflictEntity).where(
                ContextConflictEntity.tenant_id == self.tenant_id,
                ContextConflictEntity.project_id == str(project_id),
                ContextConflictEntity.resolution_status != "RESOLVED",
            )) or 0)
            review = int(s.scalar(select(func.count()).select_from(ContextConflictEntity).where(
                ContextConflictEntity.tenant_id == self.tenant_id,
                ContextConflictEntity.project_id == str(project_id),
                ContextConflictEntity.review_required.is_(True),
                ContextConflictEntity.resolution_status != "RESOLVED",
            )) or 0)
            return {
                "raw_field_count": raw_field_count,
                "normalized_data_item_count": normalized,
                "data_group_count": groups,
                "data_flow_node_count": nodes,
                "data_flow_edge_count": edges,
                "unresolved_count": conflicts,
                "conflict_count": conflicts,
                "review_required_count": review,
            }

    def pin_snapshot_context(self, *, analysis_snapshot_id: UUID, project_id: UUID, context_resolution_run_id: UUID) -> None:
        with self._sessions() as s, s.begin():
            snapshot = self._get(s, AnalysisSnapshotEntity, AnalysisSnapshotEntity.analysis_snapshot_id, analysis_snapshot_id)
            run = self._get(s, ContextResolutionRunEntity, ContextResolutionRunEntity.context_resolution_run_id, context_resolution_run_id)
            if snapshot is None or run is None or run.project_id != str(project_id):
                raise LookupError("snapshot/context run not found in tenant scope")
            existing = s.scalar(select(AnalysisSnapshotContextPinEntity).where(
                AnalysisSnapshotContextPinEntity.tenant_id == self.tenant_id,
                AnalysisSnapshotContextPinEntity.analysis_snapshot_id == str(analysis_snapshot_id),
                AnalysisSnapshotContextPinEntity.project_id == str(project_id),
            ))
            if existing:
                if existing.context_resolution_run_id != str(context_resolution_run_id):
                    raise ValueError("analysis snapshot context pin is immutable")
                return
            s.add(AnalysisSnapshotContextPinEntity(
                analysis_snapshot_context_pin_id=str(uuid4()),
                analysis_snapshot_id=str(analysis_snapshot_id), project_id=str(project_id),
                context_resolution_run_id=str(context_resolution_run_id),
                context_resolution_version=run.version,
                product_context_version=run.product_context_version,
                data_inventory_version=run.data_inventory_version,
                data_flow_version=run.data_flow_version,
                tenant_id=self.tenant_id,
            ))

    def get_context_resolution(self, project_id: UUID) -> ContextResolutionResult | None:
        with self._sessions() as s:
            run = s.scalar(select(ContextResolutionRunEntity).where(
                ContextResolutionRunEntity.tenant_id == self.tenant_id,
                ContextResolutionRunEntity.project_id == str(project_id),
                ContextResolutionRunEntity.status == "COMPLETED",
                *([ContextResolutionRunEntity.context_resolution_run_id == str(self.context_resolution_run_id)]
                  if self.context_resolution_run_id is not None else []),
            ).order_by(ContextResolutionRunEntity.version.desc()))
            if run is None:
                return None
        version=run.version
        facts=[x for x in self.get_business_context(project_id) if int(x["version"])==version]
        product_rows=[x for x in self.get_product_context(project_id) if int(x["version"])==version]
        scenario_rows=[x for x in self.get_scenario_context(project_id) if int(x["version"])==version]
        system_rows=[x for x in self.get_systems(project_id) if int(x["version"])==version]
        device_rows=[x for x in self.get_devices(project_id) if int(x["version"])==version]
        party_rows=[x for x in self.get_parties(project_id) if int(x["version"])==version]
        jurisdiction_rows=[x for x in self.get_jurisdiction_context(project_id) if int(x["version"])==version]
        conflict_rows=[x for x in self.list_conflicts(project_id) if int(x["version"])==version]

        product_contexts=[]
        for row in product_rows:
            dimensions={k:[] for k in ["PRODUCT_DOMAIN","PRODUCT_CATEGORY","PRODUCT_FAMILY","PRODUCT","PRODUCT_TAG"]}
            for definition in row["definitions"]:
                if definition["dimension_type"] in dimensions:
                    dimensions[definition["dimension_type"]].append(UUID(str(definition["definition_id"])))
            product_contexts.append(ProductContext(
                product_context_id=UUID(str(row["product_context_id"])),project_id=project_id,
                product_domain_ids=tuple(dimensions["PRODUCT_DOMAIN"]),
                product_category_ids=tuple(dimensions["PRODUCT_CATEGORY"]),
                product_family_ids=tuple(dimensions["PRODUCT_FAMILY"]),
                product_ids=tuple(dimensions["PRODUCT"]),
                product_tag_ids=tuple(dimensions["PRODUCT_TAG"]),
                source=str(row["source"]),confidence=float(row["confidence"]),
                evidence_ids=tuple(UUID(x) for x in row.get("evidence_ids",[])),
                source_trace_ids=tuple(UUID(x) for x in row.get("source_trace_ids",[])),
                effective_scope=tuple(UUID(x) for x in row.get("effective_scope",[])),
                resolution_status=str(row["resolution_status"]),
                review_required=bool(row["review_required"]),version=version,
            ))
        scenario_contexts=tuple(ScenarioContext(
            UUID(str(row["scenario_context_id"])),project_id,
            UUID(str(row["scenario_definition_id"])) if row.get("scenario_definition_id") else None,
            str(row["source"]),float(row["confidence"]),
            tuple(UUID(x) for x in row.get("source_trace_ids",[])),
            ContextValidationStatus(str(row["validation_status"])),
            bool(row["review_required"]),version,
        ) for row in scenario_rows)
        system_contexts=tuple(SystemContext(
            UUID(str(row["system_id"])),project_id,str(row["display_name"]),
            UUID(str(row["system_type_ref"])) if row.get("system_type_ref") else None,
            tuple(UUID(x) for x in row.get("product_context_refs",[])),
            tuple(UUID(x) for x in row.get("party_refs",[])),
            tuple(UUID(x) for x in row.get("location_refs",[])),
            tuple(UUID(x) for x in row.get("source_trace_ids",[])),
            float(row["confidence"]),ContextValidationStatus(str(row["validation_status"])),version,
        ) for row in system_rows)
        device_contexts=tuple(DeviceContext(
            UUID(str(row["device_id"])),project_id,str(row["display_name"]),
            UUID(str(row["device_type_ref"])) if row.get("device_type_ref") else None,
            UUID(str(row["system_id"])) if row.get("system_id") else None,
            tuple(UUID(x) for x in row.get("product_context_refs",[])),
            tuple(UUID(x) for x in row.get("source_trace_ids",[])),
            float(row["confidence"]),ContextValidationStatus(str(row["validation_status"])),version,
        ) for row in device_rows)
        party_contexts=tuple(PartyResolution(
            UUID(str(row["party_resolution_id"])),UUID(str(row["party_candidate_id"])),
            UUID(str(row["project_party_id"])) if row.get("project_party_id") else None,
            UUID(str(row["legal_entity_id"])) if row.get("legal_entity_id") else None,
            ResolutionAction(str(row["action"])),float(row["confidence"]),
            str(row.get("reason_code") or "PERSISTED_PARTY_RESOLUTION"),
            tuple(UUID(x) for x in row.get("source_trace_ids",[])),
            bool(row["review_required"]),version,
        ) for row in party_rows)
        jurisdiction_contexts=tuple(JurisdictionContext(
            UUID(str(row["jurisdiction_context_id"])),project_id,
            UUID(str(row["jurisdiction_id"])) if row.get("jurisdiction_id") else None,
            str(row["context_type"]),LocationPrecision(str(row["location_precision"])),
            str(row["source"]),float(row["confidence"]),row.get("latitude"),row.get("longitude"),
            tuple(UUID(x) for x in row.get("source_trace_ids",[])),
            ContextValidationStatus(str(row["validation_status"])),
            bool(row["review_required"]),version,
        ) for row in jurisdiction_rows)
        conflicts=tuple(ContextConflict(
            UUID(str(row["conflict_id"])),project_id,str(row["conflict_type"]),
            str(row["object_type"]),tuple(UUID(x) for x in row.get("object_ids",[])),
            str(row["reason_code"]),dict(row.get("details") or {}),
            tuple(UUID(x) for x in row.get("source_trace_ids",[])),
            float(row["confidence"]),str(row["resolution_status"]),
            bool(row["review_required"]),version,
        ) for row in conflict_rows)
        conflict_ids=[str(x.conflict_id) for x in conflicts]
        if conflict_ids:
            with self._sessions() as s:
                review_ids=tuple(UUID(x) for x in s.scalars(select(ReviewTaskEntity.review_id).where(
                    ReviewTaskEntity.tenant_id==self.tenant_id,
                    ReviewTaskEntity.object_type=="CONTEXT_CONFLICT",
                    ReviewTaskEntity.object_id.in_(conflict_ids),
                )))
        else:
            review_ids=()
        flows=self.get_data_flows(project_id)
        latest_edge_ids={x["flow_edge_id"] for x in flows["edges"] if int(x["version"])==version}
        latest_flows={
            "nodes":[x for x in flows["nodes"] if int(x["version"])==version],
            "edges":[x for x in flows["edges"] if int(x["version"])==version],
            "data_item_links":[x for x in flows["data_item_links"] if x["flow_edge_id"] in latest_edge_ids],
        }
        with self._sessions() as s:
            project_runs = self._project_parse_runs(project_id)
            candidate_ids = set()
            for model, identity in ((BusinessFactCandidateEntity, BusinessFactCandidateEntity.fact_id), (CandidateDataItemEntity, CandidateDataItemEntity.candidate_data_item_id), (CandidateDataFlowEdgeEntity, CandidateDataFlowEdgeEntity.candidate_edge_id)):
                candidate_ids.update(s.scalars(select(identity).where(
                    model.tenant_id == self.tenant_id, model.parse_run_id.in_(project_runs),
                )).all())
            unresolved_candidates = tuple(s.scalars(select(CandidateResolutionEntity.resolution_reason_code).where(
                CandidateResolutionEntity.tenant_id == self.tenant_id,
                CandidateResolutionEntity.version == run.data_inventory_version,
                CandidateResolutionEntity.candidate_id.in_(candidate_ids),
                CandidateResolutionEntity.action == "REVIEW_REQUIRED",
            )).all())
        stats=run.statistics_json
        return ContextResolutionResult(
            context_resolution_run_id=UUID(run.context_resolution_run_id),
            project_id=project_id,
            business_fact_summary={"facts":facts},
            product_contexts=tuple(product_contexts),
            scenario_contexts=scenario_contexts,
            system_contexts=system_contexts,
            device_contexts=device_contexts,
            party_contexts=party_contexts,
            data_inventory_summary={"items":self.get_data_items(project_id, version=run.data_inventory_version),"groups":self.get_data_groups(project_id)},
            data_flow_summary=latest_flows,
            jurisdiction_contexts=jurisdiction_contexts,
            unresolved_items=tuple(dict.fromkeys([x.reason_code for x in conflicts if x.resolution_status!="RESOLVED"] + list(unresolved_candidates))),
            conflicts=conflicts,review_task_ids=review_ids,
            statistics=ContextStatistics(**stats),
            confidence=run.confidence,version=version,
        )
