from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from crossborder_compliance.application.metadata_services import (
    MetadataLifecycleError,
    MetadataLifecycleService,
    RegistrySyncService,
    SnapshotPinService,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    AdminPublishRecordEntity,
    MetadataDefinitionEntity,
    MetadataVersionEntity,
    RegistrySyncEventEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataOptimisticConcurrencyError,
    PostgresAdminMetadataRepository,
    PostgresRegistrySourceRepository,
    PostgresRegistrySyncEventRepository,
    PostgresSnapshotRegistryPinRepository,
)
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    TenantEntity,
)
from crossborder_compliance.infrastructure.registry import ScenarioRegistry


pytestmark = pytest.mark.runtime_smoke


def _sf():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql"), "real PostgreSQL is mandatory"
    return build_session_factory(settings.database_url)[1]


def _seed_tenant(sf, tenant_id: UUID, name: str) -> None:
    with sf() as session, session.begin():
        session.add(TenantEntity(tenant_id=str(tenant_id), name=name))


def _ctx(tenant_id: UUID, actor: str, scopes: set[str]) -> RepositoryContext:
    return RepositoryContext.user(tenant_id, actor, scopes=scopes)


def _publish_generic_scenario(sf, tenant_id: UUID, code: str):
    creator = _ctx(tenant_id, f"creator-{code}", {"metadata:admin"})
    reviewer = _ctx(tenant_id, f"reviewer-{code}", {"metadata:review"})
    publisher = _ctx(tenant_id, f"publisher-{code}", {"metadata:publish"})

    creator_repo = PostgresAdminMetadataRepository(sf, creator)
    draft = MetadataLifecycleService(creator_repo, creator).create_draft(
        kind="SCENARIO",
        code=code,
        display_name=f"Scenario {code}",
        payload={"marker": code},
    )
    version_id = UUID(str(draft["version_id"]))
    submitted = MetadataLifecycleService(creator_repo, creator).submit_review(
        version_id, expected_record_version=int(draft["record_version"])
    )
    reviewer_repo = PostgresAdminMetadataRepository(sf, reviewer)
    approved = MetadataLifecycleService(reviewer_repo, reviewer).approve(
        version_id, expected_record_version=int(submitted["record_version"])
    )
    publisher_repo = PostgresAdminMetadataRepository(sf, publisher)
    active = MetadataLifecycleService(publisher_repo, publisher).publish(
        version_id, expected_record_version=int(approved["record_version"])
    )
    return {
        "creator": creator,
        "reviewer": reviewer,
        "publisher": publisher,
        "creator_repo": creator_repo,
        "publisher_repo": publisher_repo,
        "draft": draft,
        "active": active,
    }


def test_metadata_lifecycle_publish_refresh_tenant_isolation_and_idempotency() -> None:
    sf = _sf()
    tenant_a, tenant_b = uuid4(), uuid4()
    _seed_tenant(sf, tenant_a, "Phase1C Tenant A")
    _seed_tenant(sf, tenant_b, "Phase1C Tenant B")

    source_a = PostgresRegistrySourceRepository(sf, _ctx(tenant_a, "runtime-a", set()))
    source_b = PostgresRegistrySourceRepository(sf, _ctx(tenant_b, "runtime-b", set()))
    registry_a = ScenarioRegistry(source_a)
    registry_a.refresh()
    assert registry_a.list() == []

    published = _publish_generic_scenario(sf, tenant_a, f"scenario-{uuid4().hex[:8]}")
    assert registry_a.list() == [], "cache must remain stale until sync refresh"

    registry_b = ScenarioRegistry(source_b)
    registry_b.refresh()
    assert registry_b.list() == []

    events = PostgresRegistrySyncEventRepository(sf, _ctx(tenant_a, "sync", set()))
    sync = RegistrySyncService(events, {"SCENARIO": registry_a})
    first = sync.run_once()
    assert first["applied"] == 1
    assert len(registry_a.list()) == 1
    assert registry_a.list()[0]["version_id"] == str(published["active"]["version_id"])

    second = sync.run_once()
    assert second == {"applied": 0, "retried": 0, "ignored": 0}
    assert len(registry_a.list()) == 1


