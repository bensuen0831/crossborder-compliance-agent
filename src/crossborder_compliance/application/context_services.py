from __future__ import annotations

import re
from dataclasses import asdict
from itertools import combinations
from uuid import UUID, uuid4

from crossborder_compliance.application.context_ports import (
    CandidateSimilarityPort, ContextResolutionRepositoryPort,
)
from crossborder_compliance.domain.context_resolution import (
    BusinessFact, CandidateResolution, ContextConflict,
    ContextValidationStatus, DataFlowEdgeContext, DataFlowNodeContext,
    DataItemDeduplicationResult, DataItemResolutionDetail, DedupDecision,
    DeviceContext, JurisdictionContext, JurisdictionResolution,
    LocationPrecision, PartyCandidate, PartyResolution, ProductContext,
    ProductScopeResolution, ResolutionAction, ScenarioContext, SystemContext,
)


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_key(value: object) -> str:
    return _norm(value).casefold()


class BusinessFactNormalizationService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def normalize(self, project_id: UUID, *, version: int) -> list[BusinessFact]:
        candidates = self.repository.list_candidate_facts(project_id)
        groups: dict[tuple[str, str], list[dict[str, object]]] = {}
        for candidate in candidates:
            fact_type = str(candidate["fact_type"])
            registry = getattr(self.repository, "metadata_definition_by_code")(
                kind="BUSINESS_FACT_TYPE", code=fact_type
            )
            trace_ids = tuple(UUID(x) for x in candidate.get("source_trace_ids", []))
            if registry is None:
                self.repository.save_candidate_resolution(CandidateResolution(
                    uuid4(), "BUSINESS_FACT", UUID(str(candidate["candidate_id"])),
                    "BUSINESS_FACT", None, ResolutionAction.REVIEW_REQUIRED,
                    float(candidate.get("confidence", 0.0)), "FACT_TYPE_NOT_IN_ACTIVE_REGISTRY",
                    trace_ids, True, None, "POLICY", version,
                ))
                continue
            key = (fact_type, _norm_key(candidate.get("normalized_value")))
            groups.setdefault(key, []).append(candidate)

        results: list[BusinessFact] = []
        for (fact_type, _), rows in groups.items():
            normalized_value = rows[0].get("normalized_value")
            trace_ids = tuple(dict.fromkeys(
                UUID(x) for row in rows for x in row.get("source_trace_ids", [])
            ))
            document_ids = tuple(dict.fromkeys(
                UUID(x) for row in rows for x in row.get("source_document_ids", [])
            ))
            confidence = min(float(row.get("confidence", 0.0)) for row in rows)
            fact = BusinessFact(
                fact_id=uuid4(), project_id=project_id, fact_type=fact_type,
                normalized_value=normalized_value,
                original_values=tuple(row.get("original_value") for row in rows),
                source_trace_ids=trace_ids, source_document_ids=document_ids,
                resolution_method="DETERMINISTIC_NORMALIZATION",
                confidence=confidence, validation_status=ContextValidationStatus.VALIDATED,
                conflict_status="NONE", review_required=False, version=version,
            )
            self.repository.save_business_fact(
                fact, tuple(UUID(str(row["candidate_id"])) for row in rows)
            )
            for row in rows:
                self.repository.save_candidate_resolution(CandidateResolution(
                    uuid4(), "BUSINESS_FACT", UUID(str(row["candidate_id"])),
                    "BUSINESS_FACT", fact.fact_id,
                    ResolutionAction.ACCEPTED if len(rows) == 1 else ResolutionAction.MERGED,
                    confidence, "FACT_NORMALIZED", trace_ids, False, None, "POLICY", version,
                ))
            results.append(fact)
        return results


