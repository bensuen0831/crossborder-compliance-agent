"""One analysis snapshot keeps its knowledge universe across different subjects."""

from uuid import UUID

import pytest
from test_phase1f_postgres import binding, context, item, publish, scope
from test_phase1f_postgres import fixture as fixture

from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)

pytestmark = pytest.mark.runtime_smoke


def test_snapshot_new_subject_retains_previously_active_version(fixture):
    f = fixture
    run = context(f, [f["a"], f["b"]], [f["a"], f["b"]])
    ia, ib = item(f, f["a"], run["version"]), item(f, f["b"], run["version"])
    a = publish(f)
    old_b = publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    first = scope(f, subject_type="DATA_ITEM", subject_id=ia, snapshot_id=f["snapshot"])
    assert first.filter_spec.version_filter == (a["knowledge_version_id"],)
    new_b = publish(f, [binding(f, dimensions={"product": [f["b"]]})], doc=old_b["document_id"])
    second = scope(f, subject_type="DATA_ITEM", subject_id=ib, snapshot_id=f["snapshot"])
    assert second.filter_spec.version_filter == (old_b["knowledge_version_id"],)
    assert new_b["knowledge_version_id"] not in second.filter_spec.version_filter


def test_snapshot_empty_knowledge_universe_cannot_refresh_for_new_subject(fixture):
    f = fixture
    ident = item(f, f["a"], 1)
    first = scope(f, snapshot_id=f["snapshot"])
    assert not first.filter_spec.version_filter
    publish(f)
    second = scope(f, subject_type="DATA_ITEM", subject_id=ident, snapshot_id=f["snapshot"])
    assert not second.filter_spec.version_filter


def test_snapshot_creation_loser_rechecks_its_own_permission(fixture):
    f = fixture
    public = publish(f)
    secret = publish(f, [binding(f, permissions=["read:secret"])])
    privileged = RepositoryContext.user(
        UUID(f["tenant"]), "privileged", {"read:internal", "read:secret"}
    )
    winner = PostgresKnowledgeRepository(f["sf"], privileged)

    class CreationRace(PostgresKnowledgeRepository):
        def save_scope(self, payload):
            KnowledgeScopeResolver(winner, privileged).resolve(
                f["project"], snapshot_id=f["snapshot"]
            )
            return super().save_scope(payload)

    loser = CreationRace(f["sf"], f["ctx"])
    result = KnowledgeScopeResolver(loser, f["ctx"]).resolve(
        f["project"], snapshot_id=f["snapshot"]
    )
    assert result.filter_spec.version_filter == (public["knowledge_version_id"],)
    assert secret["knowledge_version_id"] not in result.filter_spec.version_filter
