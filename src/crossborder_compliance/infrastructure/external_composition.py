"""Reuse canonical channel composition, not an external compliance engine."""
from functools import partial
from types import SimpleNamespace
from uuid import UUID, uuid4
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from crossborder_compliance.application.integrations import IntegrationFailure, IntegrationService
from crossborder_compliance.application.external_channel import ExternalChannelService
from crossborder_compliance.application.llm_model_catalog import ModelCatalogQuery
from crossborder_compliance.domain.integrations import ExternalWorkflowAccepted, ExternalWorkflowEvent, IntegrationPolicy
from crossborder_compliance.infrastructure.intake_composition import intake_service, prepare_snapshot
from crossborder_compliance.infrastructure.document_input_composition import document_input_service
from crossborder_compliance.infrastructure.llm_model_catalog_composition import model_catalog
from crossborder_compliance.infrastructure.persistence.integration_models import IntegrationWorkflowDeliveryEntity
from crossborder_compliance.infrastructure.persistence.integrations import PostgresIntegrationRepository
from crossborder_compliance.infrastructure.persistence.models import WorkflowEventEntity
from crossborder_compliance.infrastructure.persistence.workflow_read_projection import WorkflowReadProjection
from crossborder_compliance.interfaces.api.routes import workflow as canonical_workflow


def integration_service(request,context=None):
    import os
    policy=getattr(request.app.state,'integration_policy',None)
    if policy is None:
        raw=os.environ.get('EXTERNAL_INTEGRATION_POLICY_JSON')
        policy=IntegrationPolicy.model_validate_json(raw) if raw else IntegrationPolicy()
    repository=PostgresIntegrationRepository(canonical_workflow.sessions(request),policy,context)
    return IntegrationService(repository,policy)


class CanonicalChannelComposition:
    def __init__(self,request,integration):
        self.request,self.integration=request,integration
        self.sessions=canonical_workflow.sessions(request)

    def intake(self,context):
        secret_factory=getattr(self.request.app.state,'llm_secret_store_factory',None)
        preparer=getattr(self.request.app.state,'intake_snapshot_preparer',None) or partial(
            prepare_snapshot,llm_dependencies={
                'storage':getattr(self.request.app.state,'document_object_storage',None),
                'secrets':secret_factory(context) if secret_factory else None,
                'redaction':getattr(self.request.app.state,'llm_data_redaction_service',None)})
        return intake_service(self.sessions,context,preparer)

    def documents(self,context):
        return document_input_service(self.request,self.sessions,context)

    def eligible_models(self,context,project):
        return model_catalog(self.sessions,context).read(ModelCatalogQuery(project_id=project))

    def idempotent(self,principal,operation,key,payload,execute,replay,reference):
        with self.sessions() as s,s.begin():
            row,duplicate=self.integration.repository._key(s,principal.tenant_id,principal.client_id,operation,key,payload)
            if duplicate:return replay(row.response_ref)
            value=execute()
            row.response_ref=reference(value)
            return value

    def run_scope(self,tenant,run):
        from crossborder_compliance.domain.security import RepositoryContext
        # This read supplies identity only; binding/action authorization follows
        # before any runtime/result/event is read. Never grants a tenant-wide project.
        return WorkflowReadProjection(self.sessions,RepositoryContext.user(tenant,'integration-scope')).run_scope(run)

    def enqueue(self,principal,context,project,snapshot,key):
        sf,runtime,factory,run=canonical_workflow.delivery(self.request,context,project,snapshot,'execute')
        # Existing pin/authorization owner reconstructs and validates the run;
        # no execution occurs on the HTTP request.
        with sf() as s,s.begin():
            idem,duplicate=self.integration.repository._key(s,principal.tenant_id,principal.client_id,
                'start',key,{'project':str(project),'snapshot':str(snapshot)})
            job=s.get(IntegrationWorkflowDeliveryEntity,str(run))
            if job is None:
                job=IntegrationWorkflowDeliveryEntity(workflow_run_id=str(run),tenant_id=str(context.tenant_id),
                    client_id=str(principal.client_id),credential_id=str(principal.credential_id),
                    project_id=str(project),snapshot_id=str(snapshot),scopes_json=list(principal.scopes),
                    correlation_id=self.request.state.request_id,status='PENDING',attempts=0,
                    deadline_at=datetime.now(UTC)+timedelta(seconds=self.integration.policy.analysis_deadline_seconds))
                s.add(job)
            elif job.client_id != str(principal.client_id):
                raise IntegrationFailure('PROJECT_ACCESS_DENIED',404)
            idem.response_ref=str(run)
            status=job.status
        prefix='/api/v1/external/workflows/'+str(run)
        return ExternalWorkflowAccepted(project_id=project,analysis_snapshot_id=snapshot,
            workflow_run_id=run,status='ACCEPTED' if status in {'PENDING','DELIVERING'} else status,
            status_url=prefix,result_url=prefix+'/stage1-result',events_url=prefix+'/events')

    def status(self,context,run,project,snapshot):
        # Pending technical delivery is a projection, not a second workflow status authority.
        with self.sessions() as s:
            job=s.get(IntegrationWorkflowDeliveryEntity,str(run))
            if job and job.status=='PENDING':
                return canonical_workflow.WorkflowView(workflow_run_id=run,project_id=project,
                    analysis_snapshot_id=snapshot,status='RUNNING',reason_codes=('ASYNC_DELIVERY_PENDING',))
            if job and job.status=='DENIED':raise IntegrationFailure('FORBIDDEN')
        return canonical_workflow.read(run,self.request,context)

    def result(self,context,run):
        return canonical_workflow.stage1_result(run,self.request,context)

    def events(self,tenant,project,snapshot,run,after=None):
        with self.sessions() as s:
            rows=s.scalars(select(WorkflowEventEntity).where(WorkflowEventEntity.tenant_id==str(tenant),
                WorkflowEventEntity.workflow_run_id==str(run)).order_by(
                    WorkflowEventEntity.occurred_at,WorkflowEventEntity.event_id)).all()
            if after:
                indexes=[i for i,x in enumerate(rows) if x.event_id==str(after)]
                if not indexes:raise IntegrationFailure('INVALID_INPUT',422)
                rows=rows[indexes[0]+1:]
            result=[]
            for row in rows[:100]:
                payload=row.payload_json
                # Runtime persistence stores DTO payload; never forward arbitrary
                # nested payload or raw checkpoint/model output.
                value=payload.get('payload',payload)
                result.append(ExternalWorkflowEvent(event_id=row.event_id,event_code=row.event_type,
                    timestamp=row.occurred_at,project_id=project,workflow_run_id=run,analysis_snapshot_id=snapshot,
                    status=payload.get('status',value.get('status')),step=row.node_code,
                    result_ref=f'/api/v1/external/workflows/{run}/stage1-result' if row.event_type=='WORKFLOW_COMPLETED' else None,
                    review_ref=value.get('review_id') or value.get('review_ref'),
                    reason_codes=tuple(value.get('reason_codes',()))))
            return tuple(result)


def external_channel(request,principal):
    integration=integration_service(request)
    return ExternalChannelService(integration,principal,CanonicalChannelComposition(request,integration))
