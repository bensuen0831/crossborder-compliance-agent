"""Confirmed user flow input → existing canonical DataFlow persistence owner.

No candidate, legal result or alternate flow store is created here. Source names
are scoped natural references resolved after canonical inventory normalization.
"""
from uuid import UUID, uuid5

from crossborder_compliance.domain.context_resolution import (
    ContextValidationStatus, DataFlowEdgeContext, DataFlowNodeContext,
)


def formalize_user_flows(repo, project_id, context_run_id, version, flows, *, normalize_name):
    # Caller obtained flows from the exact confirmed ProjectVersion/Snapshot
    # through the canonical repository read port, never M2-D correction state.
    inventory = repo.get_data_items(project_id, version=version)
    jurisdictions = repo.get_jurisdiction_context(project_id)
    prepared = []
    # Resolve every reference before creating any flow relation; never choose a
    # similarly named object outside this project's exact inventory version.
    for flow in flows:
        items = [row for row in inventory if normalize_name(row["canonical_name"]) == normalize_name(flow.data_item_canonical_name)]
        if len(items) != 1 or items[0]["validation_status"] != "VALIDATED":
            raise ValueError("INTAKE_FLOW_DATA_ITEM_UNRESOLVED")
        locations = []
        for role, jurisdiction in (("SOURCE", flow.source_jurisdiction_id), ("DESTINATION", flow.destination_jurisdiction_id)):
            matches = [row for row in jurisdictions if row["version"] == version and row["context_type"] == role and row["jurisdiction_id"] == str(jurisdiction) and row["validation_status"] == "VALIDATED"]
            if len(matches) != 1:
                raise ValueError("INTAKE_FLOW_JURISDICTION_UNRESOLVED")
            locations.append(matches[0])
        # Existing read ports validate reference ownership. IDs cannot grant
        # access or point to another tenant/project through a channel payload.
        for party_id in (flow.source_party_id, flow.destination_party_id):
            if party_id is not None and str(party_id) not in {p["project_party_id"] for p in repo.get_parties(project_id)}:
                raise LookupError("INTAKE_FLOW_PARTY_NOT_FOUND")
        for system_id in (flow.source_system_id, flow.destination_system_id):
            if system_id is not None and str(system_id) not in {p["system_id"] for p in repo.get_systems(project_id)}:
                raise LookupError("INTAKE_FLOW_SYSTEM_NOT_FOUND")
        prepared.append((flow, items[0], locations))
    for flow, item, locations in prepared:
        endpoints = []
        for role, location, name, party, system in (
            ("SOURCE", locations[0], flow.source_name, flow.source_party_id, flow.source_system_id),
            ("DESTINATION", locations[1], flow.destination_name, flow.destination_party_id, flow.destination_system_id),
        ):
            identity = uuid5(context_run_id, f"USER_INPUT:{flow.input_key}:{role}")
            detail = DataFlowNodeContext(identity, system, party, UUID(location["jurisdiction_context_id"]), role, (), 1.0, ContextValidationStatus.VALIDATED, version)
            repo.create_formal_flow_node(project_id=project_id, node_type="LOCATION", display_name=name,
                jurisdiction_id=UUID(location["jurisdiction_id"]), detail=detail)
            endpoints.append(identity)
        edge = uuid5(context_run_id, f"USER_INPUT:{flow.input_key}:EDGE")
        detail = DataFlowEdgeContext(edge, None, flow.direction, {}, {}, (), 1.0, ContextValidationStatus.VALIDATED, version)
        repo.create_formal_flow_edge(project_id=project_id, source_node_id=endpoints[0], target_node_id=endpoints[1], flow_type="FLOW", detail=detail)
        repo.link_data_item_flow(data_item_id=UUID(item["data_item_id"]), flow_edge_id=edge,
            relationship_type="CARRIED_ON_FLOW", source_trace_ids=tuple(UUID(x) for x in item["source_trace_ids"]), confidence=1.0)
