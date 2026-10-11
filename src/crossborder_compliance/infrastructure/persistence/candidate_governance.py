"""Canonical draft preparation/decision owner over 0019 relational identities."""

import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from crossborder_compliance.application.candidate_governance_services import CandidateDecisionInput
from crossborder_compliance.domain.contracts import ProjectIntakeContext
from crossborder_compliance.infrastructure.persistence import candidate_governance_models as g
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
)
from crossborder_compliance.infrastructure.persistence.project_intake import IntakeConflict


def content_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode()
    ).hexdigest()


@contextmanager
def joined(session):
    with Session(
        bind=session.connection(), join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as child:
        yield child


def input_universe(s, tenant, version):
    ids = list(
        s.scalars(
            select(d.ProjectVersionDocumentLinkEntity.document_version_id).where(
                d.ProjectVersionDocumentLinkEntity.tenant_id == tenant,
                d.ProjectVersionDocumentLinkEntity.project_version_id == version.project_version_id,
            )
        ).all()
    )
    documents = []
    for identity in sorted(ids):
        doc = s.get(b.DocumentVersionEntity, identity)
        owner = s.get(b.DocumentEntity, doc.document_id) if doc else None
        if (
            not doc
            or not owner
            or doc.tenant_id != tenant
            or owner.tenant_id != tenant
            or owner.project_id != version.project_id
        ):
            raise LookupError("document outside draft project")
        documents.append({"document_version_id": identity, "content_hash": doc.content_hash})
    return {
        "project_version_id": version.project_version_id,
        "intake": version.intake_json,
        "documents": documents,
    }


def configuration_universe(s, tenant):
    # Version references only. Secrets and arbitrary provider responses are not
    # copied into preparation/audit. Exact used pins are separate relations.
    metadata = s.execute(
        select(
            m.MetadataDefinitionEntity.definition_id, m.MetadataDefinitionEntity.active_version_id
        ).where(
            m.MetadataDefinitionEntity.tenant_id == tenant,
            m.MetadataDefinitionEntity.kind.in_(
                ("MODEL_USAGE_POLICY", "LLM_INVOCATION_POLICY", "BUSINESS_FACT_TYPE")
            ),
        )
    ).all()
    models = s.execute(
        select(
            m.ModelDefinitionEntity.model_definition_id,
            m.ModelDefinitionEntity.active_deployment_id,
        ).where(m.ModelDefinitionEntity.tenant_id == tenant)
    ).all()
    prompts = s.execute(
        select(
            m.PromptBindingEntity.prompt_binding_id,
            m.PromptBindingEntity.prompt_version_id,
            m.PromptBindingEntity.status,
        ).where(
            m.PromptBindingEntity.tenant_id == tenant,
            m.PromptBindingEntity.binding_type == "LLM_INVOCATION_PURPOSE",
        )
    ).all()
    return {
        "metadata": sorted([list(r) for r in metadata]),
        "models": sorted([list(r) for r in models]),
        "prompts": sorted([list(r) for r in prompts]),
    }


KINDS = {
    "BUSINESS_FACT": (
        d.BusinessFactCandidateEntity,
        "fact_id",
        d.BusinessFactSourceLinkEntity,
        "fact_id",
    ),
    "DATA_ITEM": (
        d.CandidateDataItemEntity,
        "candidate_data_item_id",
        d.CandidateDataItemSourceLinkEntity,
        "candidate_data_item_id",
    ),
    "DATA_FLOW_NODE": (
        d.CandidateDataFlowNodeEntity,
        "candidate_node_id",
        d.CandidateDataFlowNodeSourceLinkEntity,
        "candidate_node_id",
    ),
    "DATA_FLOW_EDGE": (
        d.CandidateDataFlowEdgeEntity,
        "candidate_edge_id",
        d.CandidateDataFlowEdgeSourceLinkEntity,
        "candidate_edge_id",
    ),
}


def candidate_payload(s, tenant, kind, identity):
    if kind not in KINDS:
        raise IntakeConflict("INVALID_CANDIDATE_DECISION")
    model, pk, link, link_pk = KINDS[kind]
    row = s.scalar(
        select(model).where(getattr(model, pk) == str(identity), model.tenant_id == tenant)
    )
    if not row:
        raise IntakeConflict("CANDIDATE_UNIVERSE_CHANGED")
    payload = {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
        if c.name not in {"created_at", "updated_at", "record_version", "status", "tenant_id"}
    }
    payload["source_trace_ids"] = sorted(
        s.scalars(
            select(link.source_trace_ref_id).where(
                link.tenant_id == tenant, getattr(link, link_pk) == str(identity)
            )
        ).all()
    )
    return payload


def candidate_universe(s, tenant, parse_ids):
    result = []
    for kind, (model, pk, _, _) in KINDS.items():
        rows = s.scalars(
            select(model).where(model.tenant_id == tenant, model.parse_run_id.in_(parse_ids))
        ).all()
        for row in rows:
            payload = candidate_payload(s, tenant, kind, getattr(row, pk))
            detail = s.get(d.DocumentParseRunDetailEntity, row.parse_run_id)
            semantic = bool(detail and detail.provenance_json.get("semantic_invocation"))
            origin = (
                "LLM_STRUCTURED_OUTPUT"
                if (semantic or getattr(row, "extraction_method", None) == "LLM_STRUCTURED_OUTPUT")
                else "NATIVE_DETERMINISTIC"
            )
            provenance = (
                detail.provenance_json.get("semantic_candidates", {}).get(getattr(row, pk), {})
                if detail
                else {}
            )
            if origin == "LLM_STRUCTURED_OUTPUT" and not provenance:
                raise IntakeConflict("CANDIDATE_LLM_PROVENANCE_REQUIRED")
            result.append(
                {
                    "candidate_type": kind,
                    "candidate_id": getattr(row, pk),
                    "candidate_origin": origin,
                    "candidate_digest": content_digest(payload),
                    "llm_request_id": provenance.get("request_id"),
                    "llm_invocation_group_id": provenance.get("invocation_group_id"),
                }
            )
    return sorted(result, key=lambda r: (r["candidate_type"], r["candidate_id"]))


class PostgresCandidateGovernance:
    def __init__(self, sessions, context, **dependencies):
        self.sessions, self.context, self.dependencies = sessions, context, dependencies
        self.project = PostgresProjectRepository(sessions, context)
        self.tenant = str(context.tenant_id)

    def _draft(self, s, project_id, expected_version=None):
        self.project._intake_permission("update")
        project = self.project._intake_project(s, project_id, True)
        version = self.project._intake_current(s, project)
        if version.status != "DRAFT":
            raise IntakeConflict("CANDIDATE_PREPARATION_REQUIRES_DRAFT")
        if expected_version is not None and version.version_no != expected_version:
            raise IntakeConflict("STALE_INTAKE_VERSION")
        return project, version

    def _preparation(self, s, project_id, identity):
        row = s.scalar(
            select(g.CandidatePreparationEntity).where(
                g.CandidatePreparationEntity.candidate_preparation_id == str(identity),
                g.CandidatePreparationEntity.tenant_id == self.tenant,
                g.CandidatePreparationEntity.project_id == str(project_id),
            )
        )
        if not row:
            raise LookupError("candidate preparation not found")
        return row

    def prepare(self, project_id, request):
        from crossborder_compliance.infrastructure.intake_composition import project_context
        from crossborder_compliance.infrastructure.llm_document_inputs import (
            prepare_document_candidates,
        )
        from crossborder_compliance.infrastructure.llm_snapshot_pins import freeze_llm_configuration

        context = project_context(self.sessions, self.context, project_id)
        self.project._intake_permission("update")
        with self.sessions() as s, s.begin():
            receipt, duplicate = self.project._intake_key(
                s,
                f"candidate-prepare:{project_id}",
                request.idempotency_key,
                request.model_dump(mode="json"),
            )
            _, version = self._draft(s, project_id, request.expected_version)
            if duplicate:
                identity = UUID(receipt.response_ref)
            else:
                universe = content_digest(input_universe(s, self.tenant, version))
                config = content_digest(configuration_universe(s, self.tenant))
                prior = s.scalar(
                    select(g.CandidatePreparationEntity).where(
                        g.CandidatePreparationEntity.tenant_id == self.tenant,
                        g.CandidatePreparationEntity.project_version_id
                        == version.project_version_id,
                        g.CandidatePreparationEntity.input_universe_digest == universe,
                        g.CandidatePreparationEntity.configuration_digest == config,
                        g.CandidatePreparationEntity.status.in_(["PREPARING", "COMPLETED"]),
                    )
                )
                if prior:
                    identity = UUID(prior.candidate_preparation_id)
                    receipt.response_ref = str(identity)
                    duplicate = True
                else:
                    identity = uuid4()
                    row = g.CandidatePreparationEntity(
                        candidate_preparation_id=str(identity),
                        tenant_id=self.tenant,
                        project_id=str(project_id),
                        project_version_id=version.project_version_id,
                        analysis_as_of_date=ProjectIntakeContext.model_validate(
                            version.intake_json
                        ).analysis_as_of_date,
                        input_universe_digest=universe,
                        configuration_digest=config,
                        created_by=self.context.permission.actor_id,
                        idempotency_key=request.idempotency_key,
                        request_digest=content_digest(request.model_dump(mode="json")),
                    )
                    s.add(row)
                    s.flush()
                    receipt.response_ref = str(identity)
            intake = ProjectIntakeContext.model_validate(version.intake_json)
        if duplicate:
            return self.preview(project_id, identity)
        try:
            ensure_native_parse_runs(
                self.sessions, context, intake, identity, self.dependencies.get("storage")
            )
            freeze_llm_configuration(
                self.sessions, context, intake, None, candidate_preparation_id=identity
            )
            prepare_document_candidates(
                self.sessions,
                context,
                intake,
                candidate_preparation_id=identity,
                **self.dependencies,
            )
            with self.sessions() as s, s.begin():
                _, version = self._draft(s, project_id, request.expected_version)
                row = self._preparation(s, project_id, identity)
                if (
                    row.project_version_id != version.project_version_id
                    or content_digest(input_universe(s, self.tenant, version))
                    != row.input_universe_digest
                    or content_digest(configuration_universe(s, self.tenant))
                    != row.configuration_digest
                ):
                    raise IntakeConflict("CANDIDATE_PREPARATION_STALE")
                ids = [
                    x["document_version_id"]
                    for x in input_universe(s, self.tenant, version)["documents"]
                ]
                for doc_id in ids:
                    pin = s.scalar(
                        select(g.CandidatePreparationDocumentPinEntity).where(
                            g.CandidatePreparationDocumentPinEntity.tenant_id == self.tenant,
                            g.CandidatePreparationDocumentPinEntity.candidate_preparation_id
                            == str(identity),
                            g.CandidatePreparationDocumentPinEntity.document_version_id == doc_id,
                        )
                    )
                    run = s.scalar(
                        select(d.DocumentParseRunDetailEntity)
                        .where(
                            d.DocumentParseRunDetailEntity.tenant_id == self.tenant,
                            d.DocumentParseRunDetailEntity.document_version_id == doc_id,
                        )
                        .order_by(d.DocumentParseRunDetailEntity.parse_run_version.desc())
                    )
                    base = s.get(b.DocumentParseRunEntity, run.parse_run_id) if run else None
                    quality = (
                        s.scalar(
                            select(d.DocumentParseQualityEntity).where(
                                d.DocumentParseQualityEntity.tenant_id == self.tenant,
                                d.DocumentParseQualityEntity.parse_run_id == run.parse_run_id,
                            )
                        )
                        if run
                        else None
                    )
                    if (
                        not base
                        or base.status != "COMPLETED"
                        or not quality
                        or quality.quality_status not in {"PASS", "WARNING"}
                    ):
                        raise IntakeConflict("CANDIDATE_PREPARATION_PARSE_NOT_READY")
                    if pin and pin.parse_run_id != run.parse_run_id:
                        raise IntakeConflict("CANDIDATE_PREPARATION_STALE")
                    if not pin:
                        s.add(
                            g.CandidatePreparationDocumentPinEntity(
                                preparation_document_pin_id=str(uuid4()),
                                tenant_id=self.tenant,
                                candidate_preparation_id=str(identity),
                                document_version_id=doc_id,
                                parse_run_id=run.parse_run_id,
                            )
                        )
                s.flush()
                parse_ids = list(
                    s.scalars(
                        select(g.CandidatePreparationDocumentPinEntity.parse_run_id).where(
                            g.CandidatePreparationDocumentPinEntity.tenant_id == self.tenant,
                            g.CandidatePreparationDocumentPinEntity.candidate_preparation_id
                            == str(identity),
                        )
                    )
                )
                candidates = candidate_universe(s, self.tenant, parse_ids)
                for candidate in candidates:
                    s.add(
                        g.CandidatePreparationCandidateEntity(
                            preparation_candidate_id=str(uuid4()),
                            tenant_id=self.tenant,
                            candidate_preparation_id=str(identity),
                            **candidate,
                        )
                    )
                s.flush()
                row.candidate_universe_digest = content_digest(candidates)
                row.completed_at = datetime.now(UTC)
                row.record_version += 1
                row.status = "COMPLETED"
        except Exception:
            with self.sessions() as s, s.begin():
                row = self._preparation(s, project_id, identity)
                if row.status == "PREPARING":
                    row.status = "FAILED"
                    row.completed_at = datetime.now(UTC)
                    row.record_version += 1
            raise
        return self.preview(project_id, identity)

    def preview(self, project_id, preparation_id=None):
        self.project.read_intake(project_id)
        with self.sessions() as s:
            project = self.project._intake_project(s, project_id)
            version = self.project._intake_current(s, project)
            if preparation_id is None:
                preparation_id = s.scalar(
                    select(g.CandidatePreparationEntity.candidate_preparation_id)
                    .where(
                        g.CandidatePreparationEntity.tenant_id == self.tenant,
                        g.CandidatePreparationEntity.project_id == str(project_id),
                        g.CandidatePreparationEntity.project_version_id
                        == version.project_version_id,
                    )
                    .order_by(g.CandidatePreparationEntity.created_at.desc())
                    .limit(1)
                )
            if preparation_id is None:
                return {
                    "status": "NOT_PREPARED",
                    "candidates": [],
                    "candidate_preparation_id": None,
                    "candidate_universe_digest": None,
                }
            row = self._preparation(s, project_id, preparation_id)
            decision_set = s.scalar(
                select(g.CandidateDecisionSetEntity)
                .where(
                    g.CandidateDecisionSetEntity.tenant_id == self.tenant,
                    g.CandidateDecisionSetEntity.candidate_preparation_id
                    == row.candidate_preparation_id,
                    g.CandidateDecisionSetEntity.sealed.is_(True),
                )
                .order_by(g.CandidateDecisionSetEntity.submitted_at.desc())
                .limit(1)
            )
            decisions = (
                {
                    r.preparation_candidate_id: r
                    for r in s.scalars(
                        select(g.CandidateDecisionEntity).where(
                            g.CandidateDecisionEntity.candidate_decision_set_id
                            == decision_set.candidate_decision_set_id
                        )
                    )
                }
                if decision_set
                else {}
            )
            items = s.scalars(
                select(g.CandidatePreparationCandidateEntity)
                .where(
                    g.CandidatePreparationCandidateEntity.tenant_id == self.tenant,
                    g.CandidatePreparationCandidateEntity.candidate_preparation_id
                    == row.candidate_preparation_id,
                )
                .order_by(
                    g.CandidatePreparationCandidateEntity.candidate_type,
                    g.CandidatePreparationCandidateEntity.candidate_id,
                )
            ).all()
            candidates = []
            for item in items:
                if (
                    not self.context.permission.system
                    and "document:read" not in self.context.permission.scopes
                ):
                    raise PermissionError("document:read required")
                payload = candidate_payload(s, self.tenant, item.candidate_type, item.candidate_id)
                traces = []
                for trace_id in payload["source_trace_ids"]:
                    trace = s.get(d.SourceTraceDetailEntity, trace_id)
                    node = (
                        s.get(d.CanonicalStructureNodeEntity, trace.structure_node_id)
                        if trace
                        else None
                    )
                    if not trace or trace.tenant_id != self.tenant:
                        raise LookupError("candidate source unavailable")
                    traces.append(
                        {
                            "source_trace_ref_id": trace_id,
                            "parse_run_id": trace.parse_run_id,
                            "document_version_id": node.document_version_id if node else None,
                            "section": trace.section_path,
                            "source_excerpt": (node.original_text or node.normalized_text or "")[
                                :600
                            ]
                            if node
                            else "",
                        }
                    )
                candidates.append(
                    {
                        "preparation_candidate_id": item.preparation_candidate_id,
                        "candidate_id": item.candidate_id,
                        "candidate_type": item.candidate_type,
                        "candidate_origin": item.candidate_origin,
                        "candidate_digest": item.candidate_digest,
                        "proposed_payload": {
                            k: v
                            for k, v in payload.items()
                            if k not in {"original_value_json", "source_trace_ids"}
                        },
                        "confidence": payload.get("confidence"),
                        "requires_confirmation": item.candidate_origin == "LLM_STRUCTURED_OUTPUT",
                        "sources": traces,
                    }
                )
                decision = decisions.get(item.preparation_candidate_id)
                candidates[-1].update(
                    decision_status=decision.action if decision else "UNRESOLVED",
                    edited_payload=decision.edited_payload_json if decision else None,
                )
                detail = s.get(d.DocumentParseRunDetailEntity, payload["parse_run_id"])
                candidates[-1]["llm_provenance"] = (
                    detail.provenance_json.get("semantic_candidates", {}).get(item.candidate_id)
                    if detail
                    else None
                )
            return {
                "candidate_preparation_id": row.candidate_preparation_id,
                "project_version_id": row.project_version_id,
                "status": row.status,
                "candidate_universe_digest": row.candidate_universe_digest,
                "stale": row.project_version_id != version.project_version_id,
                "candidates": candidates,
                "candidate_decision_set_id": decision_set.candidate_decision_set_id
                if decision_set
                else None,
            }

    def resolve(self, project_id, request):
        with self.sessions() as s, s.begin():
            receipt, duplicate = self.project._intake_key(
                s,
                f"candidate-decide:{project_id}",
                request.idempotency_key,
                request.model_dump(mode="json"),
            )
            _, version = self._draft(s, project_id, request.expected_version)
            preparation = self._preparation(s, project_id, request.candidate_preparation_id)
            validate_preparation(s, self.tenant, version, preparation)
            if request.candidate_universe_digest != preparation.candidate_universe_digest:
                raise IntakeConflict("CANDIDATE_UNIVERSE_CHANGED")
            if duplicate:
                row = s.get(g.CandidateDecisionSetEntity, receipt.response_ref)
                return decision_receipt(row)
            items = {
                r.preparation_candidate_id: r
                for r in s.scalars(
                    select(g.CandidatePreparationCandidateEntity).where(
                        g.CandidatePreparationCandidateEntity.tenant_id == self.tenant,
                        g.CandidatePreparationCandidateEntity.candidate_preparation_id
                        == preparation.candidate_preparation_id,
                    )
                )
            }
            for decision in request.decisions:
                item = items.get(str(decision.preparation_candidate_id))
                if item is None:
                    raise IntakeConflict("INVALID_CANDIDATE_DECISION")
                validate_edit(item.candidate_type, decision)
            row = g.CandidateDecisionSetEntity(
                candidate_decision_set_id=str(uuid4()),
                tenant_id=self.tenant,
                project_id=str(project_id),
                project_version_id=version.project_version_id,
                candidate_preparation_id=preparation.candidate_preparation_id,
                candidate_universe_digest=preparation.candidate_universe_digest,
                decision_payload_digest=content_digest(
                    sorted(
                        [v.model_dump(mode="json") for v in request.decisions],
                        key=lambda d: d["preparation_candidate_id"],
                    )
                ),
                submitted_by=self.context.permission.actor_id,
                idempotency_key=request.idempotency_key,
                request_digest=content_digest(request.model_dump(mode="json")),
            )
            s.add(row)
            s.flush()
            for decision in request.decisions:
                s.add(
                    g.CandidateDecisionEntity(
                        candidate_decision_id=str(uuid4()),
                        tenant_id=self.tenant,
                        candidate_preparation_id=preparation.candidate_preparation_id,
                        candidate_decision_set_id=row.candidate_decision_set_id,
                        preparation_candidate_id=str(decision.preparation_candidate_id),
                        action=decision.action,
                        edited_payload_json=decision.edited_payload,
                        decision_digest=content_digest(decision.model_dump(mode="json")),
                    )
                )
            s.flush()
            row.sealed = True
            s.flush()
            receipt.response_ref = row.candidate_decision_set_id
            return decision_receipt(row)


def decision_receipt(row):
    return {
        "candidate_decision_set_id": row.candidate_decision_set_id,
        "candidate_preparation_id": row.candidate_preparation_id,
        "submitted_by": row.submitted_by,
        "submitted_at": row.submitted_at,
    }


def ensure_native_parse_runs(sessions, context, intake, preparation_id, storage):
    import os

    from crossborder_compliance.application.document_services import DocumentParseService
    from crossborder_compliance.infrastructure.document_parsers import default_native_parsers
    from crossborder_compliance.infrastructure.document_storage import FileObjectStorageAdapter
    from crossborder_compliance.infrastructure.persistence.document_repositories import (
        PostgresDocumentIntelligenceRepository,
    )

    with sessions() as s:
        prep = s.get(g.CandidatePreparationEntity, str(preparation_id))
        documents = list(
            s.scalars(
                select(d.ProjectVersionDocumentLinkEntity.document_version_id).where(
                    d.ProjectVersionDocumentLinkEntity.tenant_id == str(context.tenant_id),
                    d.ProjectVersionDocumentLinkEntity.project_version_id
                    == prep.project_version_id,
                )
            )
        )
        pending = [
            identity
            for identity in documents
            if s.scalar(
                select(d.DocumentParseRunDetailEntity.parse_run_id)
                .where(
                    d.DocumentParseRunDetailEntity.tenant_id == str(context.tenant_id),
                    d.DocumentParseRunDetailEntity.document_version_id == identity,
                )
                .limit(1)
            )
            is None
        ]
    if not pending:
        return
    storage = storage or (
        FileObjectStorageAdapter(os.environ["DOCUMENT_OBJECT_STORAGE_ROOT"])
        if os.environ.get("DOCUMENT_OBJECT_STORAGE_ROOT")
        else None
    )
    if storage is None:
        raise IntakeConflict("CANDIDATE_PREPARATION_STORAGE_NOT_CONFIGURED")

    class Receipt:
        def enqueue(self, **kwargs):
            return None

    repo = PostgresDocumentIntelligenceRepository(sessions, context)
    service = DocumentParseService(repo, storage, default_native_parsers(), Receipt())
    for identity in pending:
        result = service.request_parse(
            document_version_id=UUID(identity),
            idempotency_key=f"candidate-native:{preparation_id}:{identity}",
            parser_profile_id="native-v1",
        )
        service.process_task(UUID(result["task_id"]))


def validate_edit(kind, decision: CandidateDecisionInput):
    fields = {
        "BUSINESS_FACT": {"normalized_value"},
        "DATA_ITEM": {"raw_name", "normalized_name", "description", "value_type", "unit"},
        "DATA_FLOW_NODE": {
            "name",
            "node_type_candidate",
            "location_candidate",
            "party_candidate",
            "system_candidate",
        },
        "DATA_FLOW_EDGE": {"direction", "transfer_type_candidate"},
    }
    if decision.action == "EDIT" and (
        not decision.edited_payload or not set(decision.edited_payload) <= fields.get(kind, set())
    ):
        raise IntakeConflict("INVALID_CANDIDATE_DECISION")
    if (
        decision.action == "EDIT"
        and kind != "BUSINESS_FACT"
        and any(
            value is not None and (not isinstance(value, str) or len(value) > 4000)
            for value in decision.edited_payload.values()
        )
    ):
        raise IntakeConflict("INVALID_CANDIDATE_DECISION")


def validate_preparation(s, tenant, version, preparation):
    if (
        preparation.project_version_id != version.project_version_id
        or preparation.status != "COMPLETED"
        or preparation.input_universe_digest != content_digest(input_universe(s, tenant, version))
    ):
        raise IntakeConflict("CANDIDATE_PREPARATION_STALE")
    pins = s.scalars(
        select(g.CandidatePreparationDocumentPinEntity).where(
            g.CandidatePreparationDocumentPinEntity.tenant_id == tenant,
            g.CandidatePreparationDocumentPinEntity.candidate_preparation_id
            == preparation.candidate_preparation_id,
        )
    ).all()
    for pin in pins:
        latest = s.scalar(
            select(d.DocumentParseRunDetailEntity)
            .where(
                d.DocumentParseRunDetailEntity.tenant_id == tenant,
                d.DocumentParseRunDetailEntity.document_version_id == pin.document_version_id,
            )
            .order_by(d.DocumentParseRunDetailEntity.parse_run_version.desc())
            .limit(1)
        )
        if not latest or latest.parse_run_id != pin.parse_run_id:
            raise IntakeConflict("CANDIDATE_PREPARATION_STALE")
    try:
        current_digest = content_digest(
            candidate_universe(s, tenant, [p.parse_run_id for p in pins])
        )
    except IntakeConflict as error:
        raise IntakeConflict("CANDIDATE_UNIVERSE_CHANGED") from error
    if current_digest != preparation.candidate_universe_digest:
        raise IntakeConflict("CANDIDATE_UNIVERSE_CHANGED")


def confirmation_authorization(s, context, project_id, version, decision_set_id):
    """Fail closed BEFORE Snapshot creation; caller holds the Project row lock."""
    tenant = str(context.tenant_id)
    decision_set = None
    if decision_set_id is not None:
        decision_set = s.scalar(
            select(g.CandidateDecisionSetEntity).where(
                g.CandidateDecisionSetEntity.candidate_decision_set_id == str(decision_set_id),
                g.CandidateDecisionSetEntity.tenant_id == tenant,
                g.CandidateDecisionSetEntity.project_id == str(project_id),
            )
        )
        if not decision_set or not decision_set.sealed:
            raise IntakeConflict("INVALID_CANDIDATE_DECISION")
        preparation = s.get(g.CandidatePreparationEntity, decision_set.candidate_preparation_id)
    else:
        preparation = s.scalar(
            select(g.CandidatePreparationEntity)
            .where(
                g.CandidatePreparationEntity.tenant_id == tenant,
                g.CandidatePreparationEntity.project_version_id == version.project_version_id,
                g.CandidatePreparationEntity.status == "COMPLETED",
            )
            .order_by(g.CandidatePreparationEntity.created_at.desc())
            .limit(1)
        )
    if preparation is None:
        if needs_candidate_preparation(s, context, version):
            raise IntakeConflict("CANDIDATE_PREPARATION_REQUIRED")
        return {}
    validate_preparation(s, tenant, version, preparation)
    members = s.scalars(
        select(g.CandidatePreparationCandidateEntity).where(
            g.CandidatePreparationCandidateEntity.tenant_id == tenant,
            g.CandidatePreparationCandidateEntity.candidate_preparation_id
            == preparation.candidate_preparation_id,
        )
    ).all()
    required = {
        m.preparation_candidate_id for m in members if m.candidate_origin == "LLM_STRUCTURED_OUTPUT"
    }
    decisions = []
    if decision_set:
        if (
            decision_set.project_version_id != version.project_version_id
            or decision_set.candidate_universe_digest != preparation.candidate_universe_digest
        ):
            raise IntakeConflict("CANDIDATE_PREPARATION_STALE")
        decisions = s.scalars(
            select(g.CandidateDecisionEntity).where(
                g.CandidateDecisionEntity.tenant_id == tenant,
                g.CandidateDecisionEntity.candidate_decision_set_id
                == decision_set.candidate_decision_set_id,
            )
        ).all()
        payload = [
            {
                "preparation_candidate_id": r.preparation_candidate_id,
                "action": r.action,
                "edited_payload": r.edited_payload_json,
            }
            for r in decisions
        ]
        if (
            content_digest(sorted(payload, key=lambda r: r["preparation_candidate_id"]))
            != decision_set.decision_payload_digest
        ):
            raise IntakeConflict("INVALID_CANDIDATE_DECISION")
    if not required <= {d.preparation_candidate_id for d in decisions}:
        raise IntakeConflict("CANDIDATE_CONFIRMATION_REQUIRED")
    revalidate_configuration(lambda: joined(s), context, project_id, preparation)
    return {
        "candidate_preparation_id": preparation.candidate_preparation_id,
        "candidate_decision_set_id": decision_set.candidate_decision_set_id
        if decision_set
        else None,
        "candidate_universe_digest": preparation.candidate_universe_digest,
    }


def needs_candidate_preparation(s, context, version):
    tenant = str(context.tenant_id)
    docs = input_universe(s, tenant, version)["documents"]
    for doc in docs:
        run = s.scalar(
            select(d.DocumentParseRunDetailEntity)
            .where(
                d.DocumentParseRunDetailEntity.tenant_id == tenant,
                d.DocumentParseRunDetailEntity.document_version_id == doc["document_version_id"],
            )
            .order_by(d.DocumentParseRunDetailEntity.parse_run_version.desc())
            .limit(1)
        )
        if run:
            candidates = candidate_universe(s, tenant, [run.parse_run_id])
            if any(x["candidate_origin"] == "LLM_STRUCTURED_OUTPUT" for x in candidates):
                return True
            if candidates:
                continue  # Existing deterministic native resolution remains authoritative.
        from crossborder_compliance.domain.llm_gateway import GatewayDenied
        from crossborder_compliance.infrastructure.llm_gateway_configuration import (
            PostgresLLMConfiguration,
        )
        from crossborder_compliance.infrastructure.llm_snapshot_pins import _policy

        try:
            _, policy = _policy(
                PostgresLLMConfiguration(lambda: joined(s), context, draft_catalog=True),
                ProjectIntakeContext.model_validate(version.intake_json).analysis_as_of_date,
            )
        except GatewayDenied:
            continue
        preference = ProjectIntakeContext.model_validate(version.intake_json).ai_model_preference
        if "DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED" in policy.allowed_triggers.get(
            preference.usage_mode, ()
        ):
            return True
    return False


def revalidate_configuration(sessions, context, project_id, preparation):
    from crossborder_compliance.application.llm_model_catalog import (
        PreparationModelConfigurationQuery,
    )
    from crossborder_compliance.domain.llm_gateway import (
        DraftPreparationInvocationScope,
        GatewayDenied,
    )
    from crossborder_compliance.infrastructure.intake_composition import project_context
    from crossborder_compliance.infrastructure.llm_gateway_configuration import (
        PostgresLLMConfiguration,
    )
    from crossborder_compliance.infrastructure.llm_invocation_governance import (
        PostgresLLMInvocationGovernance,
    )

    context = project_context(sessions, context, project_id)
    config = PostgresLLMConfiguration(
        sessions,
        context,
        frozen_snapshot=True,
        candidate_preparation_id=UUID(preparation.candidate_preparation_id),
    )
    request = PreparationModelConfigurationQuery(
        project_id=project_id,
        invocation_scope=DraftPreparationInvocationScope(
            candidate_preparation_id=preparation.candidate_preparation_id,
            project_id=project_id,
            project_version_id=preparation.project_version_id,
        ),
    )
    selection = config._saved(request, "LLM_SELECTION")
    if selection and selection[0]["logical_key"] == "UNAVAILABLE":
        return
    try:
        config.authorize(request)
        PostgresLLMInvocationGovernance(config).load(request)
        config.policies(request)
        models = config.models(request)
        expected = config._saved(request, "LLM_MODEL")
        if {str(r.deployment_id) for r in models} != {p["version_id"] for p in expected}:
            raise GatewayDenied("MODEL_CONFIGURATION_REVOKED")
        with sessions() as s:
            for pin in config.list_pins(request):
                if pin["pin_type"] == "LLM_PROMPT":
                    prompt = s.get(m.PromptVersionEntity, pin["version_id"])
                    definition = s.get(m.PromptDefinitionEntity, pin["object_id"])
                    if (
                        not prompt
                        or not definition
                        or prompt.tenant_id != config.tenant
                        or definition.tenant_id != config.tenant
                        or prompt.status != "ACTIVE"
                        or definition.status != "ACTIVE"
                        or prompt.lifecycle_status not in {"ACTIVE", "SUPERSEDED"}
                        or not config._effective(prompt, preparation.analysis_as_of_date)
                    ):
                        raise GatewayDenied("PROMPT_CONFIGURATION_REVOKED")
                elif pin["pin_type"] == "LLM_FACT_TYPE":
                    metadata = s.get(m.MetadataVersionEntity, pin["version_id"])
                    definition = s.get(m.MetadataDefinitionEntity, pin["object_id"])
                    if (
                        not metadata
                        or not definition
                        or definition.tenant_id != config.tenant
                        or metadata.tenant_id != config.tenant
                        or definition.status != "ACTIVE"
                        or metadata.status != "ACTIVE"
                        or metadata.lifecycle_status not in {"ACTIVE", "SUPERSEDED"}
                        or not config._effective(metadata, preparation.analysis_as_of_date)
                        or not set(metadata.payload_json.get("permission_scopes", ()))
                        <= context.permission.scopes
                    ):
                        raise GatewayDenied("FACT_TYPE_CONFIGURATION_REVOKED")
    except GatewayDenied as error:
        raise IntakeConflict("CANDIDATE_PREPARATION_REVALIDATION_FAILED") from error


def transfer_preparation_pins(sessions, context, snapshot_id):
    from crossborder_compliance.infrastructure.persistence.candidate_preparation_pins import (
        PostgresCandidatePreparationPins,
    )
    from crossborder_compliance.infrastructure.persistence.document_repositories import (
        PostgresDocumentIntelligenceRepository,
    )
    from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
        PostgresSnapshotRegistryPinRepository,
    )

    tenant = str(context.tenant_id)
    with sessions() as s:
        snapshot = s.get(b.AnalysisSnapshotEntity, str(snapshot_id))
        preparation_id = snapshot.provenance_json.get("candidate_preparation_id")
        if not preparation_id:
            return False
        pins = s.scalars(
            select(g.CandidatePreparationDocumentPinEntity).where(
                g.CandidatePreparationDocumentPinEntity.tenant_id == tenant,
                g.CandidatePreparationDocumentPinEntity.candidate_preparation_id == preparation_id,
            )
        ).all()
        docs = [(UUID(p.document_version_id), UUID(p.parse_run_id)) for p in pins]
    registry = PostgresSnapshotRegistryPinRepository(sessions, context)
    for pin in PostgresCandidatePreparationPins(sessions, context).list_pins(preparation_id):
        registry.add_pin(
            analysis_snapshot_id=snapshot_id,
            **{**pin, "object_id": UUID(pin["object_id"]), "version_id": UUID(pin["version_id"])},
        )
    documents = PostgresDocumentIntelligenceRepository(sessions, context)
    for doc, run in docs:
        documents.pin_parse_run(
            analysis_snapshot_id=snapshot_id, document_version_id=doc, parse_run_id=run
        )
    with sessions() as s, s.begin():
        snapshot = s.get(b.AnalysisSnapshotEntity, str(snapshot_id))
        snapshot.provenance_json = {
            **snapshot.provenance_json,
            "document_input_universe_pinned": True,
        }
    return True
