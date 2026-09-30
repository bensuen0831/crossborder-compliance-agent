from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from crossborder_compliance.application.registry_ports import (
    AdminMetadataRepositoryPort,
    RegistryPort,
    RegistrySyncEventRepositoryPort,
    SnapshotRegistryPinRepositoryPort,
)
from crossborder_compliance.domain.metadata import GovernanceStatus
from crossborder_compliance.domain.security import RepositoryContext


class AdminAuthorizationError(PermissionError):
    pass


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    GovernanceStatus.DRAFT.value: {GovernanceStatus.PENDING_REVIEW.value, GovernanceStatus.ARCHIVED.value},
    GovernanceStatus.PENDING_REVIEW.value: {GovernanceStatus.APPROVED.value, GovernanceStatus.DRAFT.value},
    GovernanceStatus.APPROVED.value: {GovernanceStatus.ACTIVE.value, GovernanceStatus.ARCHIVED.value},
    GovernanceStatus.ACTIVE.value: {GovernanceStatus.SUPERSEDED.value, GovernanceStatus.EXPIRED.value, GovernanceStatus.ARCHIVED.value},
    GovernanceStatus.SUPERSEDED.value: {GovernanceStatus.ARCHIVED.value},
    GovernanceStatus.EXPIRED.value: {GovernanceStatus.ARCHIVED.value},
    GovernanceStatus.ARCHIVED.value: set(),
}


@dataclass(frozen=True, slots=True)
class AdminActionPolicy:
    draft_scope: str = "metadata:admin"
    review_scope: str = "metadata:review"
    publish_scope: str = "metadata:publish"

    def require(self, context: RepositoryContext, scope: str) -> None:
        scopes = context.permission.scopes
        if not context.permission.system and scope not in scopes:
            raise AdminAuthorizationError(f"missing required admin scope: {scope}")


class MetadataLifecycleService:
    def __init__(self, repository: AdminMetadataRepositoryPort, context: RepositoryContext):
        self._repository = repository
        self._context = context
        self._policy = AdminActionPolicy()

    def create_draft(self, *, kind: str, code: str, display_name: str, payload: dict[str, object], parent_definition_id: UUID | None = None) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        definition = self._repository.create_definition(
            kind=kind, code=code, display_name=display_name, parent_definition_id=parent_definition_id
        )
        return self._repository.create_version(definition_id=UUID(str(definition["definition_id"])), payload=payload)

    def update_draft(self, version_id: UUID, *, payload: dict[str, object], expected_record_version: int) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        return self._repository.update_draft(
            version_id, payload=payload, expected_record_version=expected_record_version
        )

    def _transition(self, version_id: UUID, *, target_status: str, expected_record_version: int, required_scope: str) -> dict[str, object]:
        self._policy.require(self._context, required_scope)
        return self._repository.transition(
            version_id,
            target_status=target_status,
            actor_id=self._context.permission.actor_id,
            expected_record_version=expected_record_version,
        )

    def submit_review(self, version_id: UUID, *, expected_record_version: int) -> dict[str, object]:
        return self._transition(
            version_id,
            target_status=GovernanceStatus.PENDING_REVIEW.value,
            expected_record_version=expected_record_version,
            required_scope=self._policy.draft_scope,
        )

    def approve(self, version_id: UUID, *, expected_record_version: int) -> dict[str, object]:
        return self._transition(
            version_id,
            target_status=GovernanceStatus.APPROVED.value,
            expected_record_version=expected_record_version,
            required_scope=self._policy.review_scope,
        )

    def reject(self, version_id: UUID, *, expected_record_version: int) -> dict[str, object]:
        return self._transition(
            version_id,
            target_status=GovernanceStatus.DRAFT.value,
            expected_record_version=expected_record_version,
            required_scope=self._policy.review_scope,
        )

    def publish(self, version_id: UUID, *, expected_record_version: int) -> dict[str, object]:
        return self._transition(
            version_id,
            target_status=GovernanceStatus.ACTIVE.value,
            expected_record_version=expected_record_version,
            required_scope=self._policy.publish_scope,
        )

    def supersede(self, version_id: UUID, *, expected_record_version: int) -> dict[str, object]:
        return self._transition(
            version_id,
            target_status=GovernanceStatus.SUPERSEDED.value,
            expected_record_version=expected_record_version,
            required_scope=self._policy.publish_scope,
        )

    def archive(self, version_id: UUID, *, expected_record_version: int) -> dict[str, object]:
        return self._transition(
            version_id,
            target_status=GovernanceStatus.ARCHIVED.value,
            expected_record_version=expected_record_version,
            required_scope=self._policy.publish_scope,
        )


class RegistrySyncService:
    def __init__(
        self,
        event_repository: RegistrySyncEventRepositoryPort,
        registries: dict[str, RegistryPort[dict[str, object]]],
    ):
        self._events = event_repository
        self._registries = registries

    def run_once(self, limit: int = 100) -> dict[str, int]:
        applied = retried = ignored = 0
        for event in self._events.pending(limit=limit):
            event_id = UUID(str(event["registry_sync_event_id"]))
            kind = str(event["object_kind"])
            registry = self._registries.get(kind)
            if registry is None:
                self._events.mark_applied(event_id)
                ignored += 1
                continue
            try:
                registry.refresh()
            except Exception as exc:
                self._events.mark_retry(event_id, f"{type(exc).__name__}: {exc}")
                retried += 1
            else:
                self._events.mark_applied(event_id)
                applied += 1
        return {"applied": applied, "retried": retried, "ignored": ignored}


class SnapshotPinService:
    def __init__(self, pins: SnapshotRegistryPinRepositoryPort):
        self._pins = pins

    def pin_resolved(
        self,
        *,
        analysis_snapshot_id: UUID,
        pin_type: str,
        logical_key: str,
        resolved: dict[str, object],
    ) -> None:
        self._pins.add_pin(
            analysis_snapshot_id=analysis_snapshot_id,
            pin_type=pin_type,
            logical_key=logical_key,
            object_id=UUID(str(resolved["definition_id"])),
            version_id=UUID(str(resolved["version_id"])),
            version_no=int(resolved["version_no"]),
        )

    def frozen_context(self, analysis_snapshot_id: UUID) -> dict[str, dict[str, object]]:
        return {
            f"{row['pin_type']}:{row['logical_key']}": row
            for row in self._pins.list_pins(analysis_snapshot_id)
        }


def lifecycle_transition_allowed(current_status: str, target_status: str) -> bool:
    return target_status in _ALLOWED_TRANSITIONS.get(current_status, set())


def effective_on(row: dict[str, object], as_of: date) -> bool:
    start = row.get("effective_from")
    end = row.get("effective_to")
    if start and start > as_of:
        return False
    if end and end < as_of:
        return False
    return True
