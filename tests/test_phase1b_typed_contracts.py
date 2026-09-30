from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from crossborder_compliance.domain.contracts import (
    AnalysisStageResultDTO,
    ChannelContext,
    ChannelType,
    DataFlowEdgeDTO,
    EvidenceReferenceDTO,
    EvidenceValidationStatus,
    ReviewDecisionCode,
    ReviewDecisionDTO,
)


def _prov():
    from crossborder_compliance.domain.contracts import ProvenanceDTO
    return ProvenanceDTO(source_type="test", source_ref="phase1b", generated_by="pytest")


def test_required_frozen_contracts_remain_pydantic_v2_models() -> None:
    ctx = ChannelContext(
        channel_type=ChannelType.WEB,
        tenant_id=uuid4(),
        request_id="phase1b",
        provenance=_prov(),
    )
    assert ctx.model_dump()["request_id"] == "phase1b"

    node_a, node_b = uuid4(), uuid4()
    edge = DataFlowEdgeDTO(
        flow_edge_id=uuid4(),
        project_id=uuid4(),
        source_node_id=node_a,
        target_node_id=node_b,
        flow_type="TRANSFER",
        provenance=_prov(),
    )
    assert edge.source_node_id != edge.target_node_id

    evidence = EvidenceReferenceDTO(
        evidence_id=uuid4(),
        evidence_type="SOURCE_TRACE",
        source_ref="doc:v1:p1",
        validation_status=EvidenceValidationStatus.VALID,
        provenance=_prov(),
    )
    assert evidence.validation_status is EvidenceValidationStatus.VALID

    stage = AnalysisStageResultDTO(
        analysis_run_id=uuid4(),
        stage_code="FOUNDATION",
        stage_name="Foundation",
        sequence=1,
        status="COMPLETED",
        key_findings_count=0,
        warning_count=0,
        review_required=False,
        provenance=_prov(),
    )
    assert stage.sequence == 1

    decision = ReviewDecisionDTO(
        review_id=uuid4(),
        decision=ReviewDecisionCode.APPROVE,
        decided_by="tester",
        decided_at=datetime.now(timezone.utc),
        provenance=_prov(),
    )
    assert decision.decision is ReviewDecisionCode.APPROVE
