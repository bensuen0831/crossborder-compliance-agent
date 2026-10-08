"""One canonical graph, injected into the existing runtime; references only."""

import time
from typing import TypedDict
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.application.workflow_skeleton import (
    ExecutionIdentity,
    ReferenceModel,
    SemanticStep,
    StageBusinessFailure,
    StageExecutionRequest,
    StageExecutionResult,
    StageOutcomeCode,
    StageTransientFailure,
    UnavailableStage,
    WorkflowExecutionPolicy,
)
from crossborder_compliance.domain.contracts import WorkflowEventType
from crossborder_compliance.workflows.events import canonical_event

LEGACY_GRAPH_VERSION = "phase1l-a-canonical-v1"
LEGACY_STATE_VERSION = "phase1l-a-references-v1"
GRAPH_VERSION = "phase1l-a-canonical-v2"
STATE_VERSION = "phase1l-a-references-v2"
PIPELINE = tuple(SemanticStep)


class ComplianceWorkflowState(TypedDict):
    identity: dict
    current_step: str
    result_refs: dict[str, str]
    result_ref_sets: dict[str, list[str]]
    completed_steps: list[str]
    fallback_ref: str | None
    review_ref: str | None
    route: str
    reason_codes: list[str]
    step_count: int
    visits: dict[str, int]


class StateEnvelope(ReferenceModel):
    identity: ExecutionIdentity
    current_step: SemanticStep = SemanticStep.REQUIREMENT
    result_refs: dict[SemanticStep, UUID] = Field(default_factory=dict, max_length=17)
    result_ref_sets: dict[SemanticStep, tuple[UUID, ...]] = Field(
        default_factory=dict, max_length=17
    )
    completed_steps: tuple[SemanticStep, ...] = Field(default=(), max_length=17)
    fallback_ref: UUID | None = None
    review_ref: UUID | None = None
    route: str = Field(default="NEXT", pattern=r"^(NEXT|REVIEW|WARNING|FAILED|COMPLETED)$")
    reason_codes: tuple[str, ...] = Field(default=(), max_length=16)
    step_count: int = Field(default=0, ge=0, le=200)
    visits: dict[SemanticStep, int] = Field(default_factory=dict, max_length=17)

    @model_validator(mode="after")
    def bounded_codes_and_routes(self):
        import re

        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) for code in self.reason_codes):
            raise ValueError("structured reason codes only")
        if any(value < 0 or value > 200 for value in self.visits.values()):
            raise ValueError("bounded visits required")
        if len(set(self.completed_steps)) != len(self.completed_steps):
            raise ValueError("completed steps must be unique")
        for step, refs in self.result_ref_sets.items():
            if not refs or len(refs) > 128 or len(set(refs)) != len(refs):
                raise ValueError("bounded unique result references required")
            if self.result_refs.get(step) != refs[0]:
                raise ValueError("primary and related result references must agree")
        return self


