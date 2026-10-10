"""Canonical Admin integration control plane and client-owned subscriptions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from crossborder_compliance.domain.integrations import (
    WEBHOOK_EVENTS,
    ClientCreate,
    ClientCredentialView,
    ClientUpdate,
    ClientView,
    DeliveryView,
    DeliveryAccepted,
    EmptyCommand,
    IntegrationOptions,
    IntegrationPrincipal,
    IntegrationScope,
    ProjectBindingCommand,
    ProjectBindingView,
    VersionCommand,
    WebhookCreate,
    WebhookSecretView,
    WebhookUpdate,
    WebhookView,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.external_composition import (
    integration_service,
    integration_secret_store,
    integration_internal_callback_hosts,
)
from crossborder_compliance.infrastructure.persistence.webhooks import PostgresWebhookRepository
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.external import ExternalRoute, Key, Principal
from crossborder_compliance.interfaces.api.routes.external import router as external_router

admin_router = APIRouter(
    prefix="/api/v1/admin/integration-clients",
    tags=["integration-admin"],
    route_class=ExternalRoute,
)
AdminContext = Annotated[RepositoryContext, Depends(get_repository_context)]


def admin(request, ctx):
    service = integration_service(request, ctx)
    service.repository._admin()
    request.state.integration_admin_context = ctx
    return service


def webhooks(request, p, identity=None):
    request.state.integration_scope = IntegrationScope.WEBHOOK_MANAGE.value
    service = identity or integration_service(request)
    ctx = service.repository.admin_context or service.authorize(p, IntegrationScope.WEBHOOK_MANAGE)
    return PostgresWebhookRepository(
        service.repository,
        p,
        integration_secret_store(request, ctx),
        integration_internal_callback_hosts(request),
    )


@admin_router.get("", response_model=tuple[ClientView, ...])
def clients(request: Request, ctx: AdminContext):
    return admin(request, ctx).clients()


@admin_router.get("/options", response_model=IntegrationOptions)
def options(request: Request, ctx: AdminContext):
    admin(request, ctx)
    return IntegrationOptions(
        scopes=tuple(IntegrationScope), webhook_events=tuple(sorted(WEBHOOK_EVENTS))
    )


@admin_router.get("/{client_id}/project-bindings", response_model=tuple[ProjectBindingView, ...])
def bindings(client_id: UUID, request: Request, ctx: AdminContext):
    return admin(request, ctx).project_bindings(client_id)


@admin_router.post("", response_model=ClientCredentialView, status_code=201)
def create_client(body: ClientCreate, request: Request, ctx: AdminContext, key: Key):
    return admin(request, ctx).create_client(body, key)


@admin_router.patch("/{client_id}", response_model=ClientView)
def update_client(
    client_id: UUID, body: ClientUpdate, request: Request, ctx: AdminContext, key: Key
):
    return admin(request, ctx).update_client(client_id, body, key)


@admin_router.post("/{client_id}/rotate-credential", response_model=ClientCredentialView)
def rotate(client_id: UUID, body: VersionCommand, request: Request, ctx: AdminContext, key: Key):
    return admin(request, ctx).rotate_client(client_id, body, key)


@admin_router.put("/{client_id}/project-binding", response_model=ClientView)
def bind(
    client_id: UUID, body: ProjectBindingCommand, request: Request, ctx: AdminContext, key: Key
):
    return admin(request, ctx).bind_project(client_id, body, key)


def admin_webhooks(request, ctx, client_id):
    service = admin(request, ctx)
    with service.repository.sessions() as s:
        client = service.repository._admin_client(s, client_id)
        # Admin configuration is delegated explicitly; never enters compliance
        # with integration identity or a system context.
        principal = IntegrationPrincipal(
            client_id=client.client_id,
            tenant_id=client.tenant_id,
            credential_id=UUID(int=0),
            scopes=client.allowed_scopes_json,
        )
    return webhooks(request, principal, service)


@external_router.get("/webhook-subscriptions", response_model=tuple[WebhookView, ...])
def subscriptions(request: Request, p: Principal):
    return webhooks(request, p).list()


@external_router.post("/webhook-subscriptions", response_model=WebhookSecretView, status_code=201)
def create_subscription(body: WebhookCreate, request: Request, p: Principal, key: Key):
    return webhooks(request, p).create(body, key)


@external_router.patch("/webhook-subscriptions/{subscription_id}", response_model=WebhookView)
def change_subscription(
    subscription_id: UUID, body: WebhookUpdate, request: Request, p: Principal, key: Key
):
    return webhooks(request, p).change(subscription_id, body, key)


@external_router.delete("/webhook-subscriptions/{subscription_id}", response_model=WebhookView)
def remove_subscription(
    subscription_id: UUID, body: VersionCommand, request: Request, p: Principal, key: Key
):
    return webhooks(request, p).change(
        subscription_id, WebhookUpdate(expected_version=body.expected_version, enabled=False), key
    )


@external_router.post(
    "/webhook-subscriptions/{subscription_id}/rotate-secret", response_model=WebhookSecretView
)
def rotate_subscription(
    subscription_id: UUID, body: VersionCommand, request: Request, p: Principal, key: Key
):
    return webhooks(request, p).change(subscription_id, body, key, True)


@external_router.get(
    "/webhook-subscriptions/{subscription_id}/deliveries", response_model=tuple[DeliveryView, ...]
)
def deliveries(subscription_id: UUID, request: Request, p: Principal):
    return webhooks(request, p).deliveries(subscription_id)


@external_router.post(
    "/webhook-subscriptions/{subscription_id}/test",
    response_model=DeliveryAccepted,
    status_code=202,
)
def test(subscription_id: UUID, body: EmptyCommand, request: Request, p: Principal, key: Key):
    return webhooks(request, p).test(subscription_id, key)


@admin_router.get("/{client_id}/webhook-subscriptions", response_model=tuple[WebhookView, ...])
def admin_subscriptions(client_id: UUID, request: Request, ctx: AdminContext):
    return admin_webhooks(request, ctx, client_id).list()


@admin_router.post(
    "/{client_id}/webhook-subscriptions", response_model=WebhookSecretView, status_code=201
)
def admin_create_subscription(
    client_id: UUID, body: WebhookCreate, request: Request, ctx: AdminContext, key: Key
):
    return admin_webhooks(request, ctx, client_id).create(body, key)


@admin_router.patch(
    "/{client_id}/webhook-subscriptions/{subscription_id}", response_model=WebhookView
)
def admin_change_subscription(
    client_id: UUID,
    subscription_id: UUID,
    body: WebhookUpdate,
    request: Request,
    ctx: AdminContext,
    key: Key,
):
    return admin_webhooks(request, ctx, client_id).change(subscription_id, body, key)


@admin_router.post(
    "/{client_id}/webhook-subscriptions/{subscription_id}/rotate-secret",
    response_model=WebhookSecretView,
)
def admin_rotate_subscription(
    client_id: UUID,
    subscription_id: UUID,
    body: VersionCommand,
    request: Request,
    ctx: AdminContext,
    key: Key,
):
    return admin_webhooks(request, ctx, client_id).change(subscription_id, body, key, True)


@admin_router.get(
    "/{client_id}/webhook-subscriptions/{subscription_id}/deliveries",
    response_model=tuple[DeliveryView, ...],
)
def admin_deliveries(client_id: UUID, subscription_id: UUID, request: Request, ctx: AdminContext):
    return admin_webhooks(request, ctx, client_id).deliveries(subscription_id)


@admin_router.post(
    "/{client_id}/webhook-subscriptions/{subscription_id}/test",
    response_model=DeliveryAccepted,
    status_code=202,
)
def admin_test(
    client_id: UUID,
    subscription_id: UUID,
    body: EmptyCommand,
    request: Request,
    ctx: AdminContext,
    key: Key,
):
    return admin_webhooks(request, ctx, client_id).test(subscription_id, key)