class ProductContextResolutionService:
    ALLOWED_KINDS = {
        "PRODUCT_DOMAIN", "PRODUCT_CATEGORY", "PRODUCT_FAMILY", "PRODUCT", "PRODUCT_TAG"
    }

    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def _validate(self, ids: tuple[UUID, ...]) -> dict[str, tuple[UUID, ...]]:
        buckets: dict[str, list[UUID]] = {kind: [] for kind in self.ALLOWED_KINDS}
        for definition_id in ids:
            row = self.repository.metadata_definition(definition_id)
            if row is None or str(row["kind"]) not in self.ALLOWED_KINDS:
                raise ValueError("product context must reference ACTIVE Product Registry definitions")
            buckets[str(row["kind"])].append(definition_id)
        return {k: tuple(v) for k, v in buckets.items()}

    def resolve(
        self, project_id: UUID, *, selected_scope: tuple[UUID, ...],
        detected_scope: tuple[UUID, ...], source_trace_ids: tuple[UUID, ...] = (),
        version: int,
    ) -> ProductScopeResolution:
        selected = self._validate(tuple(dict.fromkeys(selected_scope)))
        detected = self._validate(tuple(dict.fromkeys(detected_scope)))
        selected_flat = tuple(dict.fromkeys(x for v in selected.values() for x in v))
        detected_flat = tuple(dict.fromkeys(x for v in detected.values() for x in v))

        conflict_id = None
        review = False
        if selected_flat and detected_flat and set(selected_flat) != set(detected_flat):
            conflict_id = uuid4()
            review = True
            self.repository.save_conflict(ContextConflict(
                conflict_id, project_id, "PRODUCT_CONTEXT_CONFLICT", "PRODUCT_CONTEXT",
                tuple(dict.fromkeys(selected_flat + detected_flat)),
                "EXPLICIT_SELECTION_DIFFERS_FROM_DOCUMENT_DETECTION",
                {
                    "selected_product_scope": [str(x) for x in selected_flat],
                    "detected_product_context": [str(x) for x in detected_flat],
                },
                source_trace_ids, 1.0, "OPEN", True, version,
            ))
            effective: tuple[UUID, ...] = ()
            status = "REVIEW_REQUIRED"
        else:
            # Document-first when no selection; never broaden to every product.
            effective = selected_flat or detected_flat
            status = "RESOLVED" if effective else "GENERIC_UNRESOLVED"

        combined = self._validate(effective) if effective else {k: () for k in self.ALLOWED_KINDS}
        context = ProductContext(
            product_context_id=uuid4(), project_id=project_id,
            product_domain_ids=combined["PRODUCT_DOMAIN"],
            product_category_ids=combined["PRODUCT_CATEGORY"],
            product_family_ids=combined["PRODUCT_FAMILY"],
            product_ids=combined["PRODUCT"], product_tag_ids=combined["PRODUCT_TAG"],
            source=("EXPLICIT_USER_SELECTION" if selected_flat else
                    "DOCUMENT_DERIVED" if detected_flat else "GENERIC"),
            confidence=1.0 if selected_flat else (0.85 if detected_flat else 0.0),
            source_trace_ids=source_trace_ids, effective_scope=effective,
            resolution_status=status, review_required=review, version=version,
        )
        self.repository.save_product_context(context)
        resolution = ProductScopeResolution(
            uuid4(), project_id, selected_flat, detected_flat, effective,
            conflict_id, status, review, version,
        )
        self.repository.save_product_scope_resolution(resolution)
        return resolution


class ScenarioResolutionService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def resolve(
        self, project_id: UUID, *, selected: tuple[UUID, ...],
        detected: tuple[UUID, ...], source_trace_ids: tuple[UUID, ...] = (),
        version: int,
    ) -> list[ScenarioContext]:
        ids = tuple(dict.fromkeys(selected or detected))
        out: list[ScenarioContext] = []
        for definition_id in ids:
            row = self.repository.metadata_definition(definition_id)
            if row is None or row["kind"] != "SCENARIO":
                raise ValueError("scenario context must reference ACTIVE Scenario Registry")
            context = ScenarioContext(
                uuid4(), project_id, definition_id,
                "EXPLICIT_USER_SELECTION" if selected else "DOCUMENT_DERIVED",
                1.0 if selected else 0.85, source_trace_ids,
                ContextValidationStatus.VALIDATED, False, version,
            )
            self.repository.save_scenario_context(context)
            out.append(context)
        if selected and detected and set(selected) != set(detected):
            self.repository.save_conflict(ContextConflict(
                uuid4(), project_id, "SCENARIO_CONTEXT_CONFLICT", "SCENARIO_CONTEXT",
                tuple(dict.fromkeys(selected + detected)), "SCENARIO_SELECTION_DIFFERS_FROM_DETECTION",
                {}, source_trace_ids, 1.0, "OPEN", True, version,
            ))
        return out


