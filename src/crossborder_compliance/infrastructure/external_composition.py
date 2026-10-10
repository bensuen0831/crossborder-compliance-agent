"""Reuse canonical channel composition, not an external compliance engine."""

from datetime import UTC, datetime, timedelta
from functools import partial

from crossborder_compliance.application.external_channel import ExternalChannelService
from crossborder_compliance.application.integrations import IntegrationFailure, IntegrationService
from crossborder_compliance.application.llm_model_catalog import ModelCatalogQuery
from crossborder_compliance.domain.integrations import (
    ExternalWorkflowAccepted,
    ExternalWorkflowEvent,
    IntegrationPolicy,
    external_event_code,
)
from crossborder_compliance.infrastructure.document_input_composition import document_input_service
from crossborder_compliance.infrastructure.intake_composition import (
    intake_service,
    prepare_snapshot,
)
from crossborder_compliance.infrastructure.llm_model_catalog_composition import model_catalog
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationWorkflowDeliveryEntity,
)
from crossborder_compliance.infrastructure.persistence.integrations import (
    PostgresIntegrationRepository,
)
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository
from crossborder_compliance.infrastructure.persistence.workflow_read_projection import (
    WorkflowReadProjection,
)
from crossborder_compliance.interfaces.api.routes import workflow as canonical_workflow


def integration_service(request, context=None):
    import os

    policy = getattr(request.app.state, "integration_policy", None)
    if policy is None:
        raw = os.environ.get("EXTERNAL_INTEGRATION_POLICY_JSON")
        policy = IntegrationPolicy.model_validate_json(raw) if raw else IntegrationPolicy()
    repository = PostgresIntegrationRepository(
        canonical_workflow.sessions(request), policy, context
    )
    return IntegrationService(repository, policy)


def integration_secret_store(request, context):
    import os

    from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore

    factory = getattr(request.app.state, "integration_secret_store_factory", None)
    if factory:
        return factory(context)
    root = os.environ.get("INTEGRATION_SECRET_STORE_ROOT")
    key = os.environ.get("INTEGRATION_SECRET_STORE_KEY")
    if not root or not key:
        return None
    # Separate northbound root/key; never resolve a southbound provider reference.
    return EncryptedFileSecretStore(root, key.encode(), context.tenant_id)


def integration_internal_callback_hosts(request):
    import json
    import os

    configured = getattr(request.app.state, "integration_internal_callback_hosts", None)
    values = (
        configured
        if configured is not None
        else json.loads(os.environ.get("INTEGRATION_INTERNAL_CALLBACK_HOSTS", "[]"))
    )
    if not isinstance(values, (list, tuple)) or any(
        not isinstance(x, str) or not x for x in values
    ):
        raise IntegrationFailure("CAPABILITY_NOT_CONFIGURED", 503)
    return tuple(values)


