"""Durable northbound subscriptions; keys resolve from encrypted SecretStore."""
import secrets
from uuid import UUID,uuid4

from sqlalchemy import select

from crossborder_compliance.application.integrations import IntegrationFailure
from crossborder_compliance.domain.integrations import WEBHOOK_EVENTS, IntegrationScope, WebhookView, WebhookSecretView, DeliveryView
from crossborder_compliance.infrastructure.persistence.integration_models import WebhookSubscriptionEntity as Subscription, WebhookDeliveryEntity as Delivery
from crossborder_compliance.infrastructure.webhook_http import callback_addresses


class PostgresWebhookRepository:
    def __init__(self,identity,principal,store,internal_hosts=()):
        self.identity,self.principal,self.store,self.internal_hosts=identity,principal,store,internal_hosts
        self.sessions=identity.sessions

    def _authorize(self):
        if self.identity.admin_context:
            with self.sessions() as s:self.identity._admin_client(s,self.principal.client_id)
            return self.identity.admin_context
        return self.identity.context(self.principal,IntegrationScope.WEBHOOK_MANAGE)

    def _row(self,s,identity,lock=False):
        q=select(Subscription).where(Subscription.subscription_id==str(identity),
            Subscription.tenant_id==str(self.principal.tenant_id),Subscription.client_id==str(self.principal.client_id))
        row=s.scalar(q.with_for_update() if lock else q)
        if not row:raise IntegrationFailure('FORBIDDEN',404)
        return row

    @staticmethod
    def view(row):return WebhookView(subscription_id=row.subscription_id,client_id=row.client_id,
        callback_url=row.callback_url,event_codes=row.event_codes_json,enabled=row.enabled,
        record_version=row.record_version,secret_configured=True)

    def list(self):
        self._authorize()
        with self.sessions() as s:return tuple(self.view(row) for row in s.scalars(select(Subscription).where(
            Subscription.tenant_id==str(self.principal.tenant_id),Subscription.client_id==str(self.principal.client_id))))

    def create(self,command,key):
        ctx=self._authorize()
        if not set(command.event_codes)<=WEBHOOK_EVENTS:raise IntegrationFailure('INVALID_INPUT',422)
        callback_addresses(command.callback_url,command.deployment_class,self.internal_hosts)
        if self.store is None:raise IntegrationFailure('CAPABILITY_NOT_CONFIGURED',503)
        with self.sessions() as s,s.begin():
            record,duplicate=self.identity._key(s,ctx.tenant_id,self.principal.client_id,'webhook-create',key,command.model_dump(mode='json'))
            if duplicate:return WebhookSecretView(subscription=self.view(self._row(s,record.response_ref)))
            raw=secrets.token_urlsafe(32)
            row=Subscription(subscription_id=str(uuid4()),tenant_id=str(ctx.tenant_id),client_id=str(self.principal.client_id),
                callback_url=command.callback_url,deployment_class=command.deployment_class,event_codes_json=list(command.event_codes),
                enabled=True,secret_ref=self.store.put(raw),created_by=ctx.permission.actor_id,updated_by=ctx.permission.actor_id)
            s.add(row);s.flush();record.response_ref=row.subscription_id
            return WebhookSecretView(subscription=self.view(row),secret=raw)

    def change(self,identity,command,key,rotate=False):
        ctx=self._authorize()
        with self.sessions() as s,s.begin():
            record,duplicate=self.identity._key(s,ctx.tenant_id,self.principal.client_id,
                f'webhook-{"rotate" if rotate else "update"}:{identity}',key,command.model_dump(mode='json'))
            row=self._row(s,identity,True)
            if duplicate:return WebhookSecretView(subscription=self.view(row)) if rotate else self.view(row)
            if row.record_version!=command.expected_version:raise IntegrationFailure('VERSION_CONFLICT',409)
            raw=None
            if rotate:
                if self.store is None:raise IntegrationFailure('CAPABILITY_NOT_CONFIGURED',503)
                raw=secrets.token_urlsafe(32);row.secret_ref=self.store.put(raw)
            else:row.enabled=command.enabled
            row.record_version+=1;row.updated_by=ctx.permission.actor_id;record.response_ref=row.subscription_id
            return WebhookSecretView(subscription=self.view(row),secret=raw) if rotate else self.view(row)

    def deliveries(self,identity):
        self._authorize()
        with self.sessions() as s:
            self._row(s,identity)
            return tuple(DeliveryView(delivery_id=r.delivery_id,subscription_id=r.subscription_id,event_id=r.event_id,
                status=r.status,attempts=r.attempts,last_status_code=r.last_status_code,error_code=r.error_code,
                next_attempt_at=r.next_attempt_at) for r in s.scalars(select(Delivery).where(
                    Delivery.subscription_id==str(identity),Delivery.tenant_id==str(self.principal.tenant_id)).order_by(Delivery.next_attempt_at.desc()).limit(50)))

    def test(self,identity,key):
        self._authorize()
        with self.sessions() as s,s.begin():
            row=self._row(s,identity)
            record,duplicate=self.identity._key(s,self.principal.tenant_id,self.principal.client_id,
                                              'webhook-test:'+str(identity),key,{})
            if not row.enabled:raise IntegrationFailure('FORBIDDEN')
            if not duplicate:
                delivery=Delivery(delivery_id=str(uuid4()),tenant_id=row.tenant_id,subscription_id=row.subscription_id,
                    event_id=str(uuid4()),status='PENDING',attempts=0)
                s.add(delivery);record.response_ref=delivery.delivery_id
            return {'delivery_id':record.response_ref,'status':'ACCEPTED'}