class SystemContextResolutionService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def create_system(
        self, project_id: UUID, *, display_name: str, system_type_ref: UUID | None,
        product_context_refs: tuple[UUID, ...] = (), party_refs: tuple[UUID, ...] = (),
        location_refs: tuple[UUID, ...] = (), source_trace_ids: tuple[UUID, ...] = (),
        confidence: float = 1.0, version: int,
    ) -> SystemContext:
        if system_type_ref:
            row = self.repository.metadata_definition(system_type_ref)
            if row is None or row["kind"] != "SYSTEM_TYPE":
                raise ValueError("system type must be an ACTIVE registry definition")
        context = SystemContext(
            uuid4(), project_id, _norm(display_name), system_type_ref,
            product_context_refs, party_refs, location_refs, source_trace_ids,
            confidence, ContextValidationStatus.VALIDATED, version,
        )
        self.repository.save_system_context(context)
        return context

    def create_device(
        self, project_id: UUID, *, display_name: str, device_type_ref: UUID | None,
        system_id: UUID | None, product_context_refs: tuple[UUID, ...] = (),
        source_trace_ids: tuple[UUID, ...] = (), confidence: float = 1.0,
        version: int,
    ) -> DeviceContext:
        if device_type_ref:
            row = self.repository.metadata_definition(device_type_ref)
            if row is None or row["kind"] != "DEVICE_TYPE":
                raise ValueError("device type must be an ACTIVE registry definition")
        context = DeviceContext(
            uuid4(), project_id, _norm(display_name), device_type_ref, system_id,
            product_context_refs, source_trace_ids, confidence,
            ContextValidationStatus.VALIDATED, version,
        )
        self.repository.save_device_context(context)
        return context


class PartyResolutionService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def resolve(
        self, project_id: UUID, *, display_name: str, role_definition_id: UUID | None,
        source_trace_ids: tuple[UUID, ...] = (), confidence: float = 0.9,
        version: int,
    ) -> PartyResolution:
        if role_definition_id:
            row = self.repository.metadata_definition(role_definition_id)
            if row is None or row["kind"] != "PARTY_ROLE":
                raise ValueError("party role must be an ACTIVE registry definition")
        candidate = PartyCandidate(
            uuid4(), project_id, _norm(display_name), role_definition_id,
            source_trace_ids, confidence,
        )
        self.repository.save_party_candidate(candidate)
        party = self.repository.find_project_party_by_name(project_id, candidate.display_name)
        resolution = PartyResolution(
            uuid4(), candidate.party_candidate_id,
            UUID(str(party["project_party_id"])) if party else None,
            UUID(str(party["legal_entity_id"])) if party and party.get("legal_entity_id") else None,
            ResolutionAction.ACCEPTED if party else ResolutionAction.REVIEW_REQUIRED,
            confidence if party else min(confidence, 0.5),
            "EXACT_PROJECT_PARTY_ALIAS" if party else "UNRESOLVED_PARTY",
            source_trace_ids, not bool(party), version,
        )
        self.repository.save_party_resolution(resolution)
        return resolution


class DataItemDeduplicationService:
    def __init__(
        self, repository: ContextResolutionRepositoryPort,
        similarity: CandidateSimilarityPort | None = None,
    ):
        self.repository = repository
        self.similarity = similarity

    def compare(
        self, project_id: UUID, left: dict[str, object], right: dict[str, object],
        *, version: int,
    ) -> DataItemDeduplicationResult:
        same_name = _norm_key(left.get("normalized_name")) == _norm_key(right.get("normalized_name"))
        same_structure = (
            left.get("value_type") == right.get("value_type")
            and left.get("unit") == right.get("unit")
        )
        deterministic = 1.0 if same_name and same_structure else (0.8 if same_name else 0.0)
        semantic = self.similarity.candidate_similarity(left=left, right=right) if self.similarity else None
        if deterministic >= 0.8:
            decision = DedupDecision.SAME_ITEM
            review = False
            reason = "DETERMINISTIC_NORMALIZED_NAME"
        elif semantic is not None and semantic >= 0.8:
            # Semantic evidence is suggestion-only. Formal merge is not performed here.
            decision = DedupDecision.POSSIBLE_SAME
            review = True
            reason = "SEMANTIC_CANDIDATE_ONLY"
        else:
            decision = DedupDecision.DIFFERENT
            review = False
            reason = "DETERMINISTIC_DIFFERENT"
        result = DataItemDeduplicationResult(
            uuid4(), project_id, UUID(str(left["candidate_id"])),
            UUID(str(right["candidate_id"])), decision, deterministic,
            semantic, reason, review, version,
        )
        self.repository.save_dedup_result(result)
        return result


