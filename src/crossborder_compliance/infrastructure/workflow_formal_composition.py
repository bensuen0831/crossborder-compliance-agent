"""Dependency assembly for the existing canonical runtime, never another graph."""

from crossborder_compliance.application.classification_services import ClassificationService
from crossborder_compliance.application.country_compliance_services import CountryComplianceSkill
from crossborder_compliance.application.decision_services import FormalDecisionService
from crossborder_compliance.application.formal_result_services import (
    CrossBorderAssessmentService,
    RegulatoryDocumentRequirementService,
)
from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
from crossborder_compliance.application.retrieval_services import KnowledgeRetrievalService
from crossborder_compliance.application.workflow_formal import (
    FormalWorkflowAuthorization,
    FormalWorkflowStages,
    WorkflowDeliveryService,
)
from crossborder_compliance.infrastructure.persistence.classification_repository import (
    PostgresFormalClassificationRepository,
)
from crossborder_compliance.infrastructure.persistence.context_repositories import (
    PostgresContextResolutionRepository,
)
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)
from crossborder_compliance.infrastructure.persistence.runtime_operations import (
    SqlRuntimeOperations,
)
from crossborder_compliance.infrastructure.persistence.workflow_authorization import (
    SqlWorkflowAuthorization,
)
from crossborder_compliance.infrastructure.persistence.workflow_delivery_guard import (
    PostgresWorkflowDeliveryGuard,
)
from crossborder_compliance.infrastructure.retrieval_search import (
    PgvectorRetrieverAdapter,
    PostgresFTSRetrieverAdapter,
)
from crossborder_compliance.workflows.canonical import GRAPH_VERSION, CanonicalGraphFactory
from crossborder_compliance.workflows.langgraph_adapter import (
    LangGraphWorkflowRuntimeAdapter,
    installed_version,
)
from crossborder_compliance.workflows.runtime_context import RuntimeContext


def formal_workflow_runtime(
    *,
    sessions,
    context,
    plan,
    postgres_uri,
    request_id,
    preferred_locale=None,
    execution_policy=None,
    retrieval_ports=None,
):
    """The trusted host supplies a server-prepared, stable plan and current access.

    H/I/J configuration must already be explicitly pinned by its owning services.
    No hidden latest-version selection, HTTP calls or raw database work here.
    Connector cancellation remains the existing synchronous-port boundary.
    """
    if context.tenant_id != plan.tenant_id:
        raise PermissionError("workflow plan not found")
    if (
        not context.permission.system
        and f"project:{plan.project_id}:comply" not in context.permission.scopes
    ):
        raise PermissionError("workflow project not found")
    retrieval_repo = PostgresRetrievalRepository(sessions, context)
    country_repo = PostgresCountryComplianceRepository(sessions, context)
    stages = FormalWorkflowStages(
        plan,
        contexts=PostgresContextResolutionRepository(
            sessions, context, context_resolution_run_id=plan.context_resolution_run_id
        ),
        knowledge_scope=KnowledgeScopeResolver(retrieval_repo, context),
        retrieval=KnowledgeRetrievalService(
            retrieval_repo,
            context,
            PostgresFTSRetrieverAdapter(sessions, context),
            PgvectorRetrieverAdapter(sessions, context),
            **(retrieval_ports or {}),
        ),
        evidence=retrieval_repo,
        classification=ClassificationService(
            PostgresFormalClassificationRepository(sessions, context)
        ),
        country=CountryComplianceSkill(country_repo),
        decisions=FormalDecisionService(country_repo),
        scenario_rules=country_repo,
        cross_border=CrossBorderAssessmentService(country_repo),
        document_requirements=RegulatoryDocumentRequirementService(country_repo),
    )
    auth = SqlWorkflowAuthorization(
        sessions, context, request_context_ref=plan.request_context_ref, mode=plan.mode
    )
    factory = CanonicalGraphFactory(
        authorization=FormalWorkflowAuthorization(auth, plan),
        stages=stages.bindings(),
        policy=execution_policy,
        emit_result_refs=True,
    )
    runtime = LangGraphWorkflowRuntimeAdapter(
        postgres_uri=postgres_uri,
        context=RuntimeContext(
            SqlRuntimeOperations(RuntimeRepository(sessions)),
            request_id,
            GRAPH_VERSION,
            installed_version("langgraph"),
            installed_version("langgraph-checkpoint-postgres"),
            preferred_locale,
        ),
        graph_factory=factory,
    )
    return WorkflowDeliveryService(
        runtime, factory, PostgresWorkflowDeliveryGuard(sessions, context)
    ), factory
