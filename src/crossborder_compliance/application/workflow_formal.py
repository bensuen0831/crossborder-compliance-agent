"""In-process owning-service bindings for the single canonical workflow.

This is orchestration, not a legal evaluator or another result authority.
The trusted application reconstructs the same reference plan on restart.
"""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.application.country_compliance_services import ApplicabilityRequest
from crossborder_compliance.application.decision_services import (
    PARENTS,
    DecisionRequest,
    UpstreamIdentifier,
)
from crossborder_compliance.application.formal_result_services import FormalAuthorityRequest
from crossborder_compliance.application.workflow_skeleton import (
    ReferenceModel,
    SemanticStep,
    StageExecutionResult,
    StageOutcomeCode,
)
from crossborder_compliance.domain.classification import ClassificationJurisdictionBinding
from crossborder_compliance.domain.retrieval import KnowledgeRetrievalQuery, RAGContextPack


class ApplicabilityBinding(ReferenceModel):
    jurisdiction_id: UUID
    config_id: UUID


class FormalWorkflowPlan(ReferenceModel):
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    request_context_ref: UUID
    context_resolution_run_id: UUID
    mode: Literal["DATA_AWARE", "SCENARIO_LEVEL"]
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    classification_data_item_ids: tuple[UUID, ...] = Field(default=(), max_length=128)
    scheme_version_id: UUID | None = None  # Frozen single-jurisdiction legacy plans.
    classification_bindings: tuple[ClassificationJurisdictionBinding, ...] = Field(default=(), max_length=128)
    applicability: tuple[ApplicabilityBinding, ...] = Field(min_length=1, max_length=128)
    retrieval_query: KnowledgeRetrievalQuery
    requirement_review: bool = False
    input_capability_gap: Literal["MULTI_SUBJECT_WORKFLOW_NOT_CONFIGURED"] | None = None

    @model_validator(mode="after")
    def scoped_plan(self):
        q = self.retrieval_query
        if (UUID(q.project_id), UUID(q.analysis_snapshot_id)) != (
            self.project_id,
            self.analysis_snapshot_id,
        ):
            raise ValueError("retrieval plan scope mismatch")
        expected = (
            ("PROJECT", self.project_id)
            if self.mode == "SCENARIO_LEVEL"
            else (self.subject_type, self.subject_id)
        )
        if (q.subject_type, UUID(q.subject_id or q.project_id)) != expected:
            raise ValueError("retrieval subject mismatch")
        if (self.mode == "SCENARIO_LEVEL") != (self.subject_type == "SCENARIO"):
            raise ValueError("scenario/data mode mismatch")
        if self.mode == "SCENARIO_LEVEL" and (
            self.classification_data_item_ids or self.scheme_version_id
        ):
            raise ValueError("scenario mode cannot fabricate classification")
        if self.mode == "DATA_AWARE" and (
            not self.classification_data_item_ids or not (self.scheme_version_id or self.classification_bindings)
        ):
            raise ValueError("data mode requires explicit classification references")
        if self.input_capability_gap is not None and (
            self.mode != "DATA_AWARE"
            or len(self.classification_data_item_ids) < 2
            or self.subject_id not in self.classification_data_item_ids
        ):
            raise ValueError("invalid multi-subject capability boundary")
        if (
            self.subject_type == "DATA_ITEM"
            and self.input_capability_gap is None
            and self.classification_data_item_ids != (self.subject_id,)
        ):
            raise ValueError("classification subject mismatch")
        if len(set(self.classification_data_item_ids)) != len(self.classification_data_item_ids):
            raise ValueError("duplicate classification subject")
        if len({(v.jurisdiction_id, v.config_id) for v in self.applicability}) != len(
            self.applicability
        ):
            raise ValueError("duplicate applicability binding")
        if self.classification_bindings:
            if self.scheme_version_id is not None:
                raise ValueError("explicit binding plan cannot mix legacy scheme selection")
            jurisdictions = [b.jurisdiction_id for b in self.classification_bindings]
            if len(set(jurisdictions)) != len(jurisdictions) or set(jurisdictions) != {b.jurisdiction_id for b in self.applicability}:
                raise ValueError("classification bindings must cover exact applicability jurisdictions")
        return self


