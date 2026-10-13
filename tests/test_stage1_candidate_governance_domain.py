"""Public owner boundaries reject high-confidence proposals without consent."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from crossborder_compliance.application.candidate_governance_services import (
    CandidateDecisionInput,
    ResolveDocumentCandidates,
)
from crossborder_compliance.application.context_services import (
    BusinessFactNormalizationService,
    DataFlowResolutionService,
    DataItemNormalizationService,
)
from crossborder_compliance.application.llm_invocation_services import GovernedLLMInvocationService
from crossborder_compliance.domain.llm_gateway import (
    DraftPreparationInvocationScope,
    GatewayDenied,
    LLMRequest,
)
from crossborder_compliance.domain.llm_invocation import InvocationFacts


def draft_request(**overrides):
    project, version, preparation = uuid4(), uuid4(), uuid4()
    value = {
        "project_id": project,
        "invocation_scope": DraftPreparationInvocationScope(
            candidate_preparation_id=preparation, project_id=project, project_version_id=version
        ),
        "operation": "structured_output",
        "input_refs": [
            {"resource_type": "DOCUMENT_PARSE_RUN", "resource_id": uuid4(), "version_id": uuid4()}
        ],
        "output_schema": {"type": "object"},
    }
    return LLMRequest(**{**value, **overrides})


def test_draft_scope_has_genuine_distinct_identity_and_no_snapshot():
    request = draft_request()
    assert request.analysis_snapshot_id is None
    assert (
        request.invocation_scope.candidate_preparation_id
        != request.invocation_scope.project_version_id
    )
    with pytest.raises(ValidationError, match="DRAFT_INVOCATION_SCOPE_INVALID"):
        draft_request(analysis_snapshot_id=uuid4())
    with pytest.raises(ValidationError, match="DRAFT_INVOCATION_SCOPE_INVALID"):
        draft_request(operation="chat")
    with pytest.raises(ValidationError):
        DraftPreparationInvocationScope(
            candidate_preparation_id=uuid4(),
            project_id=uuid4(),
            project_version_id=uuid4(),
            purpose="QUERY_EXPANSION",
        )


@pytest.mark.parametrize(
    "purpose,trigger",
    [
        ("QUERY_EXPANSION", "KNOWLEDGE_EVIDENCE_INSUFFICIENT"),
        ("DERIVED_EXPLANATION", "RESULT_EXPLANATION_REQUESTED"),
    ],
)
def test_draft_cannot_route_other_purposes_to_gateway(purpose, trigger):
    class Poison:
        def load(self, *args):
            pytest.fail("draft invalid purpose reached configuration")

    with pytest.raises(GatewayDenied, match="DRAFT_INVOCATION_PURPOSE_DENIED"):
        GovernedLLMInvocationService(Poison(), Poison()).invoke(
            draft_request(), InvocationFacts(purpose=purpose, trigger=trigger)
        )


@pytest.mark.parametrize("owner", ["FACT", "ITEM", "FLOW"])
def test_confidence_one_is_not_authorization_for_any_formal_owner(owner):
    candidate = {
        "candidate_id": str(uuid4()),
        "candidate_origin": "LLM_STRUCTURED_OUTPUT",
        "confidence": 1,
        "fact_type": "GOVERNED",
        "normalized_value": "proposed",
        "normalized_name": "proposed",
        "source_trace_ids": [str(uuid4())],
    }

    class Repo:
        def list_candidate_facts(self, *args):
            return [candidate]

        def list_candidate_items(self, *args):
            return [candidate]

        def list_candidate_flow_nodes(self, *args):
            return [candidate]

        def list_candidate_flow_edges(self, *args):
            return []

        def save_business_fact(self, *args):
            pytest.fail("unconfirmed formal fact created")

        def create_formal_data_item(self, **kwargs):
            pytest.fail("unconfirmed formal item created")

    service = {
        "FACT": BusinessFactNormalizationService,
        "ITEM": DataItemNormalizationService,
        "FLOW": DataFlowResolutionService,
    }[owner](Repo())
    with pytest.raises(ValueError, match="CANDIDATE_CONFIRMATION_REQUIRED"):
        service.normalize(uuid4(), version=1) if owner != "FLOW" else service.resolve(
            uuid4(), data_item_candidate_bindings={}, version=1
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "POLICY"},
        {"action": "EDIT"},
        {"action": "REJECT", "edited_payload": {"normalized_value": "value"}},
        {"action": "ACCEPT", "actor_id": "spoof"},
    ],
)
def test_decision_contract_has_no_policy_action_or_actor_authority(payload):
    with pytest.raises(ValidationError):
        CandidateDecisionInput(preparation_candidate_id=uuid4(), **payload)


def test_decision_universe_rejects_duplicate_members():
    identity = uuid4()
    with pytest.raises(ValidationError, match="INVALID_CANDIDATE_DECISION"):
        ResolveDocumentCandidates(
            expected_version=1,
            idempotency_key="unique",
            candidate_preparation_id=uuid4(),
            candidate_universe_digest="a" * 64,
            decisions=[
                {"preparation_candidate_id": identity, "action": "ACCEPT"},
                {"preparation_candidate_id": identity, "action": "REJECT"},
            ],
        )
