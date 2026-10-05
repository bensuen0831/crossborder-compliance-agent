"""Presentation locales never participate in canonical execution or authorization."""

import ast
from dataclasses import fields
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError
from test_phase1l_a_skeleton import Authority, Operations

from crossborder_compliance.application.workflow_skeleton import (
    ExecutionIdentity,
    SemanticStep,
    StageExecutionRequest,
    StageExecutionResult,
    StageOutcomeCode,
    WorkflowExecutionPolicy,
    WorkflowRetryPolicy,
)
from crossborder_compliance.domain.contracts import WorkflowEventType
from crossborder_compliance.workflows.canonical import (
    GRAPH_VERSION,
    CanonicalGraphFactory,
    StateEnvelope,
)
from crossborder_compliance.workflows.events import canonical_event
from crossborder_compliance.workflows.runtime_context import RuntimeContext

LOCALES = ("zh-CN", "zh-HK", "en-US")
STATUSES = {"WAITING", "RUNNING", "COMPLETED", "WARNING", "REVIEW_REQUIRED", "FAILED"}


class ReviewOperations(Operations):
    def __init__(self, review_id):
        super().__init__()
        self.review_id = review_id

    def ensure_review_task(self, **kwargs):
        return self.review_id

    def mark_review_required(self, workflow_run_id):
        self.status_value = "REVIEW_REQUIRED"


@pytest.mark.parametrize("outcome", tuple(StageOutcomeCode))
def test_same_input_all_locales_produces_same_routes_refs_stage_requests_and_event_codes(outcome):
    authority = Authority()
    workflow_id = authority.identity.workflow_run_id
    result_ref, fallback_ref, review_id = uuid4(), uuid4(), uuid4()
    result = StageExecutionResult(
        status=outcome,
        result_ref=result_ref,
        fallback_ref=fallback_ref if outcome == StageOutcomeCode.EVIDENCE_INSUFFICIENT else None,
        reason_codes=("CANONICAL_TEST_REASON",),
    )
    executions = []
    for locale in LOCALES:
        requests = []

        class Stage:
            def __init__(self, recorded_requests):
                self.requests = recorded_requests

            def execute(self, request):
                self.requests.append(request.model_dump(mode="json"))
                return result

        operations = ReviewOperations(review_id)
        factory = CanonicalGraphFactory(
            authorization=authority,
            stages={SemanticStep.REQUIREMENT: Stage(requests)},
            policy=WorkflowExecutionPolicy(
                retry=WorkflowRetryPolicy(max_attempts=2, interval_seconds=0)
            ),
        )
        graph = factory.build(
            InMemorySaver(),
            RuntimeContext(
                operations,
                "same-request",
                GRAPH_VERSION,
                "test",
                "test",
                preferred_locale=locale,
            ),
        )
        graph.invoke(factory.initial_state(workflow_id), factory.config(workflow_id))
        checkpoint = graph.get_state(factory.config(workflow_id))
        state = StateEnvelope.model_validate(checkpoint.values).model_dump(mode="json")
        events = [
            (str(e.event_id), e.event_type.value, e.node_code, e.status, e.payload)
            for e in operations.events
        ]
        assert state["result_refs"] == (
            {}
            if outcome == StageOutcomeCode.RETRYABLE_FAILURE
            else {"requirement": str(result_ref)}
        )
        assert all(e.status in STATUSES for e in operations.events)
        assert all(
            set(e.payload) == {"status", "reason_codes", "request_id"} for e in operations.events
        )
        if outcome in {
            StageOutcomeCode.CONFLICTED,
            StageOutcomeCode.LOW_CONFIDENCE,
            StageOutcomeCode.REVIEW_REQUIRED,
        }:
            assert state["route"] == "REVIEW" and checkpoint.next == ("human_review",)
        elif outcome in {
            StageOutcomeCode.SUCCESS,
            StageOutcomeCode.NOT_APPLICABLE,
            StageOutcomeCode.EVIDENCE_SUFFICIENT,
        }:
            assert state["completed_steps"] == ["requirement"]
            assert state["route"] == "WARNING"  # Next owning service is deliberately absent.
        elif outcome in {
            StageOutcomeCode.FAILED,
            StageOutcomeCode.NON_RETRYABLE_FAILURE,
            StageOutcomeCode.RETRYABLE_FAILURE,
        }:
            assert state["route"] == "FAILED"
        else:
            assert state["route"] == "WARNING"
        executions.append((state, checkpoint.next, requests, events, operations.status_value))
    assert executions[0] == executions[1] == executions[2]


