"""Publication-driven READY barrier, automatic worker, and the shared registry outbox."""

import time
from uuid import UUID, uuid4

import pytest
from redis import Redis
from sqlalchemy import event, func, select
from test_phase1f_postgres import (
    FakeEmbedding,
    draft,
    ingest,
    step,
)
from test_phase1f_postgres import (
    fixture as fixture,
)
from test_phase1f_postgres import (
    publish as publish_domain,
)
from test_phase1g_persistence_postgres import policies, query, service

from crossborder_compliance.application.knowledge_runtime_services import (
    KnowledgePublicationConsumer,
    KnowledgeRuntimeMaterializationService,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_publication_worker import (
    KnowledgePublicationWorker,
    PublicationEvents,
    RedisRuntimeProjectionCache,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.knowledge_runtime_repository import (
    KnowledgeRuntimeRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresRegistrySyncEventRepository,
)
from crossborder_compliance.infrastructure.registry import ProjectionRegistry

pytestmark = pytest.mark.runtime_smoke


def consumer(f, *, embedding=None):
    ctx = RepositoryContext.system(UUID(f["tenant"]), "test-runtime-worker")
    repo = KnowledgeRuntimeRepository(f["sf"], ctx)
    materializer = KnowledgeRuntimeMaterializationService(
        repo,
        ProjectionRegistry(repo.registry_rows),
        RedisRuntimeProjectionCache(get_settings().redis_url),
        embedding=embedding,
    )
    events = PublicationEvents(PostgresRegistrySyncEventRepository(f["sf"], ctx))
    return repo, materializer, KnowledgePublicationConsumer(events, materializer), events


def pending(f, events):
    rows = events.pending()
    assert rows and rows[0]["object_kind"] == "KNOWLEDGE_VERSION_PUBLISHED"
    return rows[0]


def snapshot(f):
    ident = str(uuid4())
    with f["sf"]() as s, s.begin():
        old = s.get(b.AnalysisSnapshotEntity, f["snapshot"])
        s.add(
            b.AnalysisSnapshotEntity(
                analysis_snapshot_id=ident,
                tenant_id=f["tenant"],
                project_version_id=old.project_version_id,
                analysis_as_of_date=old.analysis_as_of_date,
                snapshot_version=ident,
                provenance_json={"test": "new analysis"},
            )
        )
    from crossborder_compliance.infrastructure.persistence import context_models as c
    from crossborder_compliance.infrastructure.persistence.context_repositories import PostgresContextResolutionRepository
    with f["sf"]() as s:
        original_pin = s.scalar(select(c.AnalysisSnapshotContextPinEntity).where(
            c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == f["snapshot"],
            c.AnalysisSnapshotContextPinEntity.tenant_id == f["tenant"],
        ))
        run_id = UUID(original_pin.context_resolution_run_id)
    PostgresContextResolutionRepository(f["sf"], f["ctx"]).pin_snapshot_context(
        analysis_snapshot_id=UUID(ident), project_id=UUID(f["project"]), context_resolution_run_id=run_id)
    return ident


def test_publish_outbox_is_atomic_and_starts_pending(fixture):
    f = fixture
    v = publish_domain(f)
    repo, _, _, events = consumer(f)
    e = pending(f, events)
    state = repo.runtime_readiness(v["knowledge_version_id"])
    assert state.status == "PENDING" and state.publication_event_id == e["registry_sync_event_id"]
    assert state.index_version_id is None


def test_successful_build_ready_cache_graph_and_new_analysis(fixture):
    f = fixture
    r, p, _ = policies(f)
    v = publish_domain(f)
    repo, _, worker, _ = consumer(f)
    assert worker.run_once()["applied"] == 1
    ready = repo.runtime_readiness(v["knowledge_version_id"])
    assert ready.status == "READY" and all(ready.checks.values())
    assert ready.assets["graph"]["node_count"] == 2
    cache = Redis.from_url(get_settings().redis_url, decode_responses=True)
    key = f"knowledge-runtime:{f['tenant']}:{v['document_id']}:generation"
    assert cache.hget(key, "version") == v["knowledge_version_id"]
    result = service(f, r).retrieve(query(f, p))
    assert {
        i["knowledge_version_id"] for i in result["rag_context_pack"]["evidence_pack"]["items"]
    } == {v["knowledge_version_id"]}


def test_duplicate_publication_event_no_duplicate_assets(fixture):
    f = fixture
    v = publish_domain(f)
    repo, materialize, worker, events = consumer(f)
    e = pending(f, events)
    worker.run_once()
    before = repo.runtime_readiness(v["knowledge_version_id"])
    materialize.consume(e)
    after = repo.runtime_readiness(v["knowledge_version_id"])
    assert before == after
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(k.KnowledgeIndexVersionEntity)
                .where(k.KnowledgeIndexVersionEntity.tenant_id == f["tenant"])
            )
            == 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(g.GRAPH_MODELS["node"])
                .where(g.GRAPH_MODELS["node"].tenant_id == f["tenant"])
            )
            == 2
        )