def test_reviewer_separation_invalid_lifecycle_and_optimistic_concurrency() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Lifecycle Tenant")
    actor = _ctx(
        tenant,
        "same-actor",
        {"metadata:admin", "metadata:review", "metadata:publish"},
    )
    repo = PostgresAdminMetadataRepository(sf, actor)
    service = MetadataLifecycleService(repo, actor)
    draft = service.create_draft(
        kind="SCENARIO",
        code=f"review-{uuid4().hex[:8]}",
        display_name="Review Scenario",
        payload={},
    )
    version_id = UUID(str(draft["version_id"]))

    with pytest.raises(MetadataOptimisticConcurrencyError):
        service.update_draft(version_id, payload={"changed": True}, expected_record_version=99)

    with pytest.raises(MetadataLifecycleError):
        service.publish(version_id, expected_record_version=1)

    submitted = service.submit_review(version_id, expected_record_version=1)
    with pytest.raises(MetadataLifecycleError):
        service.approve(
            version_id,
            expected_record_version=int(submitted["record_version"]),
        )

    reviewer = _ctx(tenant, "different-reviewer", {"metadata:review"})
    reviewed = MetadataLifecycleService(
        PostgresAdminMetadataRepository(sf, reviewer), reviewer
    ).approve(
        version_id,
        expected_record_version=int(submitted["record_version"]),
    )
    assert reviewed["lifecycle_status"] == "APPROVED"


def test_future_active_version_is_excluded_and_unique_constraint_enforced() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Effective Tenant")
    context = _ctx(tenant, "system-admin", {"metadata:self-review"})
    repo = PostgresAdminMetadataRepository(sf, context)

    code = f"future-{uuid4().hex[:8]}"
    definition = repo.create_definition(kind="SCENARIO", code=code, display_name="Future")
    future = repo.create_version(
        definition_id=UUID(str(definition["definition_id"])),
        payload={"future": True},
        effective_from=date.today() + timedelta(days=5),
    )
    version_id = UUID(str(future["version_id"]))
    pending = repo.transition(
        version_id,
        target_status="PENDING_REVIEW",
        actor_id="system-admin",
        expected_record_version=1,
    )
    approved = repo.transition(
        version_id,
        target_status="APPROVED",
        actor_id="system-admin",
        expected_record_version=int(pending["record_version"]),
    )
    repo.transition(
        version_id,
        target_status="ACTIVE",
        actor_id="system-admin",
        expected_record_version=int(approved["record_version"]),
    )

    source = PostgresRegistrySourceRepository(sf, context)
    assert all(row["code"] != code for row in source.load_active("SCENARIO"))

    with pytest.raises(IntegrityError):
        repo.create_definition(kind="SCENARIO", code=code, display_name="Duplicate")


class _FailOnceRegistry:
    def __init__(self):
        self.calls = 0

    def refresh(self):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("synthetic refresh failure")


def test_registry_refresh_failure_is_retryable() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Retry Tenant")
    _publish_generic_scenario(sf, tenant, f"retry-{uuid4().hex[:8]}")

    events = PostgresRegistrySyncEventRepository(sf, _ctx(tenant, "sync", set()))
    failing = _FailOnceRegistry()
    sync = RegistrySyncService(events, {"SCENARIO": failing})
    first = sync.run_once()
    assert first["retried"] == 1
    pending = events.pending()
    assert len(pending) == 1
    assert pending[0]["attempts"] == 1

    second = sync.run_once()
    assert second["applied"] == 1
    assert events.pending() == []


def test_publish_transaction_failure_rolls_back_active_pointer_and_publish_record() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Split Brain Tenant")
    creator = _ctx(tenant, "creator", {"metadata:admin"})
    reviewer = _ctx(tenant, "reviewer", {"metadata:review"})
    publisher = _ctx(tenant, "publisher", {"metadata:publish"})

    creator_repo = PostgresAdminMetadataRepository(sf, creator)
    service = MetadataLifecycleService(creator_repo, creator)
    draft = service.create_draft(
        kind="SCENARIO",
        code=f"split-{uuid4().hex[:8]}",
        display_name="Split Brain",
        payload={},
    )
    version_id = UUID(str(draft["version_id"]))
    submitted = service.submit_review(version_id, expected_record_version=1)
    approved = MetadataLifecycleService(
        PostgresAdminMetadataRepository(sf, reviewer), reviewer
    ).approve(version_id, expected_record_version=int(submitted["record_version"]))

    with sf() as session, session.begin():
        session.add(
            RegistrySyncEventEntity(
                registry_sync_event_id=str(uuid4()),
                tenant_id=str(tenant),
                object_kind="SCENARIO",
                object_id=str(draft["definition_id"]),
                version_id=str(draft["version_id"]),
                event_version=1,
                attempts=0,
                status="PENDING",
            )
        )

    publisher_service = MetadataLifecycleService(
        PostgresAdminMetadataRepository(sf, publisher), publisher
    )
    with pytest.raises(IntegrityError):
        publisher_service.publish(
            version_id, expected_record_version=int(approved["record_version"])
        )

    with sf() as session:
        version = session.get(MetadataVersionEntity, str(version_id))
        definition = session.get(
            MetadataDefinitionEntity, str(draft["definition_id"])
        )
        publish_count = session.scalar(
            select(func.count())
            .select_from(AdminPublishRecordEntity)
            .where(
                AdminPublishRecordEntity.tenant_id == str(tenant),
                AdminPublishRecordEntity.version_id == str(version_id),
            )
        )
        assert version is not None and version.lifecycle_status == "APPROVED"
        assert definition is not None and definition.active_version_id is None
        assert publish_count == 0