# Structured transport outcomes only; ordinary stage results never suppress flags.
def formal_outcome(result, ordinary):
    status = result.summary_status if hasattr(result, "summary_status") else ordinary
    if (
        getattr(result, "conflict_state", None) == "CONFLICTED"
        or getattr(result, "conflict_status", None) == "CONFLICTED"
        or status == "CONFLICTED"
    ):
        return StageOutcomeCode.CONFLICTED
    if status == "INSUFFICIENT_INPUT":
        return StageOutcomeCode.INSUFFICIENT_INPUT
    if (
        getattr(result, "input_sufficiency", None) in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}
        or status == "INSUFFICIENT_EVIDENCE"
    ):
        return StageOutcomeCode.EVIDENCE_INSUFFICIENT
    if getattr(result, "review_required", False) or status in {"REVIEW_REQUIRED", "TIED"}:
        return StageOutcomeCode.REVIEW_REQUIRED
    if status == "LOW_CONFIDENCE":
        return StageOutcomeCode.LOW_CONFIDENCE
    if status == "CAPABILITY_NOT_CONFIGURED":
        return StageOutcomeCode.CAPABILITY_NOT_CONFIGURED
    if status == "NOT_APPLICABLE":
        return StageOutcomeCode.NOT_APPLICABLE
    if status in {
        "NO_VIABLE_PATH",
        "NO_RECOMMENDATION",
        "UNDETERMINED",
        "UNKNOWN",
        "CONDITIONAL_ALTERNATIVES",
    }:
        return StageOutcomeCode.REVIEW_REQUIRED
    if status in {
        "COMPLETED",
        "SUCCESS",
        "CLASSIFIED",
        "APPLICABLE",
        "CONDITIONALLY_APPLICABLE",
        "OBLIGATIONS_IDENTIFIED",
        "CANDIDATES_IDENTIFIED",
        "ASSESSED",
        "RECOMMENDED",
        "PROPOSED",
        "CONDITIONAL_PROPOSAL",
        "DIRECT_TRANSFER_ALLOWED",
        "CONDITIONAL_TRANSFER_ALLOWED",
        "TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED",
        "REQUIREMENTS_IDENTIFIED",
    }:
        return StageOutcomeCode.SUCCESS
    return StageOutcomeCode.NON_RETRYABLE_FAILURE