def test_failed_fts_build_not_ready_then_retry(fixture, monkeypatch):
    f = fixture
    v = publish_domain(f)
    repo, _, worker, _ = consumer(f)
    original = repo.build_index

    def fail(*a, **kw):
        raise ValueError("simulated build failure")

    monkeypatch.setattr(repo, "build_index", fail)
    assert worker.run_once()["retried"] == 1
    assert repo.runtime_readiness(v["knowledge_version_id"]).status == "FAILED"
    monkeypatch.setattr(repo, "build_index", original)
    assert worker.run_once()["applied"] == 1
    assert repo.runtime_readiness(v["knowledge_version_id"]).status == "READY"
    assert worker.run_once()["applied"] == 0


def test_failed_vector_build_not_ready_then_idempotent_retry(fixture):
    from test_phase1f_postgres import embedding_config

    f = fixture
    cfg = embedding_config(f)
    policies(f, vector_weight=0.5, embedding_config_id=cfg)
    v = publish_domain(f)
    repo, materialize, worker, _ = consumer(f)
    assert worker.run_once()["retried"] == 1
    assert repo.runtime_readiness(v["knowledge_version_id"]).status == "FAILED"
    materialize.embedding = FakeEmbedding()
    assert worker.run_once()["applied"] == 1
    ready = repo.runtime_readiness(v["knowledge_version_id"])
    assert ready.status == "READY" and ready.checks["vector"]
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(k.EmbeddingRecordEntity)
                .where(k.EmbeddingRecordEntity.tenant_id == f["tenant"])
            )
            == 2
        )


def test_previous_ready_survives_failed_new_build_and_old_snapshot(fixture, monkeypatch):
    f = fixture
    r, p, _ = policies(f)
    old = publish_domain(f)
    repo, _, worker, _ = consumer(f)
    worker.run_once()
    before = service(f, r).retrieve(query(f, p))
    old_ready = repo.runtime_readiness(old["knowledge_version_id"])
    new = publish_domain(f, doc=old["document_id"])
    original = repo.build_index
    monkeypatch.setattr(
        repo, "build_index", lambda *args: (_ for _ in ()).throw(ValueError("failure"))
    )
    assert worker.run_once()["retried"] == 1
    assert repo.runtime_readiness(old["knowledge_version_id"]) == old_ready
    resumed = service(f, r).retrieve(query(f, p))
    assert {
        i["knowledge_version_id"] for i in resumed["rag_context_pack"]["evidence_pack"]["items"]
    } == {old["knowledge_version_id"]}
    # A genuinely new analysis fails closed until the replacement READY barrier completes.
    new_snapshot = snapshot(f)
    blocked = service(f, r).retrieve(query(f, p, analysis_snapshot_id=new_snapshot))
    assert not blocked["rag_context_pack"]["evidence_pack"]["items"]
    monkeypatch.setattr(repo, "build_index", original)
    worker.run_once()
    assert repo.runtime_readiness(new["knowledge_version_id"]).status == "READY"
    another = snapshot(f)
    latest = service(f, r).retrieve(query(f, p, analysis_snapshot_id=another))
    assert {
        i["knowledge_version_id"] for i in latest["rag_context_pack"]["evidence_pack"]["items"]
    } == {new["knowledge_version_id"]}
    assert (
        before["rag_context_pack"]["evidence_pack"]["manifest"]["knowledge_indexes"]
        == resumed["rag_context_pack"]["evidence_pack"]["manifest"]["knowledge_indexes"]
    )


