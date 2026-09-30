from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError
from crossborder_compliance.domain.contracts import (
    ChannelContext, ChannelType, ClassificationResultDTO, ComplianceAnalysisRequest, LegalBasisItemDTO,
    ProvenanceDTO, Stage1ComplianceResultDTO, EvidenceValidationStatus,
)
def prov(): return ProvenanceDTO(source_type="test",source_ref="fixture",generated_by="pytest")
def test_channel_and_request_typed_contract():
    ctx=ChannelContext(channel_type=ChannelType.WEB,tenant_id=uuid4(),request_id="r1",provenance=prov())
    req=ComplianceAnalysisRequest(project_id=uuid4(),requested_outputs=["stage1"],analysis_as_of_date=date.today(),idempotency_key="k1",channel_context=ctx,provenance=prov())
    assert req.channel_context.channel_type is ChannelType.WEB
def test_classification_confidence_validation():
    with pytest.raises(ValidationError):
        ClassificationResultDTO(classification_result_id=uuid4(),subject_type="DATA_ITEM",subject_id=uuid4(),scheme_id=uuid4(),scheme_version_id=uuid4(),
            category_ids=[],jurisdiction_id=uuid4(),confidence=1.5,evidence_ids=[],review_required=True,provenance=prov())
def test_legal_basis_uses_rule_hit_ids_list():
    item=LegalBasisItemDTO(legal_basis_id=uuid4(),jurisdiction_id=uuid4(),regulation_id=uuid4(),regulation_name="R",regulation_version_id=uuid4(),
        article_or_section="Section 1",rule_hit_ids=[uuid4(),uuid4()],legal_basis_summary="summary",applicability_reason="reason",official_source="official",
        effective_date=date.today(),evidence_ids=[uuid4()],citation_locator="s1",confidence=.9,validation_status=EvidenceValidationStatus.VALID,provenance=prov())
    assert len(item.rule_hit_ids)==2
def test_stage1_requires_explicit_cross_border_results_field():
    assert "cross_border_results" in Stage1ComplianceResultDTO.model_fields