class FormalWorkflowStages:
    """Application composition over existing E/F/G/H/I/J services and read ports."""

    def __init__(
        self,
        plan,
        *,
        contexts,
        knowledge_scope,
        retrieval,
        evidence,
        classification,
        country,
        decisions,
        scenario_rules=None,
        cross_border=None,
        document_requirements=None,
    ):
        self.plan = plan
        self.contexts, self.knowledge_scope = contexts, knowledge_scope
        self.retrieval, self.evidence = retrieval, evidence
        self.classification, self.country, self.decisions = classification, country, decisions
        self.scenario_rules = scenario_rules
        self.cross_border, self.document_requirements = cross_border, document_requirements

    def bindings(self):
        return {step: _BoundStage(self, step) for step in SemanticStep}

    def _check(self, request):
        p, i = self.plan, request.identity
        if (i.tenant_id, i.project_id, i.analysis_snapshot_id, i.request_context_ref, i.mode) != (
            p.tenant_id,
            p.project_id,
            p.analysis_snapshot_id,
            p.request_context_ref,
            p.mode,
        ):
            raise PermissionError("workflow plan not found")
        required = list(SemanticStep)[: list(SemanticStep).index(request.step)]
        if request.identity.graph_definition_version == "phase1l-a-canonical-v1":
            required = [s for s in required if s != SemanticStep.CROSS_BORDER]
        # Scenario classification has no result by design, not an invented UUID.
        if p.mode == "SCENARIO_LEVEL":
            required = [s for s in required if s != SemanticStep.CLASSIFICATION]
        if any(s not in request.result_refs for s in required):
            raise ValueError("missing upstream workflow reference")
        for step in list(SemanticStep)[:4]:
            if (
                step in request.result_refs
                and request.result_refs[step] != p.context_resolution_run_id
            ):
                raise PermissionError("workflow context reference mismatch")
        if (
            SemanticStep.KNOWLEDGE_SCOPE in request.result_refs
            and request.result_refs[SemanticStep.KNOWLEDGE_SCOPE] != p.analysis_snapshot_id
        ):
            raise PermissionError("workflow scope reference mismatch")

    def _context(self):
        p = self.plan
        if not self.contexts.project_exists(p.project_id):
            raise PermissionError("context project not found")
        value = self.contexts.get_context_resolution(p.project_id)
        if value is None:
            return None
        if (
            value.project_id != p.project_id
            or value.context_resolution_run_id != p.context_resolution_run_id
        ):
            raise ValueError("formal context changed; new snapshot/workflow required")
        self.contexts.pin_snapshot_context(
            analysis_snapshot_id=p.analysis_snapshot_id,
            project_id=p.project_id,
            context_resolution_run_id=p.context_resolution_run_id,
        )
        return value

    def _rag(self, request):
        run = request.result_refs[SemanticStep.RETRIEVAL]
        response = self.evidence.scoped_saved_response(str(run))
        rag = RAGContextPack.model_validate(response["rag_context_pack"])
        p = self.plan
        if (
            UUID(rag.scope.tenant_id),
            UUID(rag.scope.project_id),
            UUID(rag.scope.analysis_snapshot_id),
        ) != (p.tenant_id, p.project_id, p.analysis_snapshot_id) or UUID(
            rag.evidence_pack.retrieval_run_id
        ) != run:
            raise PermissionError("retrieval scope mismatch")
        q = p.retrieval_query
        if (rag.scope.subject_type, UUID(rag.scope.subject_id)) != (
            q.subject_type,
            UUID(q.subject_id or q.project_id),
        ):
            raise PermissionError("retrieval scope mismatch")
        return rag

    def _result(self, request, status, refs=(), reasons=(), fallback=None):
        if status == StageOutcomeCode.EVIDENCE_INSUFFICIENT and fallback is None:
            fallback = UUID(self._rag(request).evidence_pack.evidence_pack_id)
        return StageExecutionResult(
            status=status,
            result_ref=refs[0] if refs else None,
            related_result_refs=tuple(refs),
            fallback_ref=fallback,
            reason_codes=tuple(reasons)[:16],
        )

    def execute(self, request):
        self._check(request)
        step, p = request.step, self.plan
        if p.input_capability_gap is not None:
            context = self._context()
            if context is None:
                return self._result(
                    request,
                    StageOutcomeCode.INSUFFICIENT_INPUT,
                    reasons=("FORMAL_CONTEXT_REQUIRED",),
                )
            if context.conflicts:
                return self._result(
                    request,
                    StageOutcomeCode.CONFLICTED,
                    (context.context_resolution_run_id,),
                    ("FORMAL_CONTEXT_REFERENCE",),
                )
            if context.unresolved_items:
                return self._result(
                    request,
                    StageOutcomeCode.REVIEW_REQUIRED,
                    (context.context_resolution_run_id,),
                    ("FORMAL_CONTEXT_REFERENCE",),
                )
            return self._result(
                request,
                StageOutcomeCode.CAPABILITY_NOT_CONFIGURED,
                reasons=(p.input_capability_gap,),
            )
        if step in {
            SemanticStep.REQUIREMENT,
            SemanticStep.FORMAL_CONTEXT,
            SemanticStep.DATA_FLOW,
            SemanticStep.JURISDICTION,
        }:
            value = self._context()
            if value is None:
                return self._result(
                    request,
                    StageOutcomeCode.INSUFFICIENT_INPUT,
                    reasons=("FORMAL_CONTEXT_REQUIRED",),
                )
            status = StageOutcomeCode.SUCCESS
            if value.conflicts:
                status = StageOutcomeCode.CONFLICTED
            elif value.unresolved_items:
                status = StageOutcomeCode.REVIEW_REQUIRED
            if step == SemanticStep.REQUIREMENT:
                if p.mode == "SCENARIO_LEVEL" and p.subject_id not in {
                    v.scenario_definition_id for v in value.scenario_contexts
                }:
                    return self._result(
                        request,
                        StageOutcomeCode.INSUFFICIENT_INPUT,
                        reasons=("FORMAL_SCENARIO_REQUIRED",),
                    )
                if p.requirement_review and request.review_ref is None:
                    status = StageOutcomeCode.REVIEW_REQUIRED
            elif step == SemanticStep.DATA_FLOW:
                if p.mode == "SCENARIO_LEVEL":
                    status = (
                        StageOutcomeCode.NOT_APPLICABLE
                        if status == StageOutcomeCode.SUCCESS
                        else status
                    )
                else:
                    items = self.contexts.get_data_items(p.project_id)
                    valid = {
                        UUID(v["data_item_id"])
                        for v in items
                        if v["validation_status"] == "VALIDATED"
                        and not v.get("review_required")
                        and v["version"] == value.version
                    }
                    if not set(p.classification_data_item_ids) <= valid:
                        status = StageOutcomeCode.INSUFFICIENT_INPUT
                    if p.subject_type == "DATA_FLOW":
                        edges = self.contexts.get_data_flows(p.project_id)["edges"]
                        if not any(
                            UUID(e["flow_edge_id"]) == p.subject_id
                            and e["validation_status"] == "VALIDATED"
                            and e["version"] == value.version
                            for e in edges
                        ):
                            status = StageOutcomeCode.INSUFFICIENT_INPUT
            elif step == SemanticStep.JURISDICTION:
                valid = {
                    v.jurisdiction_id
                    for v in value.jurisdiction_contexts
                    if v.validation_status == "VALIDATED" and not v.review_required
                }
                if not valid or valid != {v.jurisdiction_id for v in p.applicability}:
                    status = StageOutcomeCode.INSUFFICIENT_INPUT
            return self._result(
                request, status, (value.context_resolution_run_id,), ("FORMAL_CONTEXT_REFERENCE",)
            )
        if step == SemanticStep.KNOWLEDGE_SCOPE:
            q = p.retrieval_query
            scope = self.knowledge_scope.resolve(
                str(p.project_id),
                subject_type=q.subject_type,
                subject_id=q.subject_id,
                snapshot_id=str(p.analysis_snapshot_id),
                languages=q.languages,
            )
            if (
                UUID(scope.tenant_id),
                UUID(scope.project_id),
                UUID(scope.analysis_snapshot_id),
            ) != (p.tenant_id, p.project_id, p.analysis_snapshot_id):
                raise PermissionError("knowledge scope mismatch")
            status = (
                StageOutcomeCode.REVIEW_REQUIRED
                if scope.review_required
                else StageOutcomeCode.SUCCESS
            )
            return self._result(
                request, status, (p.analysis_snapshot_id,), ("PINNED_KNOWLEDGE_SCOPE",)
            )
        if step == SemanticStep.RETRIEVAL:
            from hashlib import sha256

            query = p.retrieval_query.model_copy(
                update={"idempotency_key": sha256(request.idempotency_key.encode()).hexdigest()}
            )
            response = self.retrieval.retrieve(query)
            return self._result(
                request,
                StageOutcomeCode.SUCCESS,
                (UUID(response["retrieval_run_id"]),),
                ("PERSISTED_RETRIEVAL_RUN",),
            )
        if step == SemanticStep.SUFFICIENCY:
            rag = self._rag(request)
            suff = rag.knowledge_sufficiency
            status = (
                StageOutcomeCode.CONFLICTED
                if suff.status == "CONFLICTED"
                else StageOutcomeCode.EVIDENCE_INSUFFICIENT
                if suff.status != "SUFFICIENT"
                else StageOutcomeCode.REVIEW_REQUIRED
                if suff.review_required
                else StageOutcomeCode.EVIDENCE_SUFFICIENT
            )
            return self._result(
                request,
                status,
                (UUID(suff.sufficiency_result_id),),
                tuple(suff.reason_codes),
                UUID(rag.evidence_pack.evidence_pack_id)
                if status == StageOutcomeCode.EVIDENCE_INSUFFICIENT
                else None,
            )
        if step == SemanticStep.CLASSIFICATION:
            if p.mode == "SCENARIO_LEVEL":
                return self._result(
                    request,
                    StageOutcomeCode.NOT_APPLICABLE,
                    reasons=("SCENARIO_LEVEL_NO_CLASSIFICATION",),
                )
            refs = []
            executions = (
                tuple((b.jurisdiction_id,b.scheme_version_id) for b in p.classification_bindings)
                if p.classification_bindings else ((None,p.scheme_version_id),)
            )
            for item in p.classification_data_item_ids:
                for jurisdiction, scheme in executions:
                    kwargs = {} if jurisdiction is None else {"jurisdiction_id": jurisdiction}
                    outcome = self.classification.execute(
                        project_id=p.project_id, snapshot_id=p.analysis_snapshot_id,
                        data_item_id=item, scheme_version_id=scheme, **kwargs,
                    )
                    status = formal_outcome(outcome.result or outcome, outcome.status)
                    if outcome.result:
                        refs.append(outcome.result.classification_result_id)
                    if status != StageOutcomeCode.SUCCESS:
                        return self._result(request, status, tuple(refs), outcome.reason_codes)
            return self._result(
                request, StageOutcomeCode.SUCCESS, tuple(refs), ("FORMAL_CLASSIFICATION",)
            )
        if step == SemanticStep.APPLICABILITY:
            if p.mode == "SCENARIO_LEVEL":
                context = self._context()
                if context is None or not context.business_fact_summary.get("facts"):
                    return self._result(
                        request,
                        StageOutcomeCode.INSUFFICIENT_INPUT,
                        reasons=("FORMAL_BUSINESS_FACT_REQUIRED",),
                    )
                if context.conflicts:
                    return self._result(
                        request,
                        StageOutcomeCode.CONFLICTED,
                        reasons=("BUSINESS_FACT_CONFLICT",),
                    )
                facts = context.business_fact_summary["facts"]
                if any(
                    f.get("review_required") or f.get("validation_status") != "VALIDATED"
                    for f in facts
                ):
                    return self._result(
                        request,
                        StageOutcomeCode.REVIEW_REQUIRED,
                        reasons=("FORMAL_BUSINESS_FACT_REVIEW_REQUIRED",),
                    )
            retrieval_id = request.result_refs[SemanticStep.RETRIEVAL]
            classes = request.result_ref_sets.get(SemanticStep.CLASSIFICATION, ())
            classification_results = {ident: self.country.classify(ident) for ident in classes}
            refs, outcomes, reasons = [], [], []
            for binding in p.applicability:
                scoped_classes = tuple(ident for ident, result in classification_results.items()
                    if not p.classification_bindings or result.jurisdiction_id == binding.jurisdiction_id)
                scoped_hits = tuple(h for ident in scoped_classes for h in classification_results[ident].rule_hit_ids)
                if p.mode == "SCENARIO_LEVEL":
                    if self.scenario_rules is None:
                        return self._result(
                            request,
                            StageOutcomeCode.CAPABILITY_NOT_CONFIGURED,
                            reasons=("SCENARIO_FACT_SERVICE_NOT_CONFIGURED",),
                        )
                    profile = self.country.resolve_profile(
                        project_id=p.project_id,
                        snapshot_id=p.analysis_snapshot_id,
                        jurisdiction_id=binding.jurisdiction_id,
                    )
                    if profile.scenario_configuration.missing_inputs:
                        return self._result(
                            request,
                            StageOutcomeCode.INSUFFICIENT_INPUT,
                            reasons=("FORMAL_BUSINESS_FACT_REQUIRED",),
                        )
                    scoped_hits = tuple(
                        h.rule_hit_id
                        for h in self.scenario_rules.scenario_rule_hits(
                            p.project_id,
                            p.analysis_snapshot_id,
                            p.subject_id,
                            binding.jurisdiction_id,
                            retrieval_id,
                        )
                    )
                value = self.country.resolve_regulation_applicability(
                    ApplicabilityRequest(
                        project_id=p.project_id,
                        analysis_snapshot_id=p.analysis_snapshot_id,
                        subject_type=p.subject_type,
                        subject_id=p.subject_id,
                        jurisdiction_id=binding.jurisdiction_id,
                        applicability_config_id=binding.config_id,
                        retrieval_run_id=retrieval_id,
                        classification_result_ids=scoped_classes,
                        rule_hit_ids=tuple(dict.fromkeys(scoped_hits)),
                    )
                )
                refs.append(value.applicability_result_id)
                outcomes.append(formal_outcome(value, value.applicability_status))
                reasons.extend(value.reason_codes)
            status = next(
                (
                    code
                    for code in (
                        StageOutcomeCode.CONFLICTED,
                        StageOutcomeCode.EVIDENCE_INSUFFICIENT,
                        StageOutcomeCode.REVIEW_REQUIRED,
                        StageOutcomeCode.INSUFFICIENT_INPUT,
                        StageOutcomeCode.CAPABILITY_NOT_CONFIGURED,
                    )
                    if code in outcomes
                ),
                StageOutcomeCode.NOT_APPLICABLE
                if all(o == StageOutcomeCode.NOT_APPLICABLE for o in outcomes)
                else StageOutcomeCode.SUCCESS,
            )
            return self._result(request, status, tuple(refs), tuple(dict.fromkeys(reasons)))
        if step == SemanticStep.CROSS_BORDER or (
            step == SemanticStep.DOCUMENTS
            and request.identity.graph_definition_version != "phase1l-a-canonical-v1"
        ):
            service = (
                self.cross_border
                if step == SemanticStep.CROSS_BORDER
                else self.document_requirements
            )
            if service is None:
                return self._result(
                    request,
                    StageOutcomeCode.CAPABILITY_NOT_CONFIGURED,
                    reasons=("FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED",),
                )
            value = service.execute(
                FormalAuthorityRequest(
                    project_id=p.project_id,
                    analysis_snapshot_id=p.analysis_snapshot_id,
                    subject_type=p.subject_type,
                    subject_id=p.subject_id,
                    stage_kind="CROSS_BORDER"
                    if step == SemanticStep.CROSS_BORDER
                    else "DOCUMENT_REQUIREMENT",
                    obligation_result_id=request.result_refs[SemanticStep.OBLIGATION],
                    cross_border_result_id=request.result_refs.get(SemanticStep.CROSS_BORDER)
                    if step == SemanticStep.DOCUMENTS
                    else None,
                    final_path_result_id=request.result_refs.get(SemanticStep.FINAL_PATH)
                    if step == SemanticStep.DOCUMENTS
                    else None,
                    idempotency_key=request.idempotency_key,
                )
            )
            # C0 review authority precedes ordinary evidence-warning routing.
            outcome = (
                StageOutcomeCode.CONFLICTED
                if value.conflict_state == "CONFLICTED"
                else StageOutcomeCode.REVIEW_REQUIRED
                if value.review_required
                else formal_outcome(value, value.ordinary_status)
            )
            return self._result(request, outcome, (value.result_id,), value.reason_codes)
        if step in {
            SemanticStep.OBLIGATION,
            SemanticStep.CANDIDATE_PATH,
            SemanticStep.RISK,
            SemanticStep.RECOMMENDATION,
            SemanticStep.FINAL_PATH,
        }:
            kind = step.value.upper()
            value = self.decisions.execute(
                DecisionRequest(
                    project_id=p.project_id,
                    analysis_snapshot_id=p.analysis_snapshot_id,
                    subject_type=p.subject_type,
                    subject_id=p.subject_id,
                    stage_kind=kind,
                    applicability_result_ids=request.result_ref_sets[SemanticStep.APPLICABILITY],
                    upstream_refs=tuple(
                        UpstreamIdentifier(
                            kind=k, result_id=request.result_refs[SemanticStep(k.lower())]
                        )
                        for k in PARENTS[kind]
                    ),
                    idempotency_key=request.idempotency_key,
                )
            )
            return self._result(
                request,
                formal_outcome(value, value.ordinary_status),
                (value.result_id,),
                value.reason_codes,
            )
        final_id = request.result_refs[SemanticStep.FINAL_PATH]
        final = self.decisions.read("FINAL_PATH", final_id)
        status = formal_outcome(final, final.ordinary_status)
        if status != StageOutcomeCode.SUCCESS:
            return self._result(request, status, (final_id,), final.reason_codes)
        if step == SemanticStep.DOCUMENTS:
            return self._result(
                request,
                StageOutcomeCode.NOT_APPLICABLE,
                (final_id,),
                ("DOCUMENTS_BOUNDARY_ONLY", "CAPABILITY_NOT_CONFIGURED"),
            )
        if request.identity.graph_definition_version != "phase1l-a-canonical-v1":
            for service, upstream in (
                (self.cross_border, SemanticStep.CROSS_BORDER),
                (self.document_requirements, SemanticStep.DOCUMENTS),
            ):
                value = service.read(request.result_refs[upstream])
                if (value.project_id, value.analysis_snapshot_id) != (
                    p.project_id,
                    p.analysis_snapshot_id,
                ):
                    raise PermissionError("formal projection scope mismatch")
                outcome = (
                    StageOutcomeCode.CONFLICTED
                    if value.conflict_state == "CONFLICTED"
                    else StageOutcomeCode.REVIEW_REQUIRED
                    if value.review_required
                    else formal_outcome(value, value.ordinary_status)
                )
                if outcome not in {StageOutcomeCode.SUCCESS, StageOutcomeCode.NOT_APPLICABLE}:
                    return self._result(request, outcome, (value.result_id,), value.reason_codes)
            return self._result(
                request,
                StageOutcomeCode.SUCCESS,
                (request.result_refs[SemanticStep.DOCUMENTS],),
                ("STAGE1_FORMAL_RESULT_PROJECTION_READY", "STAGE2_USER_OPT_IN_REQUIRED"),
            )
        return self._result(
            request, StageOutcomeCode.SUCCESS, (final_id,), ("REPORT_PROJECTION_REFERENCE_ONLY",)
        )