class DataItemNormalizationService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def normalize(self, project_id: UUID, *, version: int) -> dict[str, UUID]:
        candidates = self.repository.list_candidate_items(project_id)
        grouped: dict[str, list[dict[str, object]]] = {}
        for candidate in candidates:
            key = _norm_key(candidate.get("normalized_name") or candidate.get("raw_name"))
            if key:
                grouped.setdefault(key, []).append(candidate)

        candidate_to_formal: dict[str, UUID] = {}
        for canonical_name, rows in grouped.items():
            trace_ids = tuple(dict.fromkeys(
                UUID(x) for row in rows for x in row.get("source_trace_ids", [])
            ))
            if not trace_ids:
                raise ValueError("formal DataItem requires SourceTrace")
            confidence = min(float(row.get("confidence", 0.0)) for row in rows)
            detail = DataItemResolutionDetail(
                data_item_id=uuid4(), display_name=str(rows[0].get("raw_name") or canonical_name),
                value_type=next((str(r["value_type"]) for r in rows if r.get("value_type")), None),
                format=None,
                unit=next((str(r["unit"]) for r in rows if r.get("unit")), None),
                frequency_quantity_metadata=next(
                    (dict(r.get("quantity_metadata") or {}) for r in rows if r.get("quantity_metadata")), {}
                ),
                system_ids=(), device_ids=(), source_trace_ids=trace_ids,
                raw_candidate_ids=tuple(UUID(str(r["candidate_id"])) for r in rows),
                confidence=confidence, validation_status=ContextValidationStatus.VALIDATED,
                review_required=False, version=version,
            )
            source_version = next(
                (UUID(str(r["document_version_id"])) for r in rows if r.get("document_version_id")), None
            )
            item_id = self.repository.create_formal_data_item(
                project_id=project_id, canonical_name=canonical_name,
                description=next((str(r["description"]) for r in rows if r.get("description")), None),
                source_document_version_id=source_version, source_trace_id=trace_ids[0], detail=detail,
            )
            for row in rows:
                candidate_id = UUID(str(row["candidate_id"]))
                row_trace_ids = tuple(UUID(x) for x in row.get("source_trace_ids", []))
                self.repository.attach_candidate_to_data_item(
                    data_item_id=item_id, candidate_id=candidate_id,
                    source_trace_ids=row_trace_ids,
                )
                self.repository.save_candidate_resolution(CandidateResolution(
                    uuid4(), "DATA_ITEM", candidate_id, "DATA_ITEM", item_id,
                    ResolutionAction.ACCEPTED if len(rows) == 1 else ResolutionAction.MERGED,
                    confidence, "DETERMINISTIC_DATA_ITEM_NORMALIZATION",
                    row_trace_ids, False, None, "POLICY", version,
                ))
                candidate_to_formal[str(candidate_id)] = item_id
        return candidate_to_formal


class DataItemGroupingService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def group(
        self, project_id: UUID, *, name: str, data_item_ids: tuple[UUID, ...],
        grouping_reason: str = "LOGICAL_CONTEXT_GROUP",
    ) -> UUID:
        return self.repository.ensure_data_group(
            project_id=project_id, name=_norm(name), grouping_reason=grouping_reason,
            data_item_ids=tuple(dict.fromkeys(data_item_ids)),
        )


