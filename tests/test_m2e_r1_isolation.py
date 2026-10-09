"""Owning application scoping, independent from the external channel."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from phase1i_fixtures import prepared
from phase1j_fixtures import decision_fixture
from pydantic import ValidationError
from test_phase1l_a_skeleton import Authority
from test_phase1l_b_contracts import plan_for

from crossborder_compliance.application.workflow_formal import (
    FormalWorkflowPlan,
    FormalWorkflowStages,
)
from crossborder_compliance.application.workflow_skeleton import SemanticStep, StageExecutionRequest
from crossborder_compliance.domain.regulation_applicability import ApplicabilityInput
from crossborder_compliance.domain.rules import RuleHit


def test_legacy_rule_hit_serialization_preserves_historical_digest_input():
    original = prepared().rule_hits[0].model_dump(mode="json")
    original.pop("jurisdiction_id", None)
    historical = RuleHit.model_validate(original)
    assert historical.model_dump(mode="json") == original
    explicit = historical.model_copy(update={"jurisdiction_id": uuid4()})
    assert explicit.model_dump(mode="json")["jurisdiction_id"] == str(explicit.jurisdiction_id)


def test_applicability_rejects_cross_jurisdiction_rule_hit():
    inputs = prepared()
    data = inputs.model_dump()
    data["rule_hits"] = (inputs.rule_hits[0].model_copy(update={"jurisdiction_id": uuid4()}),)
    with pytest.raises(ValidationError, match="wrong RuleHit jurisdiction"):
        ApplicabilityInput.model_validate(data)
    data["rule_hits"] = (
        inputs.rule_hits[0].model_copy(update={"jurisdiction_id": inputs.jurisdiction_id}),
    )
    assert ApplicabilityInput.model_validate(data).jurisdiction_id == inputs.jurisdiction_id


def test_formal_stages_execute_and_scope_each_explicit_jurisdiction():
    authority = Authority()
    old = plan_for(decision_fixture(), authority)
    a, b = old.applicability[0].jurisdiction_id, uuid4()
    scheme = old.scheme_version_id
    data = old.model_dump()
    data.update(
        scheme_version_id=None,
        classification_bindings=tuple(
            dict(jurisdiction_id=j, scheme_version_id=scheme, classification_binding_id=uuid4())
            for j in (a, b)
        ),
        applicability=tuple(dict(jurisdiction_id=j, config_id=uuid4()) for j in (a, b)),
    )
    plan = FormalWorkflowPlan.model_validate(data)
    results, calls, requests = {}, [], []

    class Classification:
        def execute(self, **kwargs):
            calls.append(kwargs)
            result = SimpleNamespace(
                classification_result_id=uuid4(),
                jurisdiction_id=kwargs["jurisdiction_id"],
                rule_hit_ids=(uuid4(),),
            )
            results[result.classification_result_id] = result
            return SimpleNamespace(result=result, status="COMPLETED", reason_codes=())

    class Country:
        def classify(self, ident):
            return results[ident]

        def resolve_regulation_applicability(self, request):
            requests.append(request)
            return SimpleNamespace(
                applicability_result_id=uuid4(), applicability_status="APPLICABLE", reason_codes=()
            )

    stages = FormalWorkflowStages(
        plan,
        contexts=None,
        knowledge_scope=None,
        retrieval=None,
        evidence=None,
        classification=Classification(),
        country=Country(),
        decisions=None,
    )
    refs = {
        s: uuid4()
        for s in list(SemanticStep)[: list(SemanticStep).index(SemanticStep.CLASSIFICATION)]
    }
    for step in list(SemanticStep)[:4]:
        refs[step] = plan.context_resolution_run_id
    refs[SemanticStep.KNOWLEDGE_SCOPE] = plan.analysis_snapshot_id
    request = StageExecutionRequest(
        identity=authority.identity,
        step=SemanticStep.CLASSIFICATION,
        result_refs=refs,
        idempotency_key="owning-classification",
        timeout_seconds=30,
    )
    classified = stages.execute(request)
    assert classified.status == "SUCCESS"
    assert len(classified.related_result_refs) == 2
    assert {(c["data_item_id"], c["jurisdiction_id"], c["scheme_version_id"]) for c in calls} == {
        (plan.subject_id, a, scheme),
        (plan.subject_id, b, scheme),
    }
    refs[SemanticStep.CLASSIFICATION] = classified.result_ref
    stages.execute(
        request.model_copy(
            update={
                "step": SemanticStep.APPLICABILITY,
                "result_refs": refs,
                "result_ref_sets": {SemanticStep.CLASSIFICATION: classified.related_result_refs},
            }
        )
    )
    assert len(requests) == 2
    for value in requests:
        assert len(value.classification_result_ids) == 1
        result = results[value.classification_result_ids[0]]
        assert result.jurisdiction_id == value.jurisdiction_id
        assert value.rule_hit_ids == result.rule_hit_ids
