from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_phase1c_model_registry import _sf, _seed_tenant

from crossborder_compliance.application.integrations import IntegrationFailure, IntegrationService
from crossborder_compliance.application.intake_services import CreateProjectFromIntake
from crossborder_compliance.domain.integrations import ClientCreate, ClientUpdate, IntegrationPolicy, IntegrationScope, TokenRequest, VersionCommand
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.integration_models import IntegrationAccessTokenEntity, IntegrationCredentialEntity
from crossborder_compliance.infrastructure.persistence.integrations import PostgresIntegrationRepository
from crossborder_compliance.infrastructure.persistence.postgres_repositories import PostgresProjectRepository

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def integrations():
    sf, tenant = _sf(), uuid4()
    _seed_tenant(sf, tenant)
    admin = RepositoryContext.user(tenant, 'integration-admin', {'integration:manage'})
    policy = IntegrationPolicy()
    repo = PostgresIntegrationRepository(sf, policy, admin)
    service = IntegrationService(repo, policy)
    create = ClientCreate(display_name='ERP', allowed_scopes=tuple(IntegrationScope))
    client = service.create_client(create, uuid4().hex)
    return sf, tenant, repo, service, client


def issue(service, client, **values):
    return service.token(TokenRequest(grant_type='client_credentials',client_id=client.client.client_id,
                                     client_secret=client.credential, **values))


def test_oauth_live_scopes_hashed_credentials_and_no_get_secret(integrations):
    sf, _, repo, service, created = integrations
    token = issue(service, created, scope='project:create project:read')
    p = service.authenticate(token.access_token)
    ctx = service.authorize(p, IntegrationScope.PROJECT_CREATE)
    assert ctx.permission.actor_id == f'integration:{created.client.client_id}'
    assert not ctx.permission.system
    assert 'project:create' in ctx.permission.scopes
    assert created.credential not in service.clients()[0].model_dump_json()
    with sf() as s:
        credential = s.scalar(select(IntegrationCredentialEntity).where(IntegrationCredentialEntity.client_id==str(p.client_id)))
        assert credential.credential_hash.startswith('scrypt$') and created.credential not in credential.credential_hash
        saved = s.scalar(select(IntegrationAccessTokenEntity).where(IntegrationAccessTokenEntity.client_id==str(p.client_id)))
        assert token.access_token != saved.token_digest
    with pytest.raises(IntegrationFailure,match='INVALID_SCOPE'):
        service.authorize(p, IntegrationScope.COMPLIANCE_ANALYZE)
    with pytest.raises(IntegrationFailure,match='UNAUTHORIZED'):
        service.authenticate('invalid')


@pytest.mark.parametrize('change',['expired','disabled','revoked','rotated','scope_removed'])
def test_token_revalidates_current_authority(integrations,change):
    sf, _, repo, service, created = integrations
    token = issue(service, created)
    if change=='expired':
        with sf() as s,s.begin():
            row=s.scalar(select(IntegrationAccessTokenEntity).where(IntegrationAccessTokenEntity.client_id==str(created.client.client_id)))
            row.expires_at=datetime.now(UTC)-timedelta(seconds=1)
    elif change=='rotated':
        newer=service.rotate_client(created.client.client_id,VersionCommand(expected_version=1),uuid4().hex)
        assert issue(service,newer).access_token
        with pytest.raises(IntegrationFailure):issue(service,created)
    elif change=='scope_removed':
        service.update_client(created.client.client_id,ClientUpdate(expected_version=1,status='ACTIVE',allowed_scopes=(IntegrationScope.PROJECT_READ,)),uuid4().hex)
        p=service.authenticate(token.access_token)
        with pytest.raises(IntegrationFailure,match='INVALID_SCOPE'): service.authorize(p,IntegrationScope.PROJECT_CREATE)
        return
    else:
        service.update_client(created.client.client_id,ClientUpdate(expected_version=1,status='DISABLED' if change=='disabled' else 'REVOKED'),uuid4().hex)
    with pytest.raises(IntegrationFailure,match='UNAUTHORIZED'): service.authenticate(token.access_token)