class _BoundStage:
    def __init__(self, services, step):
        self.services, self.step = services, step

    def execute(self, request):
        if request.step != self.step:
            raise ValueError("stage binding mismatch")
        return self.services.execute(request)


class WorkflowDeliveryService:
    """Serialize queue deliveries around the existing runtime, not node retries.

    The guard is an infrastructure port; no runtime, graph or checkpoint logic
    is reproduced here. Owning-service idempotency still protects stage retries.
    """

    def __init__(self, runtime, factory, guard):
        self.runtime, self.factory, self.guard = runtime, factory, guard

    def start(self, workflow_run_id, initial_state):
        self.factory.authorize(workflow_run_id, "execute")
        with self.guard.acquire(workflow_run_id):
            self.factory.authorize(workflow_run_id, "execute")
            return self.runtime.start(workflow_run_id, initial_state)

    def resume(self, workflow_run_id, decision):
        self.factory.authorize(workflow_run_id, "review")
        with self.guard.acquire(workflow_run_id):
            self.factory.authorize(workflow_run_id, "review")
            return self.runtime.resume(workflow_run_id, decision)

    def inspect_checkpoint_state(self, workflow_run_id):
        return self.runtime.inspect_checkpoint_state(workflow_run_id)

    def get_status(self, workflow_run_id):
        return self.runtime.get_status(workflow_run_id)

    def stream_events(self, workflow_run_id):
        return self.runtime.stream_events(workflow_run_id)

    def cancel(self, workflow_run_id):
        self.factory.authorize(workflow_run_id, "execute")
        return self.runtime.cancel(workflow_run_id)


class FormalWorkflowAuthorization:
    """Bind the server-prepared plan to the existing fresh authorization port."""

    def __init__(self, authorization, plan):
        self.authorization, self.plan = authorization, plan

    def authorize(self, workflow_run_id, operation):
        identity = self.authorization.authorize(workflow_run_id, operation)
        p = self.plan
        if (
            identity.tenant_id,
            identity.project_id,
            identity.analysis_snapshot_id,
            identity.request_context_ref,
            identity.mode,
        ) != (p.tenant_id, p.project_id, p.analysis_snapshot_id, p.request_context_ref, p.mode):
            raise PermissionError("workflow plan not found")
        return identity

    def authorize_review(self, workflow_run_id, decision):
        self.authorize(workflow_run_id, "review")
        return self.authorization.authorize_review(workflow_run_id, decision)