def test_commit_failure_emits_no_event_and_no_runtime_refresh(fixture):
    f = fixture
    v = draft(f)
    ingest(f, v)
    step(f, v, "validate")
    step(f, v, "submit-review")
    step(f, v, "approve", True)
    _, _, worker, events = consumer(f)
    session_class = f["sf"].class_

    def deny(session):
        raise RuntimeError("injected commit failure")

    event.listen(session_class, "before_commit", deny)
    try:
        with pytest.raises(RuntimeError):
            step(f, v, "publish")
    finally:
        event.remove(session_class, "before_commit", deny)
    assert not events.pending() and worker.run_once()["applied"] == 0
    assert f["repo"].get_version(v["knowledge_version_id"])["lifecycle"] == "APPROVED"
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(g.KnowledgeRuntimePublicationEntity)
                .where(g.KnowledgeRuntimePublicationEntity.tenant_id == f["tenant"])
            )
            == 0
        )


def test_out_of_order_event_cannot_replace_current_version(fixture):
    f = fixture
    old = publish_domain(f)
    new = publish_domain(f, doc=old["document_id"])
    repo, _, worker, _ = consumer(f)
    worker.run_once()
    assert repo.runtime_readiness(new["knowledge_version_id"]).status == "READY"
    assert repo.runtime_readiness(old["knowledge_version_id"]).status != "READY"
    cache = Redis.from_url(get_settings().redis_url, decode_responses=True)
    assert (
        cache.hget(f"knowledge-runtime:{f['tenant']}:{old['document_id']}:generation", "version")
        == new["knowledge_version_id"]
    )


def test_normal_background_publish_requires_no_manual_sync(fixture):
    f = fixture
    repo, _, _, _ = consumer(f)
    worker = KnowledgePublicationWorker(f["sf"], get_settings().redis_url, poll_interval=0.1)
    worker.start()
    try:
        v = publish_domain(f)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            ready = repo.runtime_readiness(v["knowledge_version_id"])
            if ready.status == "READY":
                break
            time.sleep(0.05)
        assert ready.status == "READY"
    finally:
        worker.stop()


def test_tenant_and_event_version_are_validated(fixture):
    f = fixture
    v = publish_domain(f)
    repo, materialize, _, events = consumer(f)
    e = pending(f, events)
    with pytest.raises(ValueError):
        materialize.consume(dict(e, event_version=99))
    outsider = KnowledgeRuntimeRepository(f["sf"], RepositoryContext.system(uuid4()))
    with pytest.raises(LookupError):
        outsider.claim_publication(e)
    assert repo.runtime_readiness(v["knowledge_version_id"]).status == "PENDING"


def test_cache_failure_retries_without_partial_ready_assets(fixture):
    f = fixture
    v = publish_domain(f)
    repo, materialize, worker, _ = consumer(f)
    real = materialize.cache

    class FailedCache:
        def invalidate(self, **kwargs):
            raise TimeoutError("cache unavailable")

    materialize.cache = FailedCache()
    assert worker.run_once()["retried"] == 1
    assert repo.runtime_readiness(v["knowledge_version_id"]).status == "FAILED"
    materialize.cache = real
    assert worker.run_once()["applied"] == 1
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(k.KnowledgeIndexVersionEntity)
                .where(k.KnowledgeIndexVersionEntity.tenant_id == f["tenant"])
            )
            == 1
        )
    assert repo.runtime_readiness(v["knowledge_version_id"]).status == "READY"


def test_concurrent_duplicate_consumers_share_publication_lease(fixture):
    from concurrent.futures import ThreadPoolExecutor

    f = fixture
    v = publish_domain(f)
    repo, materialize, _, events = consumer(f)
    e = pending(f, events)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: materialize.consume(e), range(2)))
    assert repo.runtime_readiness(v["knowledge_version_id"]).status == "READY"
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(k.KnowledgeIndexVersionEntity)
                .where(k.KnowledgeIndexVersionEntity.tenant_id == f["tenant"])
            )
            == 1
        )