class CanonicalGraphFactory:
    def __init__(self, *, authorization, stages=None, policy=None, emit_result_refs=False, review_governance=None):
        self.authorization = authorization
        self.review_governance = review_governance
        self.stages = dict(stages or {})
        if not all(isinstance(k, SemanticStep) for k in self.stages):
            raise ValueError("stage bindings require semantic step keys")
        self.policy = policy or WorkflowExecutionPolicy()
        self.emit_result_refs = emit_result_refs

    def authorize(self, workflow_run_id, operation):
        identity = self.authorization.authorize(workflow_run_id, operation)
        if identity.workflow_run_id != workflow_run_id:
            raise PermissionError("workflow not found")
        if (identity.graph_definition_version, identity.state_schema_version) not in {
            (GRAPH_VERSION, STATE_VERSION),
            (LEGACY_GRAPH_VERSION, LEGACY_STATE_VERSION),
        }:
            raise ValueError("WORKFLOW_VERSION_MISMATCH")
        return identity

    def initial_state(self, workflow_run_id):
        return StateEnvelope(identity=self.authorize(workflow_run_id, "execute")).model_dump(
            mode="json"
        )

    def validate(self, workflow_run_id, state, operation="execute"):
        fresh = self.authorize(workflow_run_id, operation)
        parsed = StateEnvelope.model_validate(state)
        if parsed.identity != fresh:
            raise PermissionError("checkpoint cannot authorize or replace execution identity")
        return parsed

    def authorize_resume(self, workflow_run_id, decision):
        self.authorize(workflow_run_id, "review")
        value = self.authorization.authorize_review(workflow_run_id, decision)
        if self.review_governance is not None:
            value = self.review_governance.authorize_resume(workflow_run_id, value)
        return value

    def config(self, workflow_run_id):
        return {
            "configurable": {"thread_id": str(workflow_run_id)},
            "recursion_limit": self.policy.recursion_limit,
        }

    def build(self, checkpointer, context):
        # The existing adapter remains the single raw runtime import boundary.
        from crossborder_compliance.workflows.langgraph_adapter import _require_langgraph

        END, START, StateGraph, Command, interrupt, _PostgresSaver = _require_langgraph()

        ops = context.operations

        def event(state, kind, status, suffix):
            ident = state.identity
            ops.record_event(
                ident.tenant_id,
                canonical_event(
                    event_type=kind,
                    workflow_run_id=ident.workflow_run_id,
                    tenant_id=ident.tenant_id,
                    request_id=context.request_id,
                    node_code=state.current_step.value,
                    status=status,
                    payload={
                        "reason_codes": list(state.reason_codes),
                        "status": status,
                        "request_id": context.request_id,
                        **(
                            {
                                "result_refs": {
                                    k.value: [str(v) for v in state.result_ref_sets.get(k, (ref,))]
                                    for k, ref in state.result_refs.items()
                                }
                            }
                            if self.emit_result_refs
                            else {}
                        ),
                    },
                    event_key=f"canonical:{state.current_step}:{state.step_count}:{suffix}",
                ),
            )

        def node(step):
            def execute(raw):
                wf = UUID(raw["identity"]["workflow_run_id"])
                state = self.validate(wf, raw)
                visits = dict(state.visits)
                visits[step] = visits.get(step, 0) + 1
                if (
                    state.step_count >= self.policy.max_steps
                    or visits[step] > self.policy.max_visits_per_step
                ):
                    return {
                        "route": "FAILED",
                        "reason_codes": ["WORKFLOW_STEP_GUARD"],
                        "current_step": step.value,
                    }
                current = state.model_copy(
                    update={"current_step": step, "step_count": state.step_count + 1}
                )
                event(current, WorkflowEventType.NODE_PROGRESS, "WAITING", "waiting")
                event(current, WorkflowEventType.NODE_STARTED, "RUNNING", "started")
                request = StageExecutionRequest(
                    identity=state.identity,
                    step=step,
                    result_refs=state.result_refs,
                    result_ref_sets=state.result_ref_sets,
                    fallback_ref=state.fallback_ref,
                    review_ref=state.review_ref,
                    idempotency_key=f"stage:{wf}:{step}:{state.review_ref or 'initial'}",
                    timeout_seconds=self.policy.timeout.stage_seconds,
                )
                service = self.stages.get(step, UnavailableStage())
                result = None
                for attempt in range(self.policy.retry.max_attempts):
                    # Dependencies live outside checkpoint state. Every retry reauthorizes.
                    self.validate(wf, raw)
                    started = time.monotonic()
                    try:
                        result = StageExecutionResult.model_validate(service.execute(request))
                        self.validate(wf, raw)
                        if time.monotonic() - started > request.timeout_seconds:
                            raise StageTransientFailure()
                        if result.status == StageOutcomeCode.RETRYABLE_FAILURE:
                            raise StageTransientFailure()
                        break
                    except StageTransientFailure:
                        if attempt + 1 == self.policy.retry.max_attempts:
                            result = StageExecutionResult(
                                status=StageOutcomeCode.FAILED,
                                reason_codes=("STAGE_RETRY_EXHAUSTED",),
                            )
                        else:
                            time.sleep(
                                self.policy.retry.interval_seconds
                                * self.policy.retry.backoff_factor**attempt
                            )
                    except StageBusinessFailure:
                        result = StageExecutionResult(
                            status=StageOutcomeCode.NON_RETRYABLE_FAILURE,
                            reason_codes=("STAGE_BUSINESS_FAILURE",),
                        )
                        break
                    except PermissionError:
                        raise
                    except Exception:
                        result = StageExecutionResult(
                            status=StageOutcomeCode.FAILED, reason_codes=("STAGE_EXECUTION_FAILED",)
                        )
                        break
                assert result is not None
                refs = dict(state.result_refs)
                ref_sets = dict(state.result_ref_sets)
                if result.result_ref:
                    refs[step] = result.result_ref
                    if result.related_result_refs:
                        ref_sets[step] = result.related_result_refs
                status = result.status
                if status in {
                    StageOutcomeCode.SUCCESS,
                    StageOutcomeCode.NOT_APPLICABLE,
                    StageOutcomeCode.EVIDENCE_SUFFICIENT,
                }:
                    route = "NEXT"
                elif status in {
                    StageOutcomeCode.CONFLICTED,
                    StageOutcomeCode.REVIEW_REQUIRED,
                    StageOutcomeCode.LOW_CONFIDENCE,
                }:
                    route = "REVIEW"
                elif status in {StageOutcomeCode.FAILED, StageOutcomeCode.NON_RETRYABLE_FAILURE}:
                    route = "FAILED"
                else:
                    route = "WARNING"
                completed = list(state.completed_steps)
                if route == "NEXT" and step not in completed:
                    completed.append(step)
                current = current.model_copy(
                    update={
                        "reason_codes": result.reason_codes,
                        "result_refs": refs,
                        "result_ref_sets": ref_sets,
                    }
                )
                event(
                    current,
                    WorkflowEventType.NODE_COMPLETED,
                    "COMPLETED"
                    if route == "NEXT"
                    else "REVIEW_REQUIRED"
                    if route == "REVIEW"
                    else route,
                    "result",
                )
                return {
                    "current_step": step.value,
                    "result_refs": {k.value: str(v) for k, v in refs.items()},
                    "result_ref_sets": {
                        k.value: [str(v) for v in values] for k, values in ref_sets.items()
                    },
                    "completed_steps": [s.value for s in completed],
                    "fallback_ref": str(result.fallback_ref)
                    if result.fallback_ref
                    else raw["fallback_ref"],
                    "route": route,
                    "reason_codes": list(result.reason_codes),
                    "step_count": current.step_count,
                    "visits": {k.value: v for k, v in visits.items()},
                }

            return execute

        def human_review(raw):
            wf = UUID(raw["identity"]["workflow_run_id"])
            state = self.validate(wf, raw)
            key = f"canonical-review:{wf}:{state.current_step}:{state.visits[state.current_step]}"
            review_id = ops.ensure_review_task(
                workflow_run_id=wf,
                tenant_id=state.identity.tenant_id,
                idempotency_key=key,
                review_type="WORKFLOW_STAGE_REVIEW",
                reason="CANONICAL_STAGE_REQUIRES_REVIEW",
            )
            if self.review_governance is not None:
                self.review_governance.describe(review_id, state.current_step, state.reason_codes, state.result_refs)
            ops.mark_review_required(wf)
            event(state, WorkflowEventType.REVIEW_REQUIRED, "REVIEW_REQUIRED", "review")
            decision = interrupt({"review_id": str(review_id), "step": state.current_step.value})
            decision = self.authorize_resume(wf, decision)
            if str(decision["review_id"]) != str(review_id):
                raise PermissionError("review not found")
            ops.resolve_review(review_id, decision)
            if decision["decision"] not in {"APPROVE", "APPROVED"}:
                return Command(
                    update={
                        "route": "FAILED",
                        "review_ref": str(review_id),
                        "reason_codes": ["REVIEW_REJECTED"],
                    },
                    goto="finish",
                )
            ops.mark_resumed(wf)
            event(state, WorkflowEventType.WORKFLOW_RESUMED, "RUNNING", "resumed")
            # Approval never manufactures a legal result: owning stage must execute again.
            return Command(
                update={"review_ref": str(review_id), "route": "NEXT"},
                goto=state.current_step.value,
            )

        def finish(raw):
            wf = UUID(raw["identity"]["workflow_run_id"])
            state = self.validate(wf, raw)
            status = state.route if state.route in {"WARNING", "FAILED"} else "COMPLETED"
            if status == "COMPLETED":
                ops.mark_completed(
                    wf, state.identity.tenant_id, state.identity.analysis_snapshot_id
                )
            else:
                ops.set_status(wf, status)
            event(
                state,
                WorkflowEventType.WORKFLOW_FAILED
                if status == "FAILED"
                else WorkflowEventType.NODE_PROGRESS
                if status == "WARNING"
                else WorkflowEventType.WORKFLOW_COMPLETED,
                status,
                "terminal",
            )
            return {"route": status}

        graph = StateGraph(ComplianceWorkflowState)
        for step in PIPELINE:
            graph.add_node(step.value, node(step))
        graph.add_node("human_review", human_review)
        graph.add_node("finish", finish)
        graph.add_edge(START, PIPELINE[0].value)
        for index, step in enumerate(PIPELINE):
            next_step = PIPELINE[index + 1].value if index + 1 < len(PIPELINE) else "finish"

            def route(state, current=step):
                if (
                    current == SemanticStep.OBLIGATION
                    and state["route"] == "NEXT"
                    and state["identity"]["graph_definition_version"] == LEGACY_GRAPH_VERSION
                ):
                    return "LEGACY_NEXT"
                return state["route"]

            graph.add_conditional_edges(
                step.value,
                route,
                {
                    "NEXT": next_step,
                    **(
                        {"LEGACY_NEXT": SemanticStep.CANDIDATE_PATH.value}
                        if step == SemanticStep.OBLIGATION
                        else {}
                    ),
                    "REVIEW": "human_review",
                    "WARNING": "finish",
                    "FAILED": "finish",
                },
            )
        graph.add_edge("finish", END)
        return graph.compile(checkpointer=checkpointer)
