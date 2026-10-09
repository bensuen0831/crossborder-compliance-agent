"""Technical northbound delivery workers; canonical runtime remains sole authority."""
import json
import logging
import threading
from datetime import UTC,datetime,timedelta
from types import SimpleNamespace
from uuid import UUID,uuid4

from sqlalchemy import or_,select

from crossborder_compliance.application.integrations import IntegrationFailure
from crossborder_compliance.domain.integrations import IntegrationPrincipal,IntegrationScope
from crossborder_compliance.infrastructure.external_composition import CanonicalChannelComposition,integration_service
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationWorkflowDeliveryEntity as Job,WebhookSubscriptionEntity as Sub,
    WebhookDeliveryEntity as Delivery,IntegrationClientEntity as Client,IntegrationCredentialEntity as Credential)
from crossborder_compliance.infrastructure.persistence.models import WorkflowEventEntity
from crossborder_compliance.infrastructure.webhook_http import post_callback,signature
from crossborder_compliance.interfaces.api.routes import workflow as canonical_workflow

log=logging.getLogger(__name__)


class IntegrationDeliveryWorker:
    def __init__(self,app):
        self.app=app;self.stopping=threading.Event();self.thread=None
        self.request=SimpleNamespace(app=app,state=SimpleNamespace(request_id='integration-worker'))
        self.integration=integration_service(self.request);self.sessions=self.integration.repository.sessions
        self.policy=self.integration.policy

    def start(self):
        self.thread=threading.Thread(target=self.run,daemon=True,name='integration-delivery');self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread:self.thread.join(timeout=5)

    def run(self):
        while not self.stopping.is_set():
            try:
                self.deliver_workflow();self.enqueue_webhooks();self.deliver_webhook()
            except Exception:
                # No SQL/provider/secret exception text is logged.
                log.warning('integration delivery iteration unavailable')
            self.stopping.wait(self.policy.worker_poll_seconds)

    def claim(self,model,key):
        now=datetime.now(UTC);owner=uuid4().hex
        with self.sessions() as s,s.begin():
            row=s.scalar(select(model).where(model.status.in_(['PENDING','DELIVERING']),
                model.next_attempt_at<=now,or_(model.lease_until.is_(None),model.lease_until<now))
                .order_by(model.next_attempt_at).with_for_update(skip_locked=True).limit(1))
            if not row:return None
            row.status='DELIVERING';row.lease_until=now+timedelta(seconds=self.policy.delivery_lease_seconds)
            row.lease_owner=owner;row.attempts+=1
            return getattr(row,key),owner

    def finish(self,model,key,identity,owner,status,error=None,status_code=None):
        with self.sessions() as s,s.begin():
            row=s.get(model,identity)
            if row.lease_owner!=owner:return
            row.status=status;row.error_code=error;row.lease_owner=None;row.lease_until=None
            row.next_attempt_at=datetime.now(UTC)+timedelta(seconds=min(
                self.policy.webhook_max_backoff_seconds,self.policy.webhook_backoff_seconds*2**max(0,row.attempts-1)))
            if model is Delivery:row.last_status_code=status_code

    def deliver_workflow(self):
        claimed=self.claim(Job,'workflow_run_id')
        if not claimed:return False
        identity,owner=claimed
        with self.sessions() as s:job=s.get(Job,identity)
        try:
            if job.deadline_at<=datetime.now(UTC):raise IntegrationFailure('ANALYSIS_DEADLINE_EXCEEDED',408)
            principal=IntegrationPrincipal(client_id=job.client_id,tenant_id=job.tenant_id,
                credential_id=job.credential_id,scopes=job.scopes_json)
            ctx=self.integration.authorize(principal,IntegrationScope.COMPLIANCE_ANALYZE,UUID(job.project_id))
            request=SimpleNamespace(app=self.app,state=SimpleNamespace(request_id=job.correlation_id))
            # Same canonical orchestration, authorizers, guard, graph and saver.
            canonical_workflow.start(UUID(job.project_id),UUID(job.snapshot_id),canonical_workflow.WorkflowStart(),request,ctx)
            status,error='DELIVERED',None
        except IntegrationFailure as exc:status,error='DENIED',exc.code
        except Exception as exc:
            # Business outcomes are returned by the owning runtime, never retried.
            from crossborder_compliance.application.workflow_skeleton import WorkflowDeliveryRetryableFailure
            from fastapi import HTTPException
            technical=isinstance(exc,WorkflowDeliveryRetryableFailure) or isinstance(exc,HTTPException) and exc.status_code==503
            status='PENDING' if technical and job.attempts<self.policy.webhook_max_attempts else 'FAILED'
            error='DELIVERY_RETRYABLE' if technical else 'DELIVERY_FAILED'
        self.finish(Job,'workflow_run_id',identity,owner,status,error)
        return True

    def _principal(self,s,client_id):
        client=s.get(Client,client_id)
        if not client or client.status!='ACTIVE':raise IntegrationFailure('UNAUTHORIZED',401)
        cred=s.scalar(select(Credential).where(Credential.client_id==client.client_id,Credential.status=='ACTIVE',
                                              Credential.generation==client.credential_generation))
        if not cred:raise IntegrationFailure('UNAUTHORIZED',401)
        return IntegrationPrincipal(client_id=client.client_id,tenant_id=client.tenant_id,
            credential_id=cred.credential_id,scopes=client.allowed_scopes_json)

    def enqueue_webhooks(self):
        with self.sessions() as s,s.begin():
            # A subscription-specific advisory lock prevents absent-row duplicate
            # outbox creation across processes; canonical event rows are the SoT.
            from sqlalchemy import text
            for sub in s.scalars(select(Sub).where(Sub.enabled.is_(True),Sub.status=='ACTIVE')):
                s.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:k,0))'),{'k':'webhook:'+sub.subscription_id})
                try:principal=self._principal(s,sub.client_id)
                except IntegrationFailure:continue
                if IntegrationScope.WEBHOOK_MANAGE not in principal.scopes:continue
                events=s.scalars(select(WorkflowEventEntity).where(WorkflowEventEntity.tenant_id==sub.tenant_id,
                    WorkflowEventEntity.event_type.in_(sub.event_codes_json),WorkflowEventEntity.occurred_at>=sub.created_at))
                for event in events:
                    if s.scalar(select(Delivery.delivery_id).where(Delivery.subscription_id==sub.subscription_id,Delivery.event_id==event.event_id)):continue
                    composition=CanonicalChannelComposition(self.request,self.integration)
                    try:
                        project,_=composition.run_scope(principal.tenant_id,UUID(event.workflow_run_id))
                        self.integration.authorize(principal,IntegrationScope.COMPLIANCE_READ,project)
                    except (IntegrationFailure,LookupError):continue
                    s.add(Delivery(delivery_id=str(uuid4()),tenant_id=sub.tenant_id,subscription_id=sub.subscription_id,
                        event_id=event.event_id,workflow_run_id=event.workflow_run_id,status='PENDING',attempts=0))

    def deliver_webhook(self):
        claimed=self.claim(Delivery,'delivery_id')
        if not claimed:return False
        identity,owner=claimed
        with self.sessions() as s:
            row=s.get(Delivery,identity);sub=s.get(Sub,row.subscription_id)
            try:principal=self._principal(s,sub.client_id)
            except IntegrationFailure:
                self.finish(Delivery,'delivery_id',identity,owner,'CANCELLED','UNAUTHORIZED');return True
        try:
            if not sub.enabled:raise IntegrationFailure('FORBIDDEN')
            self.integration.authorize(principal,IntegrationScope.WEBHOOK_MANAGE)
            if row.workflow_run_id:
                composition=CanonicalChannelComposition(self.request,self.integration)
                project,snapshot=composition.run_scope(principal.tenant_id,UUID(row.workflow_run_id))
                self.integration.authorize(principal,IntegrationScope.COMPLIANCE_READ,project)
                event=next(e for e in composition.events(principal.tenant_id,project,snapshot,UUID(row.workflow_run_id)) if str(e.event_id)==row.event_id)
                payload=event.model_dump(mode='json')
            else:
                payload={'event_id':row.event_id,'schema_version':'1.0','event_code':'WEBHOOK_TEST',
                    'timestamp':datetime.now(UTC).isoformat(),'client_id':sub.client_id}
            factory=getattr(self.app.state,'integration_secret_store_factory',None)
            if factory is None:raise IntegrationFailure('CAPABILITY_NOT_CONFIGURED',503)
            ctx=self.integration.authorize(principal,IntegrationScope.WEBHOOK_MANAGE)
            secret=factory(ctx).resolve(sub.secret_ref)
            body=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
            stamp=str(int(datetime.now(UTC).timestamp()))
            code=post_callback(sub.callback_url,sub.deployment_class,
                getattr(self.app.state,'integration_internal_callback_hosts',()),body,
                {'Content-Type':'application/json','X-Delivery-ID':identity,'X-Webhook-Timestamp':stamp,
                 'X-Webhook-Signature':signature(secret,identity,stamp,body)},self.policy.webhook_timeout_seconds)
            status='DELIVERED' if 200<=code<300 else 'PENDING' if code>=500 or code in {408,429} else 'FAILED'
            error=None if status=='DELIVERED' else 'WEBHOOK_DELIVERY_FAILED'
        except IntegrationFailure as exc:status,error,code='CANCELLED',exc.code,None
        except Exception:status,error,code='PENDING','WEBHOOK_DELIVERY_FAILED',None
        if status=='PENDING' and row.attempts>=self.policy.webhook_max_attempts:status='FAILED'
        self.finish(Delivery,'delivery_id',identity,owner,status,error,code)
        return True
