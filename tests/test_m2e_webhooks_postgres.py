"""Actual HTTP callbacks, encrypted northbound keys and durable bounded retry."""
import threading
import time
from contextlib import contextmanager
from datetime import UTC,datetime,timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from test_phase1c_model_registry import _sf,_seed_tenant

from crossborder_compliance.application.integrations import IntegrationFailure,IntegrationService
from crossborder_compliance.domain.integrations import ClientCreate,IntegrationPolicy,IntegrationScope,TokenRequest,WebhookCreate,WebhookUpdate,VersionCommand
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.integration_worker import IntegrationDeliveryWorker
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence.integrations import PostgresIntegrationRepository
from crossborder_compliance.infrastructure.persistence.integration_models import WebhookDeliveryEntity,WebhookSubscriptionEntity
from crossborder_compliance.infrastructure.persistence.webhooks import PostgresWebhookRepository
from crossborder_compliance.infrastructure.webhook_http import verify_signature,callback_addresses

pytestmark=pytest.mark.runtime_smoke


@contextmanager
def receiver(mode):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']))
            requests.append((dict(self.headers),body))
            code=200 if mode=='success' or mode=='retry' and len(requests)>1 else 500
            if mode=='timeout':time.sleep(.1)
            self.send_response(code);self.end_headers()
        def log_message(self,*args):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{http.server_port}/callback',requests
    finally:http.shutdown();http.server_close();thread.join(timeout=3)


@pytest.fixture
def webhook(tmp_path):
    sf,tenant=_sf(),uuid4();_seed_tenant(sf,tenant)
    policy=IntegrationPolicy(webhook_max_attempts=2,webhook_timeout_seconds=.03,webhook_backoff_seconds=.05)
    admin=RepositoryContext.user(tenant,'integration-admin',{'integration:manage'})
    repo=PostgresIntegrationRepository(sf,policy,admin);service=IntegrationService(repo,policy)
    created=service.create_client(ClientCreate(display_name='Receiver',allowed_scopes=(IntegrationScope.WEBHOOK_MANAGE,)),uuid4().hex)
    token=service.token(TokenRequest(grant_type='client_credentials',client_id=created.client.client_id,client_secret=created.credential))
    principal=service.authenticate(token.access_token)
    store=EncryptedFileSecretStore(tmp_path/'northbound',Fernet.generate_key(),tenant)
    identity=PostgresIntegrationRepository(sf,policy)
    wh=PostgresWebhookRepository(identity,principal,store,('127.0.0.1',))
    state=SimpleNamespace(knowledge_session_factory=sf,integration_policy=policy,
        integration_secret_store_factory=lambda context:store,integration_internal_callback_hosts=('127.0.0.1',))
    worker=IntegrationDeliveryWorker(SimpleNamespace(state=state))
    return sf,wh,worker,principal,store


@pytest.mark.parametrize('mode',['success','retry','failure','timeout'])
def test_actual_signed_delivery_retry_and_bounded_failure(webhook,mode):
    sf,wh,worker,p,store=webhook
    with receiver(mode) as (url,received):
        made=wh.create(WebhookCreate(callback_url=url,deployment_class='INTERNAL',event_codes=('WORKFLOW_COMPLETED',)),uuid4().hex)
        assert made.secret
        assert made.secret not in wh.list()[0].model_dump_json()
        with sf() as s:
            saved=s.get(WebhookSubscriptionEntity,str(made.subscription.subscription_id))
            assert saved.secret_ref.startswith('secret://') and made.secret not in saved.secret_ref
        out=wh.test(made.subscription.subscription_id,uuid4().hex)
        assert worker.deliver_webhook()
        view=wh.deliveries(made.subscription.subscription_id)[0]
        if mode!='success':
            assert view.status=='PENDING' and view.attempts==1
            with sf() as s,s.begin():s.get(WebhookDeliveryEntity,out['delivery_id']).next_attempt_at=datetime.now(UTC)-timedelta(seconds=1)
            assert worker.deliver_webhook()
            view=wh.deliveries(made.subscription.subscription_id)[0]
        assert view.status==('DELIVERED' if mode in {'success','retry'} else 'FAILED')
        assert view.attempts==(1 if mode=='success' else 2)
        assert not worker.deliver_webhook()
        headers,body=received[0]
        assert verify_signature(made.secret,headers['X-Delivery-ID'],headers['X-Webhook-Timestamp'],body,
                                headers['X-Webhook-Signature'],now=time.time())
        assert b'secret_ref' not in body and made.secret.encode() not in body
        seen=set()
        assert verify_signature(made.secret,headers['X-Delivery-ID'],headers['X-Webhook-Timestamp'],body,headers['X-Webhook-Signature'],now=time.time(),seen_delivery_ids=seen)
        assert not verify_signature(made.secret,headers['X-Delivery-ID'],headers['X-Webhook-Timestamp'],body,headers['X-Webhook-Signature'],now=time.time(),seen_delivery_ids=seen)
        assert not verify_signature(made.secret,headers['X-Delivery-ID'],headers['X-Webhook-Timestamp'],body+b'altered',headers['X-Webhook-Signature'],now=time.time())


@pytest.mark.parametrize('url',['http://127.0.0.1/callback','https://169.254.169.254/latest','https://user:password@example.com/callback','https://metadata.google.internal/','https://10.0.0.1/callback'])
def test_external_callback_ssrf_rejected(url):
    with pytest.raises(IntegrationFailure):callback_addresses(url,'EXTERNAL')


def test_disable_and_rotate_key_cas_idempotency_preserve_delivery_history(webhook):
    _,wh,worker,_,_=webhook
    with receiver('success') as (url,requests):
        key=uuid4().hex;command=WebhookCreate(callback_url=url,deployment_class='INTERNAL',event_codes=('WORKFLOW_COMPLETED',))
        first=wh.create(command,key);again=wh.create(command,key)
        assert first.subscription.subscription_id==again.subscription.subscription_id and again.secret is None
        rotated=wh.change(first.subscription.subscription_id,VersionCommand(expected_version=1),uuid4().hex,True)
        assert rotated.secret and rotated.secret!=first.secret
        wh.test(first.subscription.subscription_id,uuid4().hex)
        wh.change(first.subscription.subscription_id,WebhookUpdate(expected_version=2,enabled=False),uuid4().hex)
        worker.deliver_webhook()
        assert not requests and wh.deliveries(first.subscription.subscription_id)[0].status=='CANCELLED'
        with pytest.raises(IntegrationFailure,match='VERSION_CONFLICT'):
            wh.change(first.subscription.subscription_id,WebhookUpdate(expected_version=1,enabled=True),uuid4().hex)