class DataFlowResolutionService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def resolve(
        self, project_id: UUID, *, data_item_candidate_bindings: dict[str, list[str]],
        version: int,
    ) -> dict[str, list[UUID]]:
        candidate_nodes = self.repository.list_candidate_flow_nodes(project_id)
        candidate_edges = self.repository.list_candidate_flow_edges(project_id)
        node_map: dict[str, UUID] = {}
        formal_nodes: list[UUID] = []
        formal_edges: list[UUID] = []

        for node in candidate_nodes:
            candidate_id = UUID(str(node["candidate_node_id"]))
            traces = tuple(UUID(x) for x in node.get("source_trace_ids", []))
            if not traces:
                raise ValueError("formal DataFlow node requires SourceTrace")
            node_type=str(node.get("node_type_candidate") or "UNRESOLVED")
            display_name=str(node.get("name") or "Unnamed")
            resolved_system=self.repository.find_system_by_name(project_id, display_name) if node_type=="SYSTEM" else None
            if node_type=="SYSTEM" and resolved_system is None:
                confidence=float(node.get("confidence", 0.0))
                self.repository.save_conflict(ContextConflict(
                    uuid4(), project_id, "SYSTEM_CONTEXT_CONFLICT", "DATA_FLOW_NODE",
                    (candidate_id,), "FLOW_SYSTEM_UNRESOLVED", {"display_name":display_name},
                    traces, confidence, "OPEN", True, version,
                ))
                self.repository.save_candidate_resolution(CandidateResolution(
                    uuid4(), "DATA_FLOW_NODE", candidate_id, "DATA_FLOW_NODE", None,
                    ResolutionAction.CONFLICT, confidence, "FLOW_SYSTEM_UNRESOLVED",
                    traces, True, None, "POLICY", version,
                ))
                continue
            node_id = uuid4()
            detail = DataFlowNodeContext(
                node_id,
                UUID(str(resolved_system["system_id"])) if resolved_system else None,
                None, None, None, traces,
                float(node.get("confidence", 0.0)),
                ContextValidationStatus.VALIDATED, version,
            )
            self.repository.create_formal_flow_node(
                project_id=project_id,
                node_type=node_type,
                display_name=display_name,
                jurisdiction_id=None, detail=detail,
            )
            self.repository.save_candidate_resolution(CandidateResolution(
                uuid4(), "DATA_FLOW_NODE", candidate_id, "DATA_FLOW_NODE", node_id,
                ResolutionAction.ACCEPTED, detail.confidence,
                "STRUCTURED_FLOW_NODE_RESOLUTION", traces, False, None, "POLICY", version,
            ))
            node_map[str(candidate_id)] = node_id
            formal_nodes.append(node_id)

        for edge in candidate_edges:
            candidate_edge_id = UUID(str(edge["candidate_edge_id"]))
            traces = tuple(UUID(x) for x in edge.get("source_trace_ids", []))
            source_id = node_map.get(str(edge["source_candidate_node_id"]))
            target_id = node_map.get(str(edge["target_candidate_node_id"]))
            if source_id is None or target_id is None:
                confidence=float(edge.get("confidence", 0.0))
                self.repository.save_conflict(ContextConflict(
                    uuid4(), project_id, "SOURCE_DESTINATION_CONFLICT", "DATA_FLOW_EDGE",
                    (candidate_edge_id,), "FLOW_ENDPOINT_UNRESOLVED", {}, traces,
                    confidence, "OPEN", True, version,
                ))
                self.repository.save_candidate_resolution(CandidateResolution(
                    uuid4(), "DATA_FLOW_EDGE", candidate_edge_id, "DATA_FLOW_EDGE", None,
                    ResolutionAction.CONFLICT, confidence, "FLOW_ENDPOINT_UNRESOLVED",
                    traces, True, None, "POLICY", version,
                ))
                continue
            direction = str(edge.get("direction") or "").strip()
            if not direction or direction.upper() == "UNKNOWN":
                confidence=float(edge.get("confidence", 0.0))
                self.repository.save_conflict(ContextConflict(
                    uuid4(), project_id, "FLOW_DIRECTION_CONFLICT", "DATA_FLOW_EDGE",
                    (candidate_edge_id,), "FLOW_DIRECTION_UNRESOLVED", {}, traces,
                    confidence, "OPEN", True, version,
                ))
                self.repository.save_candidate_resolution(CandidateResolution(
                    uuid4(), "DATA_FLOW_EDGE", candidate_edge_id, "DATA_FLOW_EDGE", None,
                    ResolutionAction.CONFLICT, confidence, "FLOW_DIRECTION_UNRESOLVED",
                    traces, True, None, "POLICY", version,
                ))
                continue
            candidate_item_ids = [
                UUID(x) for x in data_item_candidate_bindings.get(str(candidate_edge_id), [])
            ]
            formal_item_ids = tuple(dict.fromkeys(
                item_id for item_id in (
                    self.repository.formal_data_item_by_candidate(x) for x in candidate_item_ids
                ) if item_id is not None
            ))
            if not formal_item_ids:
                confidence=float(edge.get("confidence", 0.0))
                self.repository.save_conflict(ContextConflict(
                    uuid4(), project_id, "DATA_ITEM_FLOW_CONFLICT", "DATA_FLOW_EDGE",
                    (candidate_edge_id,), "NO_RESOLVED_DATA_ITEM_FOR_FLOW", {}, traces,
                    confidence, "OPEN", True, version,
                ))
                self.repository.save_candidate_resolution(CandidateResolution(
                    uuid4(), "DATA_FLOW_EDGE", candidate_edge_id, "DATA_FLOW_EDGE", None,
                    ResolutionAction.CONFLICT, confidence, "NO_RESOLVED_DATA_ITEM_FOR_FLOW",
                    traces, True, None, "POLICY", version,
                ))
                continue
            edge_id = uuid4()
            detail = DataFlowEdgeContext(
                edge_id, None, direction, {}, {}, traces,
                float(edge.get("confidence", 0.0)),
                ContextValidationStatus.VALIDATED, version,
            )
            self.repository.create_formal_flow_edge(
                project_id=project_id, source_node_id=source_id, target_node_id=target_id,
                flow_type=str(edge.get("transfer_type_candidate") or "FLOW"), detail=detail,
            )
            for data_item_id in formal_item_ids:
                self.repository.link_data_item_flow(
                    data_item_id=data_item_id, flow_edge_id=edge_id,
                    relationship_type="CARRIED_ON_FLOW", source_trace_ids=traces,
                    confidence=detail.confidence,
                )
            self.repository.save_candidate_resolution(CandidateResolution(
                uuid4(), "DATA_FLOW_EDGE", candidate_edge_id, "DATA_FLOW_EDGE", edge_id,
                ResolutionAction.ACCEPTED, detail.confidence,
                "STRUCTURED_FLOW_EDGE_RESOLUTION", traces, False, None, "POLICY", version,
            ))
            formal_edges.append(edge_id)
        return {"nodes": formal_nodes, "edges": formal_edges}


