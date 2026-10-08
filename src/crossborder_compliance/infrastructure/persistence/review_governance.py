"""Operations of PostgresReviewRepository, using canonical review/input tables."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, select, text

from crossborder_compliance.application.intake_services import IntakeFacts
from crossborder_compliance.application.review_services import (
    ReviewChoice,
    ReviewHistoryItem,
    ReviewLineage,
    ReviewPage,
    ReviewView,
)
from crossborder_compliance.domain.contracts import ProvenanceDTO, ReviewDecisionDTO
from crossborder_compliance.domain.review_governance import resolution_actions
from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.review_models import ReviewCorrectionEntity


class ReviewConflict(ValueError):
    pass


class ReviewGovernanceOperations:
    def describe(
        self, review_id, *, stage, reasons, conflict_id, requirement_confirmation, result_refs=None
    ):
        with self._sessions() as session, session.begin():
            task, run, snapshot, _version, project = self._scope(session, review_id, lock=True)
            if run.graph_definition_version != "phase1l-a-canonical-v2":
                return  # Historical authority is never retrofitted by product review.
            if conflict_id:
                conflict = session.get(e.ContextConflictEntity, str(conflict_id))
                pin = session.scalar(
                    select(e.AnalysisSnapshotContextPinEntity).where(
                        e.AnalysisSnapshotContextPinEntity.tenant_id == self.tenant_id,
                        e.AnalysisSnapshotContextPinEntity.analysis_snapshot_id
                        == snapshot.analysis_snapshot_id,
                    )
                )
                if (
                    not conflict
                    or not pin
                    or conflict.tenant_id != self.tenant_id
                    or conflict.project_id != project.project_id
                    or conflict.version != pin.context_resolution_version
                ):
                    raise LookupError("REVIEW_NOT_FOUND")
            if task.owning_stage is not None:
                if (task.owning_stage, task.reason_codes_json, task.requirement_confirmation) != (
                    stage,
                    list(reasons),
                    requirement_confirmation,
                ):
                    raise ReviewConflict("REVIEW_CONTEXT_MISMATCH")
                return
            task.owning_stage = stage
            task.reason_codes_json = list(reasons)
            task.requirement_confirmation = requirement_confirmation
            task.required_role = "workflow:review"
            from crossborder_compliance.infrastructure.persistence import decision_models as j
            from crossborder_compliance.infrastructure.persistence import formal_result_models as c0

            models = {**j.MODELS, **c0.MODELS}
            evidence, basis = set(), set()

            def references(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key == "evidence_ids":
                            evidence.update(item)
                        elif key == "legal_basis_ids":
                            basis.update(item)
                        else:
                            references(item)
                elif isinstance(value, list):
                    for item in value:
                        references(item)

            for step, ref in (result_refs or {}).items():
                kind = "DOCUMENT_REQUIREMENT" if step == "documents" else step.upper()
                if kind in models:
                    row = session.get(models[kind], str(ref))
                    if (
                        not row
                        or row.tenant_id != self.tenant_id
                        or row.analysis_snapshot_id != snapshot.analysis_snapshot_id
                        or row.project_id != project.project_id
                    ):
                        raise LookupError("REVIEW_NOT_FOUND")
                    references(row.result_json)
            task.evidence_ids_json, task.legal_basis_ids_json = sorted(evidence), sorted(basis)
            if conflict_id:
                task.object_type, task.object_id = "CONTEXT_CONFLICT", str(conflict_id)
            elif requirement_confirmation and _version.intake_json.get("analysis_as_of_date"):
                task.object_type, task.object_id = "PROJECT_INTAKE", _version.project_version_id

    def _scope(self, session, review_id, *, write=False, lock=False):
        query = select(b.ReviewTaskEntity).where(
            b.ReviewTaskEntity.tenant_id == self.tenant_id,
            b.ReviewTaskEntity.review_id == str(review_id),
        )
        task = session.scalar(query.with_for_update() if lock else query)
        run = session.get(b.WorkflowRunEntity, task.workflow_run_id) if task else None
        snapshot = session.get(b.AnalysisSnapshotEntity, run.analysis_snapshot_id) if run else None
        version = (
            session.get(b.ProjectVersionEntity, snapshot.project_version_id) if snapshot else None
        )
        project = session.get(b.ProjectEntity, version.project_id) if version else None
        scopes = self._context.permission.scopes
        if (
            not task
            or not run
            or not snapshot
            or not version
            or not project
            or any(v.tenant_id != self.tenant_id for v in (task, run, snapshot, version, project))
            or run.thread_id != run.workflow_run_id
            or task.thread_id != run.workflow_run_id
            or snapshot.status != "ACTIVE"
            or project.status != "ACTIVE"
            or "workflow:read" not in scopes
        ):
            raise LookupError("REVIEW_NOT_FOUND")
        if f"project:{project.project_id}:comply" not in scopes:
            from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
                PostgresProjectRepository,
            )

            owner = PostgresProjectRepository(self._sessions, self._context)
            try:
                owner._intake_permission("read")
                owner._intake_project(session, UUID(project.project_id))
            except (LookupError, PermissionError) as exc:
                raise LookupError("REVIEW_NOT_FOUND") from exc
        if write and ("workflow:review" not in scopes or task.required_role not in scopes):
            raise LookupError("REVIEW_NOT_FOUND")
        return task, run, snapshot, version, project

    def _choices(self, session, task, snapshot, project):
        if task.object_type != "CONTEXT_CONFLICT":
            return ()
        conflict = session.get(e.ContextConflictEntity, task.object_id)
        pin = session.scalar(
            select(e.AnalysisSnapshotContextPinEntity).where(
                e.AnalysisSnapshotContextPinEntity.tenant_id == self.tenant_id,
                e.AnalysisSnapshotContextPinEntity.analysis_snapshot_id
                == snapshot.analysis_snapshot_id,
            )
        )
        if (
            not conflict
            or not pin
            or conflict.tenant_id != self.tenant_id
            or conflict.project_id != project.project_id
            or conflict.version != pin.context_resolution_version
        ):
            raise LookupError("REVIEW_NOT_FOUND")
        if conflict.conflict_type == "BUSINESS_FACT_CONFLICT":
            rows = session.scalars(
                select(e.BusinessFactEntity).where(
                    e.BusinessFactEntity.tenant_id == self.tenant_id,
                    e.BusinessFactEntity.project_id == project.project_id,
                    e.BusinessFactEntity.version == pin.context_resolution_version,
                    e.BusinessFactEntity.fact_id.in_(conflict.object_ids_json),
                )
            ).all()
            return tuple(
                ReviewChoice(
                    object_id=r.fact_id,
                    object_type="BUSINESS_FACT",
                    display_value=json.dumps(r.normalized_value_json, ensure_ascii=False),
                    source_trace_ids=tuple(
                        dict.fromkeys(
                            t
                            for resolution in session.scalars(
                                select(e.CandidateResolutionEntity).where(
                                    e.CandidateResolutionEntity.tenant_id == self.tenant_id,
                                    e.CandidateResolutionEntity.formal_object_id == r.fact_id,
                                    e.CandidateResolutionEntity.version == r.version,
                                )
                            )
                            for t in resolution.source_trace_ids_json
                        )
                    ),
                    source_document_ids=tuple(r.source_document_ids_json),
                    structured_provenance=tuple(
                        ProvenanceDTO.model_validate(x) for x in r.structured_provenance_json
                    ),
                )
                for r in rows
            )
        if conflict.conflict_type == "PRODUCT_CONTEXT_CONFLICT":
            from crossborder_compliance.infrastructure.persistence.metadata_models import (
                MetadataDefinitionEntity,
            )

            rows = session.scalars(
                select(MetadataDefinitionEntity).where(
                    MetadataDefinitionEntity.tenant_id == self.tenant_id,
                    MetadataDefinitionEntity.definition_id.in_(conflict.object_ids_json),
                )
            ).all()
            return tuple(
                ReviewChoice(
                    object_id=r.definition_id,
                    object_type="PRODUCT_CONTEXT",
                    display_value=r.display_name,
                    source_trace_ids=tuple(conflict.source_trace_ids_json),
                )
                for r in rows
            )
        return ()

    def _view(self, session, values):
        task, run, snapshot, version, project = values
        history = tuple(
            ReviewHistoryItem(
                decision_id=h.decision_id,
                decision=h.decision_code,
                comment=h.comment,
                decided_by=h.decided_by,
                decided_at=h.decided_at,
            )
            for h in session.scalars(
                select(b.ReviewDecisionEntity)
                .where(
                    b.ReviewDecisionEntity.tenant_id == self.tenant_id,
                    b.ReviewDecisionEntity.review_id == task.review_id,
                )
                .order_by(b.ReviewDecisionEntity.decided_at, b.ReviewDecisionEntity.decision_id)
            )
        )
        actions, mode, gap = resolution_actions(
            stage=task.owning_stage,
            reasons=task.reason_codes_json,
            requirement_confirmation=task.requirement_confirmation,
            modern=run.graph_definition_version == "phase1l-a-canonical-v2"
            and task.review_type == "WORKFLOW_STAGE_REVIEW"
            and task.owning_stage is not None,
        )
        if (
            task.status == "PENDING"
            and task.requirement_confirmation
            and (task.decision_json or {}).get("decision") == "REQUEST_CHANGES"
            and task.object_type == "PROJECT_INTAKE"
        ):
            actions, mode = ("ADD_INFORMATION", "REQUEST_CHANGES", "REJECT"), "SUCCESSOR_SNAPSHOT"
        if (
            "workflow:review" not in self._context.permission.scopes
            or task.required_role not in self._context.permission.scopes
        ):
            actions = ()
        if (
            not {"project:update", "project:confirm", "workflow:execute"}
            <= self._context.permission.scopes
        ):
            actions = tuple(a for a in actions if a not in {"SUBMIT_CORRECTION", "ADD_INFORMATION"})
        lineage = session.scalar(
            select(ReviewCorrectionEntity)
            .where(
                ReviewCorrectionEntity.tenant_id == self.tenant_id,
                ReviewCorrectionEntity.source_review_id == task.review_id,
            )
            .order_by(ReviewCorrectionEntity.created_at.desc())
        )
        presentation = (
            "SUPERSEDED"
            if lineage
            else "CHANGES_REQUESTED"
            if task.status == "PENDING"
            and (task.decision_json or {}).get("decision") == "REQUEST_CHANGES"
            else task.status
        )
        if task.status != "PENDING" or lineage:
            actions = ()
        if (
            lineage
            and {"workflow:review", task.required_role, "workflow:execute"}
            <= self._context.permission.scopes
        ):
            target_run = session.get(b.WorkflowRunEntity, lineage.successor_workflow_run_id)
            if (
                target_run
                and target_run.tenant_id == self.tenant_id
                and target_run.status == "RUNNING"
            ):
                actions = ("CONTINUE_SUCCESSOR",)
        continuation = "NOT_AVAILABLE"
        if task.status == "APPROVED" and mode == "SAME_SNAPSHOT":
            other_pending = session.scalar(
                select(b.ReviewTaskEntity.review_id).where(
                    b.ReviewTaskEntity.workflow_run_id == run.workflow_run_id,
                    b.ReviewTaskEntity.tenant_id == self.tenant_id,
                    b.ReviewTaskEntity.review_id != task.review_id,
                    b.ReviewTaskEntity.status == "PENDING",
                )
            )
            continuation = (
                "RESUME_PENDING"
                if run.status in {"REVIEW_REQUIRED", "RUNNING"} and not other_pending
                else "CONTINUED"
                if run.status == "COMPLETED" or other_pending
                else "NOT_AVAILABLE"
            )
            if (
                continuation == "RESUME_PENDING"
                and {"workflow:review", task.required_role} <= self._context.permission.scopes
                and (task.decision_json or {}).get("decided_by")
                == self._context.permission.actor_id
            ):
                actions = ("RESUME",)
        return ReviewView(
            review_id=task.review_id,
            project_id=project.project_id,
            analysis_snapshot_id=snapshot.analysis_snapshot_id,
            workflow_run_id=run.workflow_run_id,
            review_type=task.review_type,
            reason_codes=tuple(task.reason_codes_json),
            reason_summary=task.reason,
            object_type=task.object_type,
            object_id=task.object_id,
            owning_stage=task.owning_stage,
            status=task.status,
            presentation_state=presentation,
            allowed_actions=actions,
            resolution_mode=mode,
            required_role=task.required_role,
            continuation_status=continuation,
            created_at=task.created_at,
            updated_at=task.updated_at,
            record_version=task.record_version,
            evidence_refs=tuple(task.evidence_ids_json),
            legal_basis_refs=tuple(task.legal_basis_ids_json),
            choices=self._choices(session, task, snapshot, project),
            history=history,
            lineage=self._lineage(lineage) if lineage else None,
            capability_gap=gap,
            intake_facts={
                k: v for k, v in version.intake_json.items() if k in IntakeFacts.model_fields
            }
            if task.object_type == "PROJECT_INTAKE"
            else None,
        )

    @staticmethod
    def _lineage(row):
        return ReviewLineage(
            **{k: getattr(row, k) for k in ReviewLineage.model_fields if k != "rerun_from_stage"}
        )

    def read(self, review_id):
        with self._sessions() as session:
            return self._view(session, self._scope(session, review_id))

    def authorized_review(self, review_id):
        with self._sessions() as session:
            return self._view(session, self._scope(session, review_id, write=True))

    def authorized_successor(self, review_id):
        with self._sessions() as session:
            value = self._view(session, self._scope(session, review_id, write=True))
            if value.lineage is None or "workflow:execute" not in self._context.permission.scopes:
                raise ReviewConflict("ACTION_NOT_ALLOWED")
            return value

    def approved_decision(self, review_id):
        with self._sessions() as session:
            values = self._scope(session, review_id, write=True)
            task = values[0]
            if (
                task.status != "APPROVED"
                or not task.requirement_confirmation
                or (task.decision_json or {}).get("decided_by") != self._context.permission.actor_id
            ):
                raise ReviewConflict("ACTION_NOT_ALLOWED")
            decision = ReviewDecisionDTO.model_validate(task.decision_json)
            row = session.get(b.ReviewDecisionEntity, str(decision.decision_id))
            if (
                not row
                or row.tenant_id != self.tenant_id
                or row.decision_payload_json != task.decision_json
            ):
                raise ReviewConflict("REVIEW_CONTEXT_MISMATCH")
            return decision, self._view(session, values)

    def list(
        self,
        *,
        status=None,
        review_type=None,
        project_id=None,
        owning_stage=None,
        created_after=None,
        created_before=None,
        offset=0,
        limit=25,
        order="CREATED_DESC",
    ):
        if "workflow:read" not in self._context.permission.scopes:
            raise LookupError("REVIEW_NOT_FOUND")
        if offset < 0 or not 1 <= limit <= 100 or order not in {"CREATED_DESC", "CREATED_ASC"}:
            raise ValueError("INVALID_REVIEW_PAGINATION")
        # Permission filtering happens in SQL, before counting/pagination.
        from sqlalchemy import or_

        grants = [
            scope.split(":")[1]
            for scope in self._context.permission.scopes
            if scope.startswith("project:") and scope.endswith(":comply") and scope.count(":") == 2
        ]
        first = select(b.ProjectVersionEntity.project_id).where(
            b.ProjectVersionEntity.tenant_id == self.tenant_id,
            b.ProjectVersionEntity.version_no == 1,
            b.ProjectVersionEntity.intake_json["provenance"]["actor_ref"].as_string()
            == self._context.permission.actor_id,
        )
        allowed = b.ProjectEntity.project_id.in_(grants)
        if "project:read" in self._context.permission.scopes:
            allowed = or_(allowed, b.ProjectEntity.project_id.in_(first))
        query = (
            select(b.ReviewTaskEntity.review_id)
            .join(
                b.WorkflowRunEntity,
                b.WorkflowRunEntity.workflow_run_id == b.ReviewTaskEntity.workflow_run_id,
            )
            .join(
                b.AnalysisSnapshotEntity,
                b.AnalysisSnapshotEntity.analysis_snapshot_id
                == b.WorkflowRunEntity.analysis_snapshot_id,
            )
            .join(
                b.ProjectVersionEntity,
                b.ProjectVersionEntity.project_version_id
                == b.AnalysisSnapshotEntity.project_version_id,
            )
            .join(b.ProjectEntity, b.ProjectEntity.project_id == b.ProjectVersionEntity.project_id)
            .where(
                *[
                    model.tenant_id == self.tenant_id
                    for model in (
                        b.ReviewTaskEntity,
                        b.WorkflowRunEntity,
                        b.AnalysisSnapshotEntity,
                        b.ProjectVersionEntity,
                        b.ProjectEntity,
                    )
                ],
                allowed,
                b.ProjectEntity.status == "ACTIVE",
                b.AnalysisSnapshotEntity.status == "ACTIVE",
            )
        )
        for col, value in (
            (b.ReviewTaskEntity.status, status),
            (b.ReviewTaskEntity.review_type, review_type),
            (b.ProjectEntity.project_id, str(project_id) if project_id else None),
            (b.ReviewTaskEntity.owning_stage, owning_stage),
        ):
            if value is not None:
                query = query.where(col == value)
        if created_after:
            query = query.where(b.ReviewTaskEntity.created_at >= created_after)
        if created_before:
            query = query.where(b.ReviewTaskEntity.created_at <= created_before)
        with self._sessions() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            ids = session.scalars(
                query.order_by(
                    b.ReviewTaskEntity.created_at.asc()
                    if order == "CREATED_ASC"
                    else b.ReviewTaskEntity.created_at.desc(),
                    b.ReviewTaskEntity.review_id,
                )
                .offset(offset)
                .limit(limit)
            ).all()
            return ReviewPage(
                items=tuple(self._view(session, self._scope(session, UUID(i))) for i in ids),
                total=total,
                offset=offset,
                limit=limit,
            )

    def _request_key(self, session, review_id, request, operation):
        actor = self._context.permission.actor_id
        digest = sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        client = sha256(f"review:{self.tenant_id}:{actor}".encode()).hexdigest()
        key = f"review:{operation}:{review_id}:{request.idempotency_key}"
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k,0))"), {"k": f"{client}:{key}"}
        )
        row = session.scalar(
            select(b.ApiIdempotencyEntity).where(
                b.ApiIdempotencyEntity.tenant_id == self.tenant_id,
                b.ApiIdempotencyEntity.api_client_id == client,
                b.ApiIdempotencyEntity.idempotency_key == key,
            )
        )
        if row:
            if row.request_hash != digest:
                raise ReviewConflict("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return row, True
        row = b.ApiIdempotencyEntity(
            api_idempotency_id=str(uuid4()),
            tenant_id=self.tenant_id,
            api_client_id=client,
            idempotency_key=key,
            request_hash=digest,
        )
        session.add(row)
        return row, False

    def decide(self, review_id, request):
        with self._sessions() as session, session.begin():
            values = self._scope(session, review_id, write=True, lock=True)
            task, run, snapshot, _version, _project = values
            key, duplicate = self._request_key(session, review_id, request, "decision")
            if duplicate:
                stored = session.get(b.ReviewDecisionEntity, key.response_ref)
                if (
                    not stored
                    or stored.tenant_id != self.tenant_id
                    or stored.review_id != str(review_id)
                    or stored.decided_by != self._context.permission.actor_id
                ):
                    raise LookupError("REVIEW_NOT_FOUND")
                decision = ReviewDecisionDTO.model_validate(stored.decision_payload_json)
                return decision, self._view(session, values)
            if task.record_version != request.expected_record_version:
                raise ReviewConflict("REVIEW_VERSION_CONFLICT")
            if task.status != "PENDING":
                raise ReviewConflict("REVIEW_ALREADY_RESOLVED")
            view = self._view(session, values)
            if request.decision.value not in view.allowed_actions:
                raise ReviewConflict("ACTION_NOT_ALLOWED")
            decision = ReviewDecisionDTO(
                review_id=review_id,
                decision=request.decision,
                comment=request.comment,
                decided_by=self._context.permission.actor_id,
                provenance=ProvenanceDTO(
                    source_type="USER_INPUT",
                    source_ref=str(review_id),
                    source_version=str(task.record_version),
                    actor_ref=self._context.permission.actor_id,
                    generated_by="HumanReviewService",
                    request_id=request.idempotency_key,
                ),
            )
            session.add(
                b.ReviewDecisionEntity(
                    decision_id=str(decision.decision_id),
                    tenant_id=self.tenant_id,
                    review_id=str(review_id),
                    decision_code=decision.decision.value,
                    comment=decision.comment,
                    decided_by=decision.decided_by,
                    decided_at=decision.decided_at,
                    decision_payload_json=decision.model_dump(mode="json"),
                )
            )
            task.decision_json = decision.model_dump(mode="json")
            task.status = {
                "APPROVE": "APPROVED",
                "REJECT": "REJECTED",
                "REQUEST_CHANGES": "PENDING",
            }[decision.decision.value]
            task.record_version += 1
            task.updated_at = datetime.now(UTC)
            task.resolved_at = None if task.status == "PENDING" else task.updated_at
            key.response_ref = str(decision.decision_id)
            session.add(
                b.AuditEventEntity(
                    audit_event_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    workflow_run_id=run.workflow_run_id,
                    analysis_snapshot_id=snapshot.analysis_snapshot_id,
                    event_type="REVIEW_DECISION_RECORDED",
                    provenance_json={
                        "review_id": str(review_id),
                        "decision_id": str(decision.decision_id),
                        "actor_id": decision.decided_by,
                        "decision": decision.decision.value,
                        "record_version": task.record_version,
                    },
                )
            )
            session.flush()
            return decision, self._view(session, values)

    def correct(self, review_id, request):
        from sqlalchemy.exc import DBAPIError

        try:
            return self._correct(review_id, request)
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "40001":
                raise ReviewConflict("REVIEW_VERSION_CONFLICT") from exc
            raise

    def _correct(self, review_id, request):
        from contextlib import contextmanager
        from functools import partial
        from uuid import uuid5

        from sqlalchemy.orm import Session

        from crossborder_compliance.application.intake_services import (
            ConfirmProjectIntake,
            IntakeFacts,
            ProjectIntakeService,
        )
        from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
        from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
            PostgresProjectRepository,
        )

        with self._sessions() as session, session.begin():
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            values = self._scope(session, review_id, write=True, lock=True)
            task, run, snapshot, version, project = values
            key, duplicate = self._request_key(session, review_id, request, "correction")
            if duplicate:
                row = session.get(ReviewCorrectionEntity, key.response_ref)
                if (
                    not row
                    or row.tenant_id != self.tenant_id
                    or row.source_review_id != str(review_id)
                    or row.submitted_by != self._context.permission.actor_id
                ):
                    raise LookupError("REVIEW_NOT_FOUND")
                return self._lineage(row)
            if task.record_version != request.expected_record_version:
                raise ReviewConflict("REVIEW_VERSION_CONFLICT")
            view = self._view(session, values)
            correction = request.correction
            needed = (
                "ADD_INFORMATION"
                if correction.correction_type == "CLARIFY_INTAKE"
                else "SUBMIT_CORRECTION"
            )
            if (
                task.status != "PENDING"
                or needed not in view.allowed_actions
                or view.resolution_mode != "SUCCESSOR_SNAPSHOT"
            ):
                raise ReviewConflict("ACTION_NOT_ALLOWED")
            if (
                correction.target_object_type != task.object_type
                or str(correction.target_object_id) != task.object_id
            ):
                raise ReviewConflict("CORRECTION_OUTSIDE_REVIEW_TARGET")
            if correction.correction_type == "SELECT_BUSINESS_FACT":
                if str(correction.selected_fact_id) not in {
                    str(c.object_id) for c in view.choices if c.object_type == "BUSINESS_FACT"
                }:
                    raise ReviewConflict("CORRECTION_OUTSIDE_REVIEW_TARGET")
            elif correction.correction_type == "SELECT_PRODUCT_SCOPE":
                choices = {
                    str(c.object_id) for c in view.choices if c.object_type == "PRODUCT_CONTEXT"
                }
                if not set(map(str, correction.selected_product_ids)) <= choices:
                    raise ReviewConflict("CORRECTION_OUTSIDE_REVIEW_TARGET")
            connection = session.connection()

            @contextmanager
            def joined():
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as child:
                    yield child

            owner = PostgresProjectRepository(joined, self._context)
            facts = (
                correction.facts
                if correction.correction_type == "CLARIFY_INTAKE"
                else IntakeFacts.model_validate(
                    {k: v for k, v in version.intake_json.items() if k in IntakeFacts.model_fields}
                )
            )
            if correction.correction_type == "SELECT_PRODUCT_SCOPE":
                from crossborder_compliance.infrastructure.persistence.metadata_models import (
                    MetadataDefinitionEntity,
                )

                rows = session.scalars(
                    select(MetadataDefinitionEntity).where(
                        MetadataDefinitionEntity.tenant_id == self.tenant_id,
                        MetadataDefinitionEntity.definition_id.in_(
                            list(map(str, correction.selected_product_ids))
                        ),
                    )
                ).all()
                if len(rows) != len(set(correction.selected_product_ids)) or any(
                    r.kind not in {"PRODUCT", "PRODUCT_DOMAIN"} for r in rows
                ):
                    raise ReviewConflict("CAPABILITY_NOT_CONFIGURED")
                facts = facts.model_copy(
                    update={
                        "selected_products": [r.definition_id for r in rows if r.kind == "PRODUCT"],
                        "selected_product_domains": [
                            r.definition_id for r in rows if r.kind == "PRODUCT_DOMAIN"
                        ],
                    }
                )
            if (
                correction.correction_type == "CLARIFY_INTAKE"
                and facts.uploaded_documents != version.intake_json.get("uploaded_documents", [])
            ):
                raise ReviewConflict("CORRECTION_OUTSIDE_REVIEW_TARGET")
            successor = owner.successor_from_review(
                UUID(project.project_id),
                UUID(version.project_version_id),
                UUID(snapshot.analysis_snapshot_id),
                facts,
            )
            successor_snapshot_id = uuid5(successor.project_version_id, "analysis-snapshot")
            successor_run_id = uuid5(successor_snapshot_id, "canonical-workflow")
            row = ReviewCorrectionEntity(
                correction_id=str(uuid4()),
                tenant_id=self.tenant_id,
                source_review_id=str(review_id),
                source_workflow_run_id=run.workflow_run_id,
                source_snapshot_id=snapshot.analysis_snapshot_id,
                source_conflict_id=task.object_id
                if task.object_type == "CONTEXT_CONFLICT"
                else None,
                successor_project_version_id=str(successor.project_version_id),
                successor_snapshot_id=str(successor_snapshot_id),
                successor_workflow_run_id=str(successor_run_id),
                correction_type=correction.correction_type,
                selected_fact_id=str(correction.selected_fact_id)
                if correction.correction_type == "SELECT_BUSINESS_FACT"
                else None,
                selected_product_ids_json=list(map(str, correction.selected_product_ids))
                if correction.correction_type == "SELECT_PRODUCT_SCOPE"
                else [],
                submitted_by=self._context.permission.actor_id,
                comment=request.comment,
            )
            session.add(row)
            session.flush()
            prepared = partial(
                prepare_snapshot, source_snapshot_id=UUID(snapshot.analysis_snapshot_id)
            )
            ProjectIntakeService(owner, prepared).confirm(
                UUID(project.project_id), ConfirmProjectIntake(expected_version=successor.version)
            )
            task.record_version += 1
            # Source task/checkpoint/result keep their original semantic state.
            # The immutable lineage provides the SUPERSEDED projection instead.
            key.response_ref = row.correction_id
            session.add(
                b.AuditEventEntity(
                    audit_event_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    workflow_run_id=run.workflow_run_id,
                    analysis_snapshot_id=snapshot.analysis_snapshot_id,
                    event_type="REVIEW_SUCCESSOR_CREATED",
                    provenance_json={
                        "review_id": str(review_id),
                        "correction_id": row.correction_id,
                        "successor_snapshot_id": str(successor_snapshot_id),
                        "successor_workflow_run_id": str(successor_run_id),
                        "actor_id": row.submitted_by,
                        "rerun_from_stage": "requirement",
                    },
                )
            )
            return self._lineage(row)
