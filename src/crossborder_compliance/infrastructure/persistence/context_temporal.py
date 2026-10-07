"""Exact-version queries shared by the existing E/F/H/I adapters.

No current/latest fallback; detail existence is inventory membership.
"""
from sqlalchemy import select

from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence import models as b


def exact_item_detail(session, tenant_id, item_id, version):
    row = session.scalar(select(c.DataItemResolutionDetailEntity).where(
        c.DataItemResolutionDetailEntity.tenant_id == str(tenant_id),
        c.DataItemResolutionDetailEntity.data_item_id == str(item_id),
        c.DataItemResolutionDetailEntity.version == version,
    ))
    if row is None:
        raise LookupError("exact formal data item version unavailable")
    return row


def item_products(session, tenant_id, item_id, version, snapshot_id=None):
    rows = session.execute(select(b.DataItemProductLinkEntity.product_ref, c.DataItemProductLinkDetailEntity.source_trace_ids_json).join(
        c.DataItemProductLinkDetailEntity,
        c.DataItemProductLinkDetailEntity.data_item_product_link_id == b.DataItemProductLinkEntity.data_item_product_link_id,
    ).where(
        b.DataItemProductLinkEntity.tenant_id == str(tenant_id),
        c.DataItemProductLinkDetailEntity.tenant_id == str(tenant_id),
        b.DataItemProductLinkEntity.data_item_id == str(item_id),
        c.DataItemProductLinkDetailEntity.data_inventory_version == version,
    )).all()
    authorized_traces = set(item_trace_ids(session, tenant_id, item_id, version, snapshot_id)) if snapshot_id else set()
    return [product for product, traces in rows if not traces or (snapshot_id and set(traces) <= authorized_traces)]


def flow_item_ids(session, tenant_id, flow_id, inventory_version):
    return session.scalars(select(b.DataItemFlowLinkEntity.data_item_id).join(
        c.DataItemFlowLinkDetailEntity,
        c.DataItemFlowLinkDetailEntity.link_id == b.DataItemFlowLinkEntity.link_id,
    ).where(
        b.DataItemFlowLinkEntity.tenant_id == str(tenant_id),
        c.DataItemFlowLinkDetailEntity.tenant_id == str(tenant_id),
        b.DataItemFlowLinkEntity.flow_edge_id == str(flow_id),
        c.DataItemFlowLinkDetailEntity.data_inventory_version == inventory_version,
    )).all()


def item_trace_ids(session, tenant_id, item_id, version, snapshot_id):
    snapshot = session.scalar(select(b.AnalysisSnapshotEntity).where(
        b.AnalysisSnapshotEntity.tenant_id == str(tenant_id),
        b.AnalysisSnapshotEntity.analysis_snapshot_id == str(snapshot_id),
    ))
    if snapshot is None:
        raise LookupError("snapshot unavailable")
    # Membership AND exact snapshot input universe are both required. Legacy
    # snapshots without recorded input pins fail closed, never use live inputs.
    return session.scalars(select(c.DataItemSourceTraceLinkEntity.source_trace_ref_id).join(
        b.SourceTraceRefEntity,
        b.SourceTraceRefEntity.source_trace_ref_id == c.DataItemSourceTraceLinkEntity.source_trace_ref_id,
    ).join(
        d.SourceTraceDetailEntity,
        d.SourceTraceDetailEntity.source_trace_ref_id == b.SourceTraceRefEntity.source_trace_ref_id,
    ).join(
        d.AnalysisSnapshotParseRunPinEntity,
        (d.AnalysisSnapshotParseRunPinEntity.parse_run_id == d.SourceTraceDetailEntity.parse_run_id)
        & (d.AnalysisSnapshotParseRunPinEntity.document_version_id == b.SourceTraceRefEntity.document_version_id),
    ).where(
        c.DataItemSourceTraceLinkEntity.tenant_id == str(tenant_id),
        b.SourceTraceRefEntity.tenant_id == str(tenant_id),
        d.SourceTraceDetailEntity.tenant_id == str(tenant_id),
        d.AnalysisSnapshotParseRunPinEntity.tenant_id == str(tenant_id),
        c.DataItemSourceTraceLinkEntity.data_item_id == str(item_id),
        c.DataItemSourceTraceLinkEntity.data_inventory_version == version,
        d.AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id == str(snapshot_id),
    )).all()