class JurisdictionResolutionService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def resolve(
        self, project_id: UUID, *, jurisdiction_id: UUID | None, input_value: str,
        context_type: str, precision: LocationPrecision, source: str,
        confidence: float, source_trace_ids: tuple[UUID, ...] = (),
        latitude: float | None = None, longitude: float | None = None,
        version: int,
    ) -> JurisdictionResolution:
        if jurisdiction_id and not self.repository.jurisdiction_exists(jurisdiction_id):
            raise ValueError("jurisdiction must come from canonical Jurisdiction Registry")
        if (latitude is not None or longitude is not None) and precision != LocationPrecision.EXACT_CANONICAL:
            raise ValueError("formal coordinates require EXACT_CANONICAL location precision")
        if precision == LocationPrecision.EXACT_CANONICAL and jurisdiction_id is None:
            raise ValueError("EXACT_CANONICAL location requires canonical jurisdiction")
        accepted = jurisdiction_id is not None
        context_id = uuid4()
        context = JurisdictionContext(
            context_id, project_id, jurisdiction_id, context_type, precision, source,
            confidence, latitude, longitude, source_trace_ids,
            ContextValidationStatus.VALIDATED if accepted else ContextValidationStatus.REVIEW_REQUIRED,
            not accepted, version,
        )
        self.repository.save_jurisdiction_context(context)
        resolution = JurisdictionResolution(
            uuid4(), project_id, input_value, context_id,
            ResolutionAction.ACCEPTED if accepted else ResolutionAction.REVIEW_REQUIRED,
            confidence, "CANONICAL_JURISDICTION" if accepted else "JURISDICTION_AMBIGUOUS",
            source_trace_ids, not accepted, version,
        )
        self.repository.save_jurisdiction_resolution(resolution)
        if not accepted:
            self.repository.save_conflict(ContextConflict(
                uuid4(), project_id, "LOCATION_CONTEXT_CONFLICT", "JURISDICTION_CONTEXT",
                (context_id,), "JURISDICTION_AMBIGUOUS", {"input_value": input_value},
                source_trace_ids, confidence, "OPEN", True, version,
            ))
        return resolution