def test_service_account_same_context_revocable_no_global_authority(integrations):
    _, _, repo, service, _=integrations
    created=service.create_client(ClientCreate(display_name='Service',credential_type='SERVICE_ACCOUNT',allowed_scopes=(IntegrationScope.PROJECT_READ,)),uuid4().hex)
    principal=service.authenticate(created.credential)
    ctx=service.authorize(principal,IntegrationScope.PROJECT_READ)
    assert ctx.permission.actor_id.startswith('integration:') and not ctx.permission.system
    with pytest.raises(IntegrationFailure): issue(service,created)
    service.rotate_client(created.client.client_id,VersionCommand(expected_version=1),uuid4().hex)
    with pytest.raises(IntegrationFailure):service.authenticate(created.credential)


def test_binding_fail_closed_cross_client_and_tenant(integrations):
    sf, tenant, repo, service, created=integrations
    principal=service.authenticate(issue(service,created).access_token)
    ctx=service.authorize(principal,IntegrationScope.PROJECT_CREATE)
    view=PostgresProjectRepository(sf,ctx).create_intake(CreateProjectFromIntake(name=uuid4().hex,idempotency_key=uuid4().hex,facts={'analysis_as_of_date':'2026-10-09'}))
    with pytest.raises(IntegrationFailure,match='PROJECT_ACCESS_DENIED'):service.authorize(principal,IntegrationScope.PROJECT_READ,view.project_id)
    repo.bind_created(principal,view.project_id)
    assert f'project:{view.project_id}:comply' in service.authorize(principal,IntegrationScope.PROJECT_READ,view.project_id).permission.scopes
    other=service.create_client(ClientCreate(display_name='Other',allowed_scopes=(IntegrationScope.PROJECT_READ,)),uuid4().hex)
    with pytest.raises(IntegrationFailure):service.authorize(service.authenticate(issue(service,other).access_token),IntegrationScope.PROJECT_READ,view.project_id)
    foreign=PostgresIntegrationRepository(sf,repo.policy,RepositoryContext.user(uuid4(),'other',{'integration:manage'}))
    with pytest.raises(IntegrationFailure):foreign.rotate_client(created.client.client_id,VersionCommand(expected_version=1),uuid4().hex)


def test_admin_idempotency_cas_and_secret_reveal_once(integrations):
    _,_,repo,service,created=integrations
    key=uuid4().hex; cmd=ClientCreate(display_name='Second',allowed_scopes=(IntegrationScope.PROJECT_READ,))
    one=service.create_client(cmd,key);two=service.create_client(cmd,key)
    assert one.client.client_id==two.client.client_id and one.credential_id==two.credential_id
    assert one.credential and two.credential is None
    with pytest.raises(IntegrationFailure,match='IDEMPOTENCY_CONFLICT'):service.create_client(cmd.model_copy(update={'display_name':'changed'}),key)
    service.update_client(created.client.client_id,ClientUpdate(expected_version=1,status='DISABLED'),uuid4().hex)
    with pytest.raises(IntegrationFailure,match='VERSION_CONFLICT'):service.update_client(created.client.client_id,ClientUpdate(expected_version=1,status='ACTIVE'),uuid4().hex)


def test_atomic_rate_and_quota_are_configured(integrations):
    _,_,repo,service,created=integrations
    principal=service.authenticate(issue(service,created).access_token)
    repo.policy=IntegrationPolicy(client_rate_limits={'read':1},client_quotas={'requests':10,'start':10,'upload':10})
    repo.consume(principal,'read')
    with pytest.raises(IntegrationFailure,match='RATE_LIMITED') as err:repo.consume(principal,'read')
    assert err.value.status==429 and err.value.retry_after>0
    repo.policy=IntegrationPolicy(client_rate_limits={'write':10},client_quotas={'requests':1,'start':10,'upload':10})
    with pytest.raises(IntegrationFailure,match='QUOTA_EXCEEDED'):repo.consume(principal,'write')
