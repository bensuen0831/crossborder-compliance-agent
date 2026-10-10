"""Northbound integration identities and technical delivery, never legal state."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin, utcnow


class IntegrationAuditMixin(TenantAuditMixin):
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(200), nullable=False)


class IntegrationClientEntity(IntegrationAuditMixin, Base):
    __tablename__ = "integration_clients"
    client_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    allowed_scopes_json: Mapped[list] = mapped_column(JSON, nullable=False)
    credential_type: Mapped[str] = mapped_column(String(40), nullable=False)
    credential_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntegrationCredentialEntity(Base):
    __tablename__ = "integration_credentials"
    credential_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("integration_clients.client_id", ondelete="RESTRICT"), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    credential_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationAccessTokenEntity(Base):
    __tablename__ = "integration_access_tokens"
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("integration_clients.client_id", ondelete="RESTRICT"), nullable=False)
    credential_id: Mapped[str] = mapped_column(ForeignKey("integration_credentials.credential_id", ondelete="RESTRICT"), nullable=False)
    scopes_json: Mapped[list] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationProjectBindingEntity(IntegrationAuditMixin, Base):
    __tablename__ = "integration_project_bindings"
    __table_args__ = (UniqueConstraint("client_id", "project_id", name="uq_integration_project_binding"),)
    binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("integration_clients.client_id", ondelete="RESTRICT"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False)
    binding_type: Mapped[str] = mapped_column(String(40), nullable=False)


class WebhookSubscriptionEntity(IntegrationAuditMixin, Base):
    __tablename__ = "webhook_subscriptions"
    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("integration_clients.client_id", ondelete="RESTRICT"), nullable=False)
    callback_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    deployment_class: Mapped[str] = mapped_column(String(40), nullable=False)
    event_codes_json: Mapped[list] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    secret_ref: Mapped[str] = mapped_column(String(512), nullable=False)


class WebhookDeliveryEntity(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (UniqueConstraint("subscription_id", "event_id", name="uq_webhook_event_delivery"),)
    delivery_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("webhook_subscriptions.subscription_id", ondelete="RESTRICT"), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.workflow_run_id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(120))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(36))


class IntegrationWorkflowDeliveryEntity(Base):
    __tablename__ = "integration_workflow_deliveries"
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.workflow_run_id", ondelete="RESTRICT"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("integration_clients.client_id", ondelete="RESTRICT"), nullable=False)
    credential_id: Mapped[str] = mapped_column(ForeignKey("integration_credentials.credential_id", ondelete="RESTRICT"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("analysis_snapshots.analysis_snapshot_id", ondelete="RESTRICT"), nullable=False)
    scopes_json: Mapped[list] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(120))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(36))


class IntegrationUsageCounterEntity(Base):
    __tablename__ = "integration_usage_counters"
    counter_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    window_start: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


MODELS = (IntegrationClientEntity, IntegrationCredentialEntity, IntegrationAccessTokenEntity,
          IntegrationProjectBindingEntity, WebhookSubscriptionEntity, WebhookDeliveryEntity,
          IntegrationWorkflowDeliveryEntity, IntegrationUsageCounterEntity)
