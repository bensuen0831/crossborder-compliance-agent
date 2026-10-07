"""Prepare one confirmed intake's snapshot using existing owning services."""

from dataclasses import replace
from uuid import UUID, uuid5

from sqlalchemy import select

from crossborder_compliance.application.context_services import ContextResolutionService
from crossborder_compliance.application.intake_services import ProjectIntakeService
from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
from crossborder_compliance.application.workflow_formal import FormalWorkflowPlan
from crossborder_compliance.infrastructure.persistence import (
    metadata_models as m,
)
from crossborder_compliance.infrastructure.persistence import (
    models as b,
)
from crossborder_compliance.infrastructure.persistence import (
    retrieval_models as g,
)
from crossborder_compliance.infrastructure.persistence.context_repositories import (
    PostgresContextResolutionRepository,
)
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
)
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)
from crossborder_compliance.workflows.canonical import GRAPH_VERSION, STATE_VERSION
from crossborder_compliance.workflows.langgraph_adapter import installed_version


def project_context(sessions, context, project_id):
    """Revalidate existing creator provenance and current intake access on use.

    Only an exact project grant is derived; all stage/action permissions remain
    the trusted host's current permissions, without creating a new RBAC system.
    """
    repo = PostgresProjectRepository(sessions, context)
    view = repo.read_intake(project_id)
    if (
        view.intake.provenance.source_type != "USER_INPUT"
        or view.intake.provenance.generated_by != "CreateProjectFromIntake"
    ):
        raise LookupError("production intake not found")
    return replace(
        context,
        permission=replace(
            context.permission,
            scopes=context.permission.scopes
            | {f"project:{project_id}:comply", f"project:{project_id}:classify"},
        ),
    )


