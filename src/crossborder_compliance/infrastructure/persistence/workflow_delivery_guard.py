"""Tenant-scoped delivery serialization using existing PostgreSQL, no schema."""

from contextlib import contextmanager
from hashlib import sha256

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from crossborder_compliance.application.workflow_skeleton import WorkflowDeliveryRetryableFailure
from crossborder_compliance.infrastructure.persistence.models import WorkflowRunEntity


class PostgresWorkflowDeliveryGuard:
    def __init__(self, sessions, context, lock_timeout_seconds=30):
        self.sessions, self.context = sessions, context
        if not 0 < lock_timeout_seconds <= 3600:
            raise ValueError("bounded delivery lock timeout required")
        self.timeout = int(lock_timeout_seconds * 1000)

    @contextmanager
    def acquire(self, workflow_run_id):
        tenant = str(self.context.tenant_id)
        with self.sessions() as s, s.begin():
            run = s.scalar(
                select(WorkflowRunEntity).where(
                    WorkflowRunEntity.workflow_run_id == str(workflow_run_id),
                    WorkflowRunEntity.tenant_id == tenant,
                )
            )
            if run is None:
                raise PermissionError("workflow delivery not found")
            key = int(
                sha256(f"WORKFLOW_DELIVERY:{tenant}:{workflow_run_id}".encode()).hexdigest()[:15],
                16,
            )
            s.execute(
                text("SELECT set_config('lock_timeout', :timeout, true)"),
                {"timeout": f"{self.timeout}ms"},
            )
            try:
                s.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            except DBAPIError as exc:
                if getattr(exc.orig, "sqlstate", None) == "55P03":
                    raise WorkflowDeliveryRetryableFailure(
                        "WORKFLOW_DELIVERY_LOCK_TIMEOUT"
                    ) from exc
                raise
            yield