def test_complete_synthetic_pipeline_refs_and_completion_do_not_depend_on_locale():
    authority = Authority()
    workflow_id = authority.identity.workflow_run_id
    refs = {step: uuid4() for step in SemanticStep}
    outputs = []

    class Stage:
        def execute(self, request):
            return StageExecutionResult(status="SUCCESS", result_ref=refs[request.step])

    factory = CanonicalGraphFactory(
        authorization=authority, stages={step: Stage() for step in SemanticStep}
    )
    for locale in LOCALES:
        operations = Operations()
        graph = factory.build(
            InMemorySaver(),
            RuntimeContext(operations, "same-request", GRAPH_VERSION, "test", "test", locale),
        )
        graph.invoke(factory.initial_state(workflow_id), factory.config(workflow_id))
        values = graph.get_state(factory.config(workflow_id)).values
        assert values["route"] == operations.status_value == "COMPLETED"
        assert values["completed_steps"] == [step.value for step in SemanticStep]
        assert values["result_refs"] == {step.value: str(ref) for step, ref in refs.items()}
        outputs.append(values)
    assert outputs[0] == outputs[1] == outputs[2]


def test_presentation_locale_is_excluded_from_semantic_contracts_and_executable_dependencies():
    root = Path(__file__).parents[1] / "src/crossborder_compliance"
    for relative in (
        "application/workflow_skeleton.py",
        "application/workflow_classification.py",
        "workflows/canonical.py",
        "workflows/events.py",
        "workflows/langgraph_adapter.py",
        "infrastructure/persistence/workflow_authorization.py",
    ):
        tree = ast.parse((root / relative).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"locale", "preferred_locale"}, relative
            if isinstance(node, ast.Name):
                assert node.id not in {"locale", "preferred_locale"}, relative
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in {*LOCALES, "locale", "preferred_locale"}, relative
    for model in (StateEnvelope, ExecutionIdentity, StageExecutionRequest, StageExecutionResult):
        assert {"locale", "preferred_locale"}.isdisjoint(model.model_fields)
    assert "preferred_locale" in {f.name for f in fields(RuntimeContext)}
    authority = Authority()
    state = StateEnvelope(identity=authority.identity).model_dump(mode="json")
    with pytest.raises(ValidationError):
        StateEnvelope.model_validate(dict(state, preferred_locale="zh-HK"))
    with pytest.raises(ValidationError):
        ExecutionIdentity.model_validate(dict(state["identity"], preferred_locale="en-US"))


@pytest.mark.parametrize("text", ("等待中", "待人工覆核", "Human Review Required"))
def test_localized_semantics_are_rejected_by_state_stage_result_and_event_boundary(text):
    identity = Authority().identity
    with pytest.raises(ValidationError):
        StateEnvelope(identity=identity, route=text)
    with pytest.raises(ValidationError):
        StateEnvelope(identity=identity, current_step=text)
    with pytest.raises(ValidationError):
        StateEnvelope(identity=identity, reason_codes=(text,))
    with pytest.raises(ValidationError):
        StageExecutionResult(status=text)
    with pytest.raises(ValidationError):
        StageExecutionResult(status="SUCCESS", reason_codes=(text,))
    event = dict(
        event_type=WorkflowEventType.NODE_PROGRESS,
        workflow_run_id=identity.workflow_run_id,
        tenant_id=identity.tenant_id,
        request_id="request",
    )
    with pytest.raises(ValueError):
        canonical_event(**event, status=text)
    with pytest.raises(ValueError):
        canonical_event(**event, status="RUNNING", payload={"status": text})
    with pytest.raises(ValueError):
        canonical_event(**event, status="RUNNING", payload={"reason_codes": [text]})


@pytest.mark.parametrize("status", sorted(STATUSES))
def test_canonical_event_boundary_preserves_each_stable_status(status):
    event = canonical_event(
        event_type=WorkflowEventType.NODE_PROGRESS,
        workflow_run_id=uuid4(),
        tenant_id=uuid4(),
        request_id="request",
        status=status,
        payload={"status": status, "reason_codes": ["STABLE_REASON"]},
    )
    assert event.status == status and event.payload["status"] == status


def test_presentation_locale_is_optional_and_only_supported_codes_are_accepted():
    assert (
        RuntimeContext(Operations(), "request", GRAPH_VERSION, "test", "test").preferred_locale
        is None
    )
    with pytest.raises(ValueError):
        RuntimeContext(Operations(), "request", GRAPH_VERSION, "test", "test", "zh-TW")


def test_canonical_event_rejects_inconsistent_status_and_unstructured_reason_codes():
    arguments = dict(
        event_type=WorkflowEventType.NODE_PROGRESS,
        workflow_run_id=uuid4(),
        tenant_id=uuid4(),
        request_id="request",
        status="RUNNING",
    )
    with pytest.raises(ValueError):
        canonical_event(**arguments, payload={"status": "COMPLETED"})
    with pytest.raises(ValueError):
        canonical_event(**arguments, payload={"reason_codes": "STABLE_REASON"})