def prepare_snapshot(sessions, context, intake, snapshot_id, run_id):
    project_id = intake.project_id
    context = project_context(sessions, context, project_id)
    from crossborder_compliance.infrastructure.persistence.structured_intake import (
        validate_references,
    )

    validate_references(sessions, context, intake, snapshot_id)
    repo = PostgresContextResolutionRepository(sessions, context)
    locations = {
        kind: values
        for kind, values in (
            ("SOURCE", intake.source_locations),
            ("DESTINATION", intake.destination_locations),
            ("PROCESSING", intake.processing_locations),
            ("STORAGE", intake.storage_locations),
        )
    }
    with sessions() as s:
        intake_version_id = UUID(
            s.get(b.AnalysisSnapshotEntity, str(snapshot_id)).project_version_id
        )
    result = ContextResolutionService(repo).run(
        project_id,
        confirmed_intake_version_id=intake_version_id,
        structured_snapshot_id=snapshot_id,
        selected_product_scope=tuple(
            UUID(x) for x in intake.selected_product_domains + intake.selected_products
        ),
        selected_scenarios=(UUID(intake.business_scenario),),
        jurisdictions=tuple(
            dict(
                jurisdiction_id=x,
                input_value=f"{kind}:{x}",
                context_type=kind,
                location_precision="EXACT_CANONICAL",
                source="USER_INPUT",
            )
            for kind, values in locations.items()
            for x in dict.fromkeys(values)
        ),
    )
    context_run = UUID(result["context_resolution_run_id"])
    repo.pin_snapshot_context(
        analysis_snapshot_id=snapshot_id,
        project_id=project_id,
        context_resolution_run_id=context_run,
    )
    # Initialize the owning H rule/config pins without classifying nonexistent
    # data. The unique eligible governed scheme is frozen for this snapshot.
    from crossborder_compliance.infrastructure.persistence.classification_repository import (
        PostgresFormalClassificationRepository,
    )

    with sessions() as s:
        schemes = s.scalars(
            select(m.ClassificationSchemeVersionEntity).where(
                m.ClassificationSchemeVersionEntity.tenant_id == str(context.tenant_id),
                m.ClassificationSchemeVersionEntity.lifecycle_status == "ACTIVE",
            )
        ).all()
        if len(schemes) != 1:
            raise ValueError("M2A_CLASSIFICATION_CONFIGURATION_GAP")
        scheme_version_id = UUID(schemes[0].scheme_version_id)
    PostgresFormalClassificationRepository(sessions, context).pin_configuration(
        project_id, snapshot_id, scheme_version_id
    )
    retrieval = PostgresRetrievalRepository(sessions, context)
    KnowledgeScopeResolver(retrieval, context).resolve(
        str(project_id), snapshot_id=str(snapshot_id)
    )
    # No arbitrary latest/default policy: require one authorized active governed
    # retrieval policy; the existing owner validates and pins its full closure.
    with sessions() as s:
        model = g.POLICY_MODELS["retrieval"]
        policies = s.scalars(
            select(model).where(
                model.tenant_id == str(context.tenant_id), model.lifecycle == "ACTIVE"
            )
        ).all()
        if len(policies) != 1:
            raise ValueError("M2A_RETRIEVAL_POLICY_CONFIGURATION_GAP")
        policy_id = policies[0].policy_id
    policy = retrieval.resolve_policy("retrieval", policy_id, str(snapshot_id))
    # The owner freezes required policy dependencies rather than browser choices.
    for kind, field in (
        ("sufficiency", "sufficiency_policy_id"),
        ("trusted_source", "trusted_source_policy_id"),
    ):
        if policy.get(field):
            retrieval.resolve_policy(kind, str(policy[field]), str(snapshot_id))
    country = PostgresCountryComplianceRepository(sessions, context)
    bindings = []
    jurisdictions = sorted({x for values in locations.values() for x in dict.fromkeys(values)})
    for jurisdiction in jurisdictions:
        country.initialize(project_id, snapshot_id, UUID(jurisdiction))
    country.initialize_decisions(project_id, snapshot_id)
    with sessions() as s, s.begin():
        pins = country.pins(s, snapshot_id)
        for pin in pins:
            if pin.pin_type == "PHASE1I_APPLICABILITY_CONFIG":
                version = s.get(m.MetadataVersionEntity, pin.version_id)
                jurisdiction = version.payload_json["jurisdiction_id"]
                if jurisdiction in jurisdictions:
                    bindings.append(dict(jurisdiction_id=jurisdiction, config_id=pin.object_id))
        if not bindings:
            raise ValueError("M2A_APPLICABILITY_CONFIGURATION_GAP")
        plan = FormalWorkflowPlan(
            tenant_id=context.tenant_id,
            project_id=project_id,
            analysis_snapshot_id=snapshot_id,
            request_context_ref=uuid5(snapshot_id, "request-context"),
            context_resolution_run_id=context_run,
            mode="SCENARIO_LEVEL",
            subject_type="SCENARIO",
            subject_id=UUID(intake.business_scenario),
            applicability=bindings,
            retrieval_query=dict(
                project_id=str(project_id),
                analysis_snapshot_id=str(snapshot_id),
                policy_id=policy_id,
                subject_type="PROJECT",
                subject_id=str(project_id),
                query_text=intake.business_purpose[:512],
                idempotency_key="stage-owned",
            ),
        )
        snapshot = s.get(b.AnalysisSnapshotEntity, str(snapshot_id))
        snapshot.provenance_json = {
            **snapshot.provenance_json,
            "formal_workflow_plan": plan.model_dump(mode="json"),
        }
        s.add(
            b.WorkflowRunEntity(
                workflow_run_id=str(run_id),
                thread_id=str(run_id),
                tenant_id=str(context.tenant_id),
                analysis_snapshot_id=str(snapshot_id),
                status="RUNNING",
                graph_definition_version=GRAPH_VERSION,
                state_schema_version=STATE_VERSION,
                langgraph_runtime_version=installed_version("langgraph"),
                checkpointer_version=installed_version("langgraph-checkpoint-postgres"),
            )
        )


def intake_service(sessions, context):
    return ProjectIntakeService(PostgresProjectRepository(sessions, context), prepare_snapshot)


def intake_workflow_host(sessions, context, project_id, snapshot_id):
    context = project_context(sessions, context, project_id)
    view = PostgresProjectRepository(sessions, context).read_intake(project_id)
    if view.status != "CONFIRMED" or view.analysis_snapshot_id != snapshot_id:
        raise LookupError("confirmed intake snapshot not found")
    from crossborder_compliance.infrastructure.persistence.structured_intake import authorize_pins

    authorize_pins(sessions, context, snapshot_id)
    with sessions() as s:
        snapshot = s.scalar(
            select(b.AnalysisSnapshotEntity).where(
                b.AnalysisSnapshotEntity.tenant_id == str(context.tenant_id),
                b.AnalysisSnapshotEntity.analysis_snapshot_id == str(snapshot_id),
                b.AnalysisSnapshotEntity.status == "ACTIVE",
            )
        )
        if snapshot is None:
            raise LookupError("snapshot not found")
        return UUID(snapshot.provenance_json["workflow_run_id"]), FormalWorkflowPlan.model_validate(
            snapshot.provenance_json["formal_workflow_plan"]
        )