class ContextValidationService:
    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository

    def validate(
        self, project_id: UUID, *, workflow_run_id: UUID | None = None,
    ) -> tuple[dict[str, int], tuple[UUID, ...]]:
        stats = self.repository.aggregate_statistics(project_id)
        review_ids: list[UUID] = []
        if workflow_run_id:
            for conflict in self.repository.list_conflicts(project_id):
                if conflict["resolution_status"] != "RESOLVED" and conflict["review_required"]:
                    review_ids.append(self.repository.create_review_task(
                        workflow_run_id=workflow_run_id, object_type="CONTEXT_CONFLICT",
                        object_id=UUID(str(conflict["conflict_id"])),
                        reason=str(conflict["reason_code"]),
                        idempotency_key=f"phase1e:context-conflict:{conflict['conflict_id']}",
                    ))
        return stats, tuple(review_ids)


class ContextResolutionService:
    """Synchronous foundation orchestrator; not a Production Compliance Agent."""

    def __init__(self, repository: ContextResolutionRepositoryPort):
        self.repository = repository
        self.business_facts = BusinessFactNormalizationService(repository)
        self.products = ProductContextResolutionService(repository)
        self.scenarios = ScenarioResolutionService(repository)
        self.systems = SystemContextResolutionService(repository)
        self.parties = PartyResolutionService(repository)
        self.data_items = DataItemNormalizationService(repository)
        self.dedup = DataItemDeduplicationService(repository)
        self.groups = DataItemGroupingService(repository)
        self.data_flows = DataFlowResolutionService(repository)
        self.jurisdictions = JurisdictionResolutionService(repository)
        self.validation = ContextValidationService(repository)

    def run(
        self, project_id: UUID, *, selected_product_scope: tuple[UUID, ...] = (),
        detected_product_scope: tuple[UUID, ...] = (),
        selected_scenarios: tuple[UUID, ...] = (), detected_scenarios: tuple[UUID, ...] = (),
        systems: tuple[dict[str, object], ...] = (), devices: tuple[dict[str, object], ...] = (),
        parties: tuple[dict[str, object], ...] = (),
        jurisdictions: tuple[dict[str, object], ...] = (),
        data_item_product_bindings: dict[str, list[str]] | None = None,
        data_item_flow_bindings: dict[str, list[str]] | None = None,
        data_groups: tuple[dict[str, object], ...] = (),
        workflow_run_id: UUID | None = None,
    ) -> dict[str, object]:
        run = self.repository.start_context_run(project_id)
        version = int(run["version"])
        self.business_facts.normalize(project_id, version=version)
        self.products.resolve(
            project_id, selected_scope=selected_product_scope,
            detected_scope=detected_product_scope, version=version,
        )
        self.scenarios.resolve(
            project_id, selected=selected_scenarios, detected=detected_scenarios,
            version=version,
        )
        system_ids = []
        system_ids_by_name: dict[str, UUID] = {}
        for spec in systems:
            system = self.systems.create_system(
                project_id, display_name=str(spec["display_name"]),
                system_type_ref=UUID(str(spec["system_type_ref"])) if spec.get("system_type_ref") else None,
                product_context_refs=tuple(UUID(x) for x in spec.get("product_context_refs", [])),
                party_refs=tuple(UUID(x) for x in spec.get("party_refs", [])),
                location_refs=tuple(UUID(x) for x in spec.get("location_refs", [])),
                source_trace_ids=tuple(UUID(x) for x in spec.get("source_trace_ids", [])),
                confidence=float(spec.get("confidence", 1.0)), version=version,
            )
            system_ids.append(system.system_id)
            system_ids_by_name[_norm_key(system.display_name)] = system.system_id
        for spec in devices:
            device_system_id = (
                UUID(str(spec["system_id"])) if spec.get("system_id")
                else system_ids_by_name.get(_norm_key(spec.get("system_name"))) if spec.get("system_name")
                else None
            )
            self.systems.create_device(
                project_id, display_name=str(spec["display_name"]),
                device_type_ref=UUID(str(spec["device_type_ref"])) if spec.get("device_type_ref") else None,
                system_id=device_system_id,
                product_context_refs=tuple(UUID(x) for x in spec.get("product_context_refs", [])),
                source_trace_ids=tuple(UUID(x) for x in spec.get("source_trace_ids", [])),
                confidence=float(spec.get("confidence", 1.0)), version=version,
            )
        for spec in parties:
            self.parties.resolve(
                project_id, display_name=str(spec["display_name"]),
                role_definition_id=UUID(str(spec["role_definition_id"])) if spec.get("role_definition_id") else None,
                source_trace_ids=tuple(UUID(x) for x in spec.get("source_trace_ids", [])),
                confidence=float(spec.get("confidence", 0.9)), version=version,
            )
        candidate_items = self.repository.list_candidate_items(project_id)
        for left, right in combinations(candidate_items, 2):
            self.dedup.compare(project_id, left, right, version=version)
        candidate_to_formal = self.data_items.normalize(project_id, version=version)

        for group_spec in data_groups:
            formal_ids = tuple(dict.fromkeys(
                item_id for item_id in (
                    candidate_to_formal.get(str(candidate_id))
                    for candidate_id in group_spec.get("candidate_ids", [])
                ) if item_id is not None
            ))
            if formal_ids:
                self.groups.group(
                    project_id, name=str(group_spec["name"]), data_item_ids=formal_ids,
                    grouping_reason=str(group_spec.get("grouping_reason", "LOGICAL_CONTEXT_GROUP")),
                )

        for candidate_id, definition_ids in (data_item_product_bindings or {}).items():
            item_id = candidate_to_formal.get(str(candidate_id)) or self.repository.formal_data_item_by_candidate(UUID(str(candidate_id)))
            if item_id is None:
                continue
            for definition_id_text in definition_ids:
                definition_id = UUID(str(definition_id_text))
                definition = self.repository.metadata_definition(definition_id)
                if definition is None or definition["kind"] not in {"PRODUCT_DOMAIN", "PRODUCT"}:
                    raise ValueError("DataItem product binding must reference Product Registry")
                self.repository.bind_data_item_product(
                    data_item_id=item_id,
                    product_domain_definition_id=definition_id if definition["kind"] == "PRODUCT_DOMAIN" else None,
                    product_definition_id=definition_id if definition["kind"] == "PRODUCT" else None,
                    relationship_type="PRIMARY", confidence=1.0, source_trace_ids=(),
                )

        for spec in jurisdictions:
            self.jurisdictions.resolve(
                project_id,
                jurisdiction_id=UUID(str(spec["jurisdiction_id"])) if spec.get("jurisdiction_id") else None,
                input_value=str(spec.get("input_value", "")),
                context_type=str(spec.get("context_type", "PROCESSING")),
                precision=LocationPrecision(str(spec.get("location_precision", "UNKNOWN"))),
                source=str(spec.get("source", "EXPLICIT_USER_INPUT")),
                confidence=float(spec.get("confidence", 1.0)),
                source_trace_ids=tuple(UUID(x) for x in spec.get("source_trace_ids", [])),
                latitude=float(spec["latitude"]) if spec.get("latitude") is not None else None,
                longitude=float(spec["longitude"]) if spec.get("longitude") is not None else None,
                version=version,
            )

        self.data_flows.resolve(
            project_id, data_item_candidate_bindings=data_item_flow_bindings or {},
            version=version,
        )
        stats, review_ids = self.validation.validate(project_id, workflow_run_id=workflow_run_id)
        confidence = 1.0 if stats["conflict_count"] == 0 else 0.5
        self.repository.finish_context_run(
            UUID(str(run["context_resolution_run_id"])),
            statistics=stats, confidence=confidence,
        )
        return {
            "context_resolution_run_id": run["context_resolution_run_id"],
            "project_id": str(project_id), "version": version,
            "statistics": stats, "review_task_ids": [str(x) for x in review_ids],
            "confidence": confidence,
        }
