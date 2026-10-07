"""One analysis snapshot keeps its knowledge universe across different subjects."""

from uuid import UUID, uuid4

import pytest
from test_phase1f_postgres import binding, context, item, publish, scope
from test_phase1f_postgres import fixture as fixture

from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import metadata_models as m
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
    with pytest.raises(LookupError):
        scope(f, subject_type="DATA_ITEM", subject_id=str(uuid4()), snapshot_id=f["snapshot"])
    assert f["repo"].snapshot_knowledge_filters(f["snapshot"]) is None
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


def test_snapshot_domain_scope_preserves_formal_item_minimal_products(fixture):
    f = fixture
    run = context(f, [f["domain"]], [f["domain"]])
    ia, ib = item(f, f["a"], run["version"]), item(f, f["b"], run["version"])
    a = publish(f)
    bb = publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    first = scope(f, subject_type="DATA_ITEM", subject_id=ia, snapshot_id=f["snapshot"])
    second = scope(f, subject_type="DATA_ITEM", subject_id=ib, snapshot_id=f["snapshot"])
    assert first.filter_spec.version_filter == (a["knowledge_version_id"],)
    assert second.filter_spec.version_filter == (bb["knowledge_version_id"],)


def test_snapshot_new_subject_uses_frozen_product_hierarchy(fixture):
    f = fixture
    run = context(f, [f["a"], f["b"]], [f["a"], f["b"]])
    ia, ib = item(f, f["a"], run["version"]), item(f, f["b"], run["version"])
    shared = publish(f, [binding(f, "DOMAIN_SHARED", {"product_family": [f["family"]]})])
    scope(f, subject_type="DATA_ITEM", subject_id=ia, snapshot_id=f["snapshot"])
    with f["sf"]() as s, s.begin():
        # A published registry hierarchy change must not rewrite an existing analysis.
        product = s.get(m.MetadataDefinitionEntity, f["b"])
        product.parent_definition_id = f["domain"]
    resumed = scope(f, subject_type="DATA_ITEM", subject_id=ib, snapshot_id=f["snapshot"])
    assert resumed.filter_spec.version_filter == (shared["knowledge_version_id"],)
    assert resumed.allowed_product_family_ids == (f["family"],)
    from test_phase1g_publication_postgres import snapshot
    fresh_snapshot = snapshot(f)
    fresh = scope(f, subject_type="DATA_ITEM", subject_id=ib, snapshot_id=fresh_snapshot)
    assert not fresh.filter_spec.version_filter
