"""Read-only scalar projections over the existing workflow persistence.

No new store or decision logic. ORM rows remain within persistence sessions.
"""

from uuid import UUID

from sqlalchemy import select

from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    ProjectEntity,
    ProjectVersionEntity,
    ReviewTaskEntity,
    WorkflowRunEntity,
)


class WorkflowReadProjection:
    def __init__(self, sessions, context):
        self.sessions = sessions
        self.tenant = str(context.tenant_id)

    def require_scope(self, project_id, snapshot_id):
        with self.sessions() as session:
            snapshot = session.get(AnalysisSnapshotEntity, str(snapshot_id))
            version = (
                session.get(ProjectVersionEntity, snapshot.project_version_id) if snapshot else None
            )
            project = session.get(ProjectEntity, str(project_id))
            if (
                not snapshot
                or not version
                or not project
                or version.project_id != str(project_id)
                or any(row.tenant_id != self.tenant for row in (snapshot, version, project))
                or snapshot.status != "ACTIVE"
                or project.status != "ACTIVE"
            ):
                raise LookupError("workflow resource not found")

    def run_scope(self, run_id):
        with self.sessions() as session:
            run = session.get(WorkflowRunEntity, str(run_id))
            snapshot = (
                session.get(AnalysisSnapshotEntity, run.analysis_snapshot_id) if run else None
            )
            version = (
                session.get(ProjectVersionEntity, snapshot.project_version_id) if snapshot else None
            )
            if (
                not run
                or run.tenant_id != self.tenant
                or not version
                or not snapshot
                or version.tenant_id != self.tenant
                or snapshot.tenant_id != self.tenant
            ):
                raise LookupError("workflow resource not found")
            return UUID(version.project_id), UUID(run.analysis_snapshot_id)

    def pending_review(self, run_id):
        with self.sessions() as session:
            return session.scalar(
                select(ReviewTaskEntity.review_id)
                .where(
                    ReviewTaskEntity.workflow_run_id == str(run_id),
                    ReviewTaskEntity.tenant_id == self.tenant,
                    ReviewTaskEntity.review_type == "WORKFLOW_STAGE_REVIEW",
                    ReviewTaskEntity.status == "PENDING",
                )
                .order_by(ReviewTaskEntity.created_at.desc())
            )

    def context(self, project_id, snapshot_id, context_run_id):
        from crossborder_compliance.application.stage1_result import (
            DataItemSummary,
            DocumentSummary,
            FlowNodeSummary,
            FlowSummary,
            ProjectSummary,
            Stage1ContextProjection,
        )
        from crossborder_compliance.infrastructure.persistence import context_models as c
        from crossborder_compliance.infrastructure.persistence import document_models as d
        from crossborder_compliance.infrastructure.persistence import models as b
        from crossborder_compliance.infrastructure.persistence.context_temporal import (
            flow_item_ids,
            item_trace_ids,
        )

        self.require_scope(project_id, snapshot_id)
        with self.sessions() as session:
            snapshot = session.get(b.AnalysisSnapshotEntity, str(snapshot_id))
            version = session.get(b.ProjectVersionEntity, snapshot.project_version_id)
            project = session.get(b.ProjectEntity, str(project_id))
            pin = session.scalar(
                select(c.AnalysisSnapshotContextPinEntity).where(
                    c.AnalysisSnapshotContextPinEntity.tenant_id == self.tenant,
                    c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == str(snapshot_id),
                    c.AnalysisSnapshotContextPinEntity.project_id == str(project_id),
                    c.AnalysisSnapshotContextPinEntity.context_resolution_run_id
                    == str(context_run_id),
                )
            )
            run = session.get(c.ContextResolutionRunEntity, str(context_run_id))
            if (
                pin is None
                or run is None
                or (run.tenant_id, run.project_id, run.version)
                != (self.tenant, str(project_id), pin.context_resolution_version)
            ):
                raise LookupError("exact snapshot context unavailable")
            documents = session.execute(
                select(b.DocumentEntity, b.DocumentVersionEntity, b.DocumentParseRunEntity)
                .join(
                    b.DocumentVersionEntity,
                    b.DocumentVersionEntity.document_id == b.DocumentEntity.document_id,
                )
                .join(
                    d.AnalysisSnapshotParseRunPinEntity,
                    d.AnalysisSnapshotParseRunPinEntity.document_version_id
                    == b.DocumentVersionEntity.document_version_id,
                )
                .join(
                    b.DocumentParseRunEntity,
                    b.DocumentParseRunEntity.document_parse_run_id
                    == d.AnalysisSnapshotParseRunPinEntity.parse_run_id,
                )
                .where(
                    b.DocumentEntity.tenant_id == self.tenant,
                    b.DocumentEntity.project_id == str(project_id),
                    b.DocumentVersionEntity.tenant_id == self.tenant,
                    b.DocumentParseRunEntity.tenant_id == self.tenant,
                    b.DocumentParseRunEntity.document_version_id
                    == b.DocumentVersionEntity.document_version_id,
                    d.AnalysisSnapshotParseRunPinEntity.tenant_id == self.tenant,
                    d.AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id == str(snapshot_id),
                )
                .order_by(b.DocumentEntity.document_id)
            ).all()
            items = session.execute(
                select(b.DataItemEntity, c.DataItemResolutionDetailEntity)
                .join(
                    c.DataItemResolutionDetailEntity,
                    c.DataItemResolutionDetailEntity.data_item_id == b.DataItemEntity.data_item_id,
                )
                .where(
                    b.DataItemEntity.tenant_id == self.tenant,
                    b.DataItemEntity.project_id == str(project_id),
                    c.DataItemResolutionDetailEntity.tenant_id == self.tenant,
                    c.DataItemResolutionDetailEntity.version == pin.data_inventory_version,
                )
                .order_by(b.DataItemEntity.data_item_id)
            ).all()
            nodes = session.scalars(
                select(b.DataFlowNodeEntity)
                .join(
                    c.DataFlowNodeDetailEntity,
                    c.DataFlowNodeDetailEntity.flow_node_id == b.DataFlowNodeEntity.flow_node_id,
                )
                .where(
                    b.DataFlowNodeEntity.tenant_id == self.tenant,
                    b.DataFlowNodeEntity.project_id == str(project_id),
                    c.DataFlowNodeDetailEntity.tenant_id == self.tenant,
                    c.DataFlowNodeDetailEntity.version == pin.data_flow_version,
                )
                .order_by(b.DataFlowNodeEntity.flow_node_id)
            ).all()
            edges = session.execute(
                select(b.DataFlowEdgeEntity, c.DataFlowEdgeDetailEntity)
                .join(
                    c.DataFlowEdgeDetailEntity,
                    c.DataFlowEdgeDetailEntity.flow_edge_id == b.DataFlowEdgeEntity.flow_edge_id,
                )
                .where(
                    b.DataFlowEdgeEntity.tenant_id == self.tenant,
                    b.DataFlowEdgeEntity.project_id == str(project_id),
                    c.DataFlowEdgeDetailEntity.tenant_id == self.tenant,
                    c.DataFlowEdgeDetailEntity.version == pin.data_flow_version,
                )
                .order_by(b.DataFlowEdgeEntity.flow_edge_id)
            ).all()
            node_ids = {n.flow_node_id for n in nodes}
            if any(
                e.source_node_id not in node_ids or e.target_node_id not in node_ids
                for e, _ in edges
            ):
                raise LookupError("exact flow endpoints unavailable")
            return Stage1ContextProjection(
                project=ProjectSummary(
                    project_id=project_id,
                    project_version_id=version.project_version_id,
                    name=version.intake_json.get("project_name", project.name),
                    analysis_as_of_date=snapshot.analysis_as_of_date,
                    context_resolution_run_id=context_run_id,
                    data_inventory_version=pin.data_inventory_version,
                    formal_context_version=pin.context_resolution_version,
                ),
                documents=tuple(
                    DocumentSummary(
                        document_id=doc.document_id,
                        document_version_id=v.document_version_id,
                        parse_run_id=p.document_parse_run_id,
                        name=doc.name,
                        version=v.version_no,
                        parse_status=p.status,
                        parser_version=p.parser_version,
                    )
                    for doc, v, p in documents
                ),
                data_items=tuple(
                    DataItemSummary(
                        data_item_id=i.data_item_id,
                        name=detail.display_name,
                        validation_status=detail.validation_status,
                        review_required=detail.review_required,
                        source_trace_ids=item_trace_ids(
                            session,
                            self.tenant,
                            i.data_item_id,
                            pin.data_inventory_version,
                            snapshot_id,
                        ),
                    )
                    for i, detail in items
                ),
                flow_nodes=tuple(
                    FlowNodeSummary(
                        flow_node_id=n.flow_node_id,
                        name=n.display_name,
                        jurisdiction_id=n.jurisdiction_id,
                    )
                    for n in nodes
                ),
                flows=tuple(
                    FlowSummary(
                        flow_edge_id=e.flow_edge_id,
                        source_node_id=e.source_node_id,
                        target_node_id=e.target_node_id,
                        data_item_ids=flow_item_ids(
                            session, self.tenant, e.flow_edge_id, pin.data_inventory_version
                        ),
                        validation_status=detail.validation_status,
                    )
                    for e, detail in edges
                ),
            )

    def legal_basis(self, ids):
        from crossborder_compliance.application.stage1_result import OfficialLegalBasis
        from crossborder_compliance.infrastructure.persistence.models import LegalBasisItemEntity

        with self.sessions() as session:
            rows = session.scalars(
                select(LegalBasisItemEntity).where(
                    LegalBasisItemEntity.tenant_id == self.tenant,
                    LegalBasisItemEntity.legal_basis_id.in_([str(i) for i in ids]),
                )
            ).all()
            if {r.legal_basis_id for r in rows} != {str(i) for i in ids}:
                raise LookupError("official legal basis unavailable")
            return tuple(
                OfficialLegalBasis(
                    legal_basis_id=r.legal_basis_id,
                    jurisdiction_id=r.jurisdiction_id,
                    summary=r.legal_basis_summary,
                    official_source=r.official_source,
                    citation_locator=r.citation_locator,
                )
                for r in sorted(rows, key=lambda r: r.legal_basis_id)
            )
