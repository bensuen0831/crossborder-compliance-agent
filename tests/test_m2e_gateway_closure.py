# ruff: noqa: F401,F811 -- imported canonical PostgreSQL fixture graph
"""Gateway closure: actual PostgreSQL/HTTP, durable limits and live admin policy."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_m2e_http import authenticated, credential, gateway  # noqa: F401
from test_m2e_identity_postgres import integrations, issue  # noqa: F401
from test_m2e_webhooks_postgres import receiver, webhook  # noqa: F401

from crossborder_compliance.application.integrations import IntegrationFailure
from crossborder_compliance.domain.integrations import (
    IntegrationPolicy,
    WebhookCreate,
    WebhookUpdate,
)
from crossborder_compliance.infrastructure.persistence.integration_models import (
    IntegrationUsageCounterEntity,
    WebhookDeliveryEntity,
)
from crossborder_compliance.infrastructure.persistence.integrations import (
    PostgresIntegrationRepository,
)
from crossborder_compliance.infrastructure.persistence.models import AuditEventEntity

pytestmark = pytest.mark.runtime_smoke


def test_oauth_failed_attempts_are_durably_rate_limited(gateway):
    app, c, _ = gateway
    made = credential(c)
    app.state.integration_policy = IntegrationPolicy(client_rate_limits={"auth": 2})
    data = {
        "client_id": made["client"]["client_id"],
        "client_secret": "incorrect",
        "grant_type": "client_credentials",
    }
    assert c.post("/api/v1/external/oauth/token", data=data).status_code == 401
    assert c.post("/api/v1/external/oauth/token", data=data).status_code == 401
    denied = c.post("/api/v1/external/oauth/token", data=data)
    assert denied.status_code == 429 and denied.json()["error_code"] == "RATE_LIMITED"
    assert int(denied.headers["Retry-After"]) > 0
    assert "incorrect" not in denied.text


def test_parallel_rate_counter_and_repository_restart(integrations):
    sf, _, repo, service, made = integrations
    p = service.authenticate(issue(service, made).access_token)
    policy = IntegrationPolicy(rate_window_seconds=3600, client_rate_limits={"read": 3})

    def consume(_):
        try:
            PostgresIntegrationRepository(sf, policy).consume(p, "read")
            return True
        except IntegrationFailure as exc:
            assert exc.code == "RATE_LIMITED"
            return False

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(consume, range(6))) == 3
    with pytest.raises(IntegrationFailure, match="RATE_LIMITED"):
        PostgresIntegrationRepository(sf, policy).consume(p, "read")
    with sf() as s:
        counter = s.scalar(
            select(IntegrationUsageCounterEntity).where(
                IntegrationUsageCounterEntity.counter_key == f"rate:client:{p.client_id}:read"
            )
        )
        assert counter.value == 7


def test_admin_options_bindings_disabled_client_and_scope_audit(gateway):
    app, c, tenant = gateway
    auth, made = authenticated(c)
    options = c.get("/api/v1/admin/integration-clients/options")
    assert options.status_code == 200 and "webhook:manage" in options.json()["scopes"]
    created = c.post(
        "/api/v1/external/projects",
        headers={**auth, "Idempotency-Key": uuid4().hex},
        json={"name": uuid4().hex, "facts": {"analysis_as_of_date": "2026-10-09"}},
    )
    assert created.status_code == 201, created.text
    url = "/api/v1/admin/integration-clients/" + made["client"]["client_id"]
    bindings = c.get(url + "/project-bindings")
    assert bindings.json()[0]["project_id"] == created.json()["project_id"]
    assert bindings.json()[0]["binding_type"] == "CREATED_BY_CLIENT"
    disabled = c.patch(
        url,
        headers={"Idempotency-Key": uuid4().hex},
        json={"expected_version": 1, "status": "DISABLED"},
    )
    assert disabled.status_code == 200
    assert c.get(url + "/webhook-subscriptions").status_code == 200
    assert (
        c.get(
            "/api/v1/external/projects/" + created.json()["project_id"] + "/intake", headers=auth
        ).status_code
        == 401
    )
    with app.state.knowledge_session_factory() as s:
        values = s.scalars(
            select(AuditEventEntity).where(AuditEventEntity.tenant_id == str(tenant))
        ).all()
        operations = [x.provenance_json for x in values if x.event_type == "EXTERNAL_OPERATION"]
        assert any(
            x["scope"] == "project:create" and x["actor_id"].startswith("integration:")
            for x in operations
        )
        assert all(made["credential"] not in str(x) for x in operations)


def test_webhook_edits_governed_callback_and_event_filter(webhook):
    _, wh, _, _, _ = webhook
    with receiver("success") as (url, _):
        made = wh.create(
            WebhookCreate(
                callback_url=url, deployment_class="INTERNAL", event_codes=("WORKFLOW_COMPLETED",)
            ),
            uuid4().hex,
        )
        updated = wh.change(
            made.subscription.subscription_id,
            WebhookUpdate(expected_version=1, enabled=True, event_codes=("REVIEW_REQUIRED",)),
            uuid4().hex,
        )
        assert updated.event_codes == ("REVIEW_REQUIRED",) and updated.record_version == 2
        with pytest.raises(IntegrationFailure):
            wh.change(
                updated.subscription_id,
                WebhookUpdate(
                    expected_version=2, enabled=True, callback_url="http://169.254.169.254/latest"
                ),
                uuid4().hex,
            )
        assert wh.list()[0].record_version == 2


def test_interrupted_delivery_new_worker_reclaims_and_old_lease_cannot_finish(webhook):
    sf, wh, worker, _, _ = webhook
    with receiver("success") as (url, requests):
        made = wh.create(
            WebhookCreate(
                callback_url=url, deployment_class="INTERNAL", event_codes=("WORKFLOW_COMPLETED",)
            ),
            uuid4().hex,
        )
        queued = wh.test(made.subscription.subscription_id, uuid4().hex)
        identity, old_owner = worker.claim(WebhookDeliveryEntity, "delivery_id")
        assert identity == queued["delivery_id"]
        with sf() as s, s.begin():
            s.get(WebhookDeliveryEntity, identity).lease_until = datetime.now(UTC) - timedelta(
                seconds=1
            )
        from crossborder_compliance.infrastructure.integration_worker import (
            IntegrationDeliveryWorker,
        )

        restarted = IntegrationDeliveryWorker(SimpleNamespace(state=worker.app.state))
        assert restarted.deliver_webhook()
        worker.finish(WebhookDeliveryEntity, "delivery_id", identity, old_owner, "FAILED")
        view = wh.deliveries(made.subscription.subscription_id)[0]
        assert view.status == "DELIVERED" and view.attempts == 2 and len(requests) == 1


def test_unknown_workflow_has_safe_stable_error(gateway):
    _, c, _ = gateway
    auth, _ = authenticated(c)
    response = c.get("/api/v1/external/workflows/" + str(uuid4()), headers=auth)
    assert response.status_code == 404 and response.json()["error_code"] == "WORKFLOW_NOT_FOUND"
    assert set(response.json()) == {"error_code", "message", "details", "trace_id", "retryable"}
    assert response.headers["X-Correlation-ID"] == response.json()["trace_id"]


def test_failed_oauth_audit_has_server_bound_identity_without_authenticating(gateway):
    app, c, tenant = gateway
    made = credential(c)
    correlation = "failed-oauth-identity"
    response = c.post(
        "/api/v1/external/oauth/token",
        headers={"X-Correlation-ID": correlation},
        data={
            "client_id": made["client"]["client_id"],
            "client_secret": "invalid-attempt",
            "grant_type": "client_credentials",
        },
    )
    assert response.status_code == 401
    with app.state.knowledge_session_factory() as session:
        events = session.scalars(
            select(AuditEventEntity).where(AuditEventEntity.tenant_id == str(tenant))
        ).all()
        audit = next(
            e.provenance_json
            for e in events
            if e.provenance_json.get("correlation_id") == correlation
        )
        assert audit["integration_client_id"] == made["client"]["client_id"]
        assert audit["actor_id"] == "unauthenticated" and audit["authentication_verified"] is False
        assert audit["scope"] == "oauth:token" and audit["outcome"] == "DENIED"
        assert "invalid-attempt" not in str(audit) and made["credential"] not in str(audit)


def test_expired_service_credential_is_denied_by_real_http(gateway):
    app, c, _ = gateway
    response = c.post(
        "/api/v1/admin/integration-clients",
        headers={"Idempotency-Key": uuid4().hex},
        json={
            "display_name": "Expiring service",
            "credential_type": "SERVICE_ACCOUNT",
            "allowed_scopes": ["project:create", "project:read", "intake:write", "model:select"],
        },
    )
    assert response.status_code == 201
    made = response.json()
    auth = {"Authorization": "Bearer " + made["credential"]}
    created = c.post(
        "/api/v1/external/projects",
        headers={**auth, "Idempotency-Key": uuid4().hex},
        json={"name": uuid4().hex, "facts": {"analysis_as_of_date": "2026-10-09"}},
    )
    assert created.status_code == 201, created.text
    url = "/api/v1/external/projects/" + created.json()["project_id"] + "/intake"
    assert c.get(url, headers=auth).status_code == 200
    from crossborder_compliance.infrastructure.persistence.integration_models import (
        IntegrationCredentialEntity,
    )

    with app.state.knowledge_session_factory() as session, session.begin():
        session.get(IntegrationCredentialEntity, made["credential_id"]).expires_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
    denied = c.get(url, headers=auth)
    assert denied.status_code == 401 and denied.json()["error_code"] == "UNAUTHORIZED"
    assert made["credential"] not in denied.text