def _seed_snapshot(sf, tenant: UUID, snapshot_id: UUID) -> None:
    with sf() as session, session.begin():
        session.add(
            AnalysisSnapshotEntity(
                analysis_snapshot_id=str(snapshot_id),
                tenant_id=str(tenant),
                project_version_id=str(uuid4()),
                snapshot_version="1.0",
                analysis_as_of_date=date.today(),
                provenance_json={"source": "phase1c-test"},
            )
        )


def test_old_snapshot_retains_old_registry_version_new_snapshot_gets_new_version() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant, "Snapshot Pin Tenant")
    published = _publish_generic_scenario(sf, tenant, f"pin-{uuid4().hex[:8]}")
    definition_id = UUID(str(published["active"]["definition_id"]))

    source = PostgresRegistrySourceRepository(sf, _ctx(tenant, "runtime", set()))
    active_v1 = source.load_active("SCENARIO")[0]
    snapshot1, snapshot2 = uuid4(), uuid4()
    _seed_snapshot(sf, tenant, snapshot1)
    _seed_snapshot(sf, tenant, snapshot2)
    pin_repo = PostgresSnapshotRegistryPinRepository(
        sf, _ctx(tenant, "snapshot", set())
    )
    pin_service = SnapshotPinService(pin_repo)
    pin_service.pin_resolved(
        analysis_snapshot_id=snapshot1,
        pin_type="SCENARIO",
        logical_key=active_v1["code"],
        resolved=active_v1,
    )

    creator = _ctx(tenant, "creator-v2", {"metadata:admin"})
    reviewer = _ctx(tenant, "reviewer-v2", {"metadata:review"})
    publisher = _ctx(tenant, "publisher-v2", {"metadata:publish"})
    creator_repo = PostgresAdminMetadataRepository(sf, creator)
    v2 = creator_repo.create_version(
        definition_id=definition_id,
        payload={"marker": "v2"},
    )
    submitted = MetadataLifecycleService(creator_repo, creator).submit_review(
        UUID(str(v2["version_id"])), expected_record_version=1
    )
    approved = MetadataLifecycleService(
        PostgresAdminMetadataRepository(sf, reviewer), reviewer
    ).approve(
        UUID(str(v2["version_id"])),
        expected_record_version=int(submitted["record_version"]),
    )
    MetadataLifecycleService(
        PostgresAdminMetadataRepository(sf, publisher), publisher
    ).publish(
        UUID(str(v2["version_id"])),
        expected_record_version=int(approved["record_version"]),
    )
    active_v2 = source.load_active("SCENARIO")[0]
    assert active_v2["version_id"] != active_v1["version_id"]

    pin_service.pin_resolved(
        analysis_snapshot_id=snapshot2,
        pin_type="SCENARIO",
        logical_key=active_v2["code"],
        resolved=active_v2,
    )
    frozen1 = pin_service.frozen_context(snapshot1)
    frozen2 = pin_service.frozen_context(snapshot2)
    key = f"SCENARIO:{active_v1['code']}"
    assert frozen1[key]["version_id"] == active_v1["version_id"]
    assert frozen2[key]["version_id"] == active_v2["version_id"]

    with pytest.raises(MetadataLifecycleError):
        pin_repo.add_pin(
            analysis_snapshot_id=snapshot1,
            pin_type="SCENARIO",
            logical_key=active_v1["code"],
            object_id=definition_id,
            version_id=UUID(str(active_v2["version_id"])),
            version_no=int(active_v2["version_no"]),
        )