class CanonicalChannelComposition:
    def __init__(self, request, integration):
        self.request, self.integration = request, integration
        self.sessions = canonical_workflow.sessions(request)

    def intake(self, context):
        secret_factory = getattr(self.request.app.state, "llm_secret_store_factory", None)
        preparer = getattr(self.request.app.state, "intake_snapshot_preparer", None) or partial(
            prepare_snapshot,
            llm_dependencies={
                "storage": getattr(self.request.app.state, "document_object_storage", None),
                "secrets": secret_factory(context) if secret_factory else None,
                "redaction": getattr(self.request.app.state, "llm_data_redaction_service", None),
            },
        )
        return intake_service(self.sessions, context, preparer)

    def documents(self, context):
        return document_input_service(self.request, self.sessions, context)

    def eligible_models(self, context, project):
        return model_catalog(self.sessions, context).read(ModelCatalogQuery(project_id=project))

    def idempotent(self, principal, operation, key, payload, execute, replay, reference):
        with self.sessions() as s, s.begin():
            row, duplicate = self.integration.repository._key(
                s, principal.tenant_id, principal.client_id, operation, key, payload
            )
            if duplicate:
                return replay(row.response_ref)
            value = execute()
            row.response_ref = reference(value)
            return value

    def run_scope(self, tenant, run):
        from crossborder_compliance.domain.security import RepositoryContext

        # This read supplies identity only; binding/action authorization follows
        # before any runtime/result/event is read. Never grants a tenant-wide project.
        try:
            return WorkflowReadProjection(
                self.sessions, RepositoryContext.user(tenant, "integration-scope")
            ).run_scope(run)
        except LookupError:
            raise IntegrationFailure("WORKFLOW_NOT_FOUND", 404) from None

    def enqueue(self, principal, context, project, snapshot, key):
        sf, runtime, factory, run = canonical_workflow.delivery(
            self.request, context, project, snapshot, "execute"
        )
        # Existing pin/authorization owner reconstructs and validates the run;
        # no execution occurs on the HTTP request.
        with sf() as s, s.begin():
            idem, duplicate = self.integration.repository._key(
                s,
                principal.tenant_id,
                principal.client_id,
                "start",
                key,
                {"project": str(project), "snapshot": str(snapshot)},
            )
            job = s.get(IntegrationWorkflowDeliveryEntity, str(run))
            if job is None:
                job = IntegrationWorkflowDeliveryEntity(
                    workflow_run_id=str(run),
                    tenant_id=str(context.tenant_id),
                    client_id=str(principal.client_id),
                    credential_id=str(principal.credential_id),
                    project_id=str(project),
                    snapshot_id=str(snapshot),
                    scopes_json=list(principal.scopes),
                    correlation_id=self.request.state.request_id,
                    status="PENDING",
                    attempts=0,
                    deadline_at=datetime.now(UTC)
                    + timedelta(seconds=self.integration.policy.analysis_deadline_seconds),
                )
                s.add(job)
            elif job.client_id != str(principal.client_id):
                raise IntegrationFailure("PROJECT_ACCESS_DENIED", 404)
            idem.response_ref = str(run)
            status = job.status
        prefix = "/api/v1/external/workflows/" + str(run)
        return ExternalWorkflowAccepted(
            project_id=project,
            analysis_snapshot_id=snapshot,
            workflow_run_id=run,
            status="ACCEPTED" if status in {"PENDING", "DELIVERING"} else status,
            status_url=prefix,
            result_url=prefix + "/stage1-result",
            events_url=prefix + "/events",
        )

    def status(self, context, run, project, snapshot):
        # Pending technical delivery is a projection, not a second workflow status authority.
        with self.sessions() as s:
            job = s.get(IntegrationWorkflowDeliveryEntity, str(run))
            if job and job.status in {"PENDING", "DELIVERING"}:
                return canonical_workflow.WorkflowView(
                    workflow_run_id=run,
                    project_id=project,
                    analysis_snapshot_id=snapshot,
                    status="RUNNING",
                    reason_codes=(
                        "ASYNC_DELIVERY_PENDING"
                        if job.status == "PENDING"
                        else "ASYNC_DELIVERY_IN_PROGRESS",
                    ),
                )
            if job and job.status == "DENIED":
                raise IntegrationFailure("FORBIDDEN")
            if job and job.status == "FAILED":
                return canonical_workflow.WorkflowView(
                    workflow_run_id=run,
                    project_id=project,
                    analysis_snapshot_id=snapshot,
                    status="FAILED",
                    reason_codes=(job.error_code or "DELIVERY_FAILED",),
                )
        return canonical_workflow.read(run, self.request, context)

    def result(self, context, run):
        with self.sessions() as session:
            job = session.get(IntegrationWorkflowDeliveryEntity, str(run))
            if job and job.status in {"PENDING", "DELIVERING"}:
                raise IntegrationFailure("RESULT_NOT_READY", 409, retryable=True)
        return canonical_workflow.stage1_result(run, self.request, context)

    def events(self, tenant, project, snapshot, run, after=None):
        values = RuntimeRepository(self.sessions).workflow_events(run, tenant)
        if after:
            indexes = [i for i, x in enumerate(values) if x.event_id == after]
            if not indexes:
                raise IntegrationFailure("INVALID_INPUT", 422)
            values = values[indexes[0] + 1 :]
        return tuple(
            self._event(x, project, snapshot, run)
            for x in values[: self.integration.policy.event_batch_size]
        )

    def event(self, tenant, project, snapshot, run, event_id):
        # Delivery selects its exact canonical event, independent of stream batch.
        value = next(
            (
                e
                for e in RuntimeRepository(self.sessions).workflow_events(run, tenant)
                if e.event_id == event_id
            ),
            None,
        )
        if value is None:
            raise IntegrationFailure("WORKFLOW_NOT_FOUND", 404)
        return self._event(value, project, snapshot, run)

    def _event(self, event, project, snapshot, run):
        with self.sessions() as s:
            job = s.get(IntegrationWorkflowDeliveryEntity, str(run))
            correlation = job.correlation_id if job else event.request_id
        value = event.payload
        return ExternalWorkflowEvent(
            event_id=event.event_id,
            event_code=external_event_code(event.event_type.value),
            timestamp=event.timestamp,
            project_id=project,
            workflow_run_id=run,
            analysis_snapshot_id=snapshot,
            status=event.status,
            step=event.node_code,
            result_ref=f"/api/v1/external/workflows/{run}/stage1-result"
            if event.event_type == "WORKFLOW_COMPLETED"
            else None,
            review_ref=value.get("review_id") or value.get("review_ref"),
            reason_codes=tuple(value.get("reason_codes", ())),
            correlation_id=correlation,
        )


def external_channel(request, principal):
    integration = integration_service(request)
    return ExternalChannelService(
        integration, principal, CanonicalChannelComposition(request, integration)
    )
