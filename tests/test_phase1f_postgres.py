from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from crossborder_compliance.application.context_services import ContextResolutionService
from crossborder_compliance.application.knowledge_services import (
    EmbeddingFoundationService,
    KnowledgeIngestionService,
    KnowledgeScopeResolver,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_worker import (
    KnowledgeIngestionWorker,
    RedisKnowledgeTaskQueue,
)
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.context_repositories import (
    PostgresContextResolutionRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresRegistrySyncEventRepository,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)

pytestmark = pytest.mark.runtime_smoke


def uid():
    return str(uuid4())


class Storage:
    def __init__(self):
        self.data = {}

    def put(self, *, object_key, content, content_type):
        self.data[object_key] = content
        return "test://" + object_key

    def get(self, ref):
        return self.data[ref[7:]]


def metadata(sf, tenant, kind, parent=None):
    d, v = uid(), uid()
    with sf() as s, s.begin():
        row = m.MetadataDefinitionEntity(
            definition_id=d,
            tenant_id=tenant,
            kind=kind,
            code=d,
            display_name="Generic " + kind,
            parent_definition_id=parent,
        )
        s.add(row)
        s.flush()
        s.add(
            m.MetadataVersionEntity(
                version_id=v,
                tenant_id=tenant,
                definition_id=d,
                version_no=1,
                lifecycle_status="ACTIVE",
                payload_json={},
                created_by="fixture",
                approved_by="fixture",
            )
        )
        s.flush()
        row.active_version_id = v
    return d


@pytest.fixture
def fixture():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    sf = build_session_factory(settings.database_url)[1]
    tenant, project, pv, snapshot, juri, col, cv = [uid() for _ in range(7)]
    with sf() as s, s.begin():
        s.add(b.TenantEntity(tenant_id=tenant, name="Generic Tenant"))
        s.flush()
        s.add(b.ProjectEntity(project_id=project, tenant_id=tenant, name="Generic Project"))
        s.flush()
        s.add(
            b.ProjectVersionEntity(
                project_version_id=pv,
                tenant_id=tenant,
                project_id=project,
                version_no=1,
                intake_json={},
            )
        )
        s.flush()
        s.add(
            b.AnalysisSnapshotEntity(
                analysis_snapshot_id=snapshot,
                tenant_id=tenant,
                project_version_id=pv,
                analysis_as_of_date=date.today(),
                snapshot_version="1",
                provenance_json={"fixture": True},
            )
        )
        s.add(
            b.JurisdictionEntity(
                jurisdiction_id=juri,
                tenant_id=tenant,
                code="GEN-" + juri,
                name="Generic jurisdiction",
            )
        )
        s.add(
            m.KnowledgeCollectionEntity(
                knowledge_collection_id=col,
                tenant_id=tenant,
                code=col,
                display_name="Generic collection",
            )
        )
        s.flush()
        s.add(
            m.KnowledgeCollectionVersionEntity(
                knowledge_collection_version_id=cv,
                tenant_id=tenant,
                knowledge_collection_id=col,
                version_no=1,
                lifecycle_status="ACTIVE",
                payload_json={},
            )
        )
    domain = metadata(sf, tenant, "PRODUCT_DOMAIN")
    category = metadata(sf, tenant, "PRODUCT_CATEGORY", domain)
    family = metadata(sf, tenant, "PRODUCT_FAMILY", category)
    a = metadata(sf, tenant, "PRODUCT", family)
    bb = metadata(sf, tenant, "PRODUCT", family)
    tag = metadata(sf, tenant, "PRODUCT_TAG")
    scenario = metadata(sf, tenant, "SCENARIO")
    industry = metadata(sf, tenant, "INDUSTRY")
    data_category = metadata(sf, tenant, "DATA_CATEGORY")
    group = metadata(sf, tenant, "JURISDICTION_GROUP")
    with sf() as s, s.begin():
        s.add(
            m.MetadataBindingEntity(
                binding_id=uid(),
                tenant_id=tenant,
                binding_type="PRODUCT_TAG",
                source_definition_id=a,
                target_definition_id=tag,
                scope_json={},
            )
        )
    ctx = RepositoryContext.user(UUID(tenant), "author", {"knowledge:admin", "read:internal"})
    reviewer = RepositoryContext.user(
        UUID(tenant), "reviewer", {"knowledge:admin", "read:internal"}
    )
    repo = PostgresKnowledgeRepository(sf, ctx)
    other = PostgresKnowledgeRepository(sf, reviewer)
    f = dict(
        sf=sf,
        tenant=tenant,
        project=project,
        snapshot=snapshot,
        juri=juri,
        col=col,
        cv=cv,
        a=a,
        b=bb,
        domain=domain,
        category=category,
        family=family,
        tag=tag,
        scenario=scenario,
        industry=industry,
        data_category=data_category,
        group=group,
        ctx=ctx,
        repo=repo,
        reviewer=other,
        storage=Storage(),
    )
    context(f, [a], [a])
    source = repo.create_source(
        dict(
            collection_id=col,
            code=uid(),
            source_type="OFFICIAL_LEGISLATION",
            canonical_url="https://generic.example/official.json",
            jurisdiction_refs=[juri],
            trust_level="APPROVED",
            language="en",
            validation_status="VALIDATED",
            provenance={"fixture": "Generic Official Regulation"},
        )
    )
    f["source"] = source["source_id"]
    return f


def context(f, selected, detected):
    result = ContextResolutionService(PostgresContextResolutionRepository(f["sf"], f["ctx"])).run(
        UUID(f["project"]),
        selected_product_scope=tuple(UUID(x) for x in selected),
        detected_product_scope=tuple(UUID(x) for x in detected),
        selected_scenarios=(UUID(f["scenario"]),),
        detected_scenarios=(UUID(f["scenario"]),),
        jurisdictions=(
            {
                "jurisdiction_id": f["juri"],
                "input_value": "Generic registered location",
                "context_type": "STORAGE",
                "precision": "COUNTRY",
                "source": "APPROVED_METADATA",
                "confidence": 1,
            },
        ),
    )

    # Initialize the explicit E pin before F performs any snapshot read. Each
    # subsequent fixture input gets a new snapshot, never overwrites an old pin.
    repo = PostgresContextResolutionRepository(f["sf"], f["ctx"])
    with f["sf"]() as session, session.begin():
        existing = session.scalar(select(c.AnalysisSnapshotContextPinEntity).where(
            c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == f["snapshot"]))
        if existing is not None:
            previous = session.get(b.AnalysisSnapshotEntity, f["snapshot"])
            f["snapshot"] = uid()
            session.add(b.AnalysisSnapshotEntity(analysis_snapshot_id=f["snapshot"], tenant_id=f["tenant"],
                project_version_id=previous.project_version_id, snapshot_version=str(result["version"]),
                analysis_as_of_date=previous.analysis_as_of_date, provenance_json={"fixture": True}))
    repo.pin_snapshot_context(analysis_snapshot_id=UUID(f["snapshot"]), project_id=UUID(f["project"]),
        context_resolution_run_id=UUID(result["context_resolution_run_id"]))
    return result


def binding(f, scope="PRODUCT_SPECIFIC", dimensions=None, permissions=None, **extra):
    return dict(
        scope_type=scope,
        dimensions=dimensions if dimensions is not None else {"product": [f["a"]]},
        permission_scopes=permissions or [],
        provenance={"fixture": True},
        **extra,
    )


def draft(f, doc=None, **extra):
    r = f["repo"]
    doc = (
        doc
        or r.create_document(
            {"source_id": f["source"], "display_name": "Generic Official Regulation"}
        )["document_id"]
    )
    return r.create_version(
        doc,
        dict(
            collection_version_id=f["cv"],
            language="en",
            effective_from=date.today().isoformat(),
            provenance={"fixture": True},
            **extra,
        ),
    )


def inputs(f, bindings=None, nodes=None):
    return dict(
        idempotency_key=uid(),
        nodes=nodes
        or [
            {
                "node_type": "ACT",
                "canonical_locator": "act",
                "original_text": "Generic Official Regulation",
            },
            {
                "node_type": "ARTICLE",
                "canonical_locator": "act/article/1",
                "parent_locator": "act",
                "original_text": "Generic rule original text",
                "official_number": "1",
            },
        ],
        bindings=bindings if bindings is not None else [binding(f)],
        strategy="STRUCTURE_AWARE",
    )


def ingest(f, v, payload=None):
    service = KnowledgeIngestionService(f["repo"], storage=f["storage"])
    run = service.ingest(v["knowledge_version_id"], payload or inputs(f))
    service.work(run["ingestion_run_id"])
    return run


def step(f, v, action, reviewer=False):
    r = f["reviewer"] if reviewer else f["repo"]
    version = r.get_version(v["knowledge_version_id"])
    return r.governance(version["knowledge_version_id"], action, version["record_version"])


def publish(f, bindings=None, doc=None, **extra):
    v = draft(f, doc, **extra)
    ingest(f, v, inputs(f, bindings))
    step(f, v, "validate")
    step(f, v, "submit-review")
    step(f, v, "approve", True)
    return step(f, v, "publish")


def scope(f, **kw):
    if kw.get("subject_type") in {"DATA_ITEM", "DATA_FLOW"} and "snapshot_id" not in kw:
        kw["snapshot_id"] = f["snapshot"]
    return KnowledgeScopeResolver(f["repo"], f["ctx"]).resolve(f["project"], **kw)


def count(f, model):
    with f["sf"]() as s:
        return s.scalar(
            select(func.count()).select_from(model).where(model.tenant_id == f["tenant"])
        )


def test_source_crud_permission_tenant_optimistic(fixture):
    f = fixture
    r = f["repo"]
    src = r.get_source(f["source"])
    assert src["source_type"] == "OFFICIAL_LEGISLATION"
    assert r.update_source(f["source"], {"enabled": False}, 1)["record_version"] == 2
    with pytest.raises(OptimisticConcurrencyError):
        r.update_source(f["source"], {"enabled": True}, 1)
    with pytest.raises(PermissionError):
        PostgresKnowledgeRepository(
            f["sf"], RepositoryContext.user(UUID(f["tenant"]), "reader")
        ).get_source(f["source"])
    with pytest.raises(LookupError):
        PostgresKnowledgeRepository(
            f["sf"], RepositoryContext.user(uuid4(), "outsider", {"knowledge:admin"})
        ).get_source(f["source"])
    with pytest.raises(ValueError):
        r.create_source(dict(src, canonical_url="http://127.0.0.1"))


def test_lifecycle_quality_review_provenance(fixture):
    f = fixture
    v = draft(f)
    with pytest.raises(ValueError):
        step(f, v, "publish")
    ingest(f, v)
    validated = step(f, v, "validate")
    assert validated["lifecycle"] == "VALIDATED"
    quality = f["repo"].list_component(v["knowledge_version_id"], "quality")[0]
    assert quality["status"] == "PASS" and len(quality["checks"]) == 7
    step(f, v, "submit-review")
    with pytest.raises(ValueError):
        step(f, v, "approve")
    step(f, v, "approve", True)
    active = step(f, v, "publish")
    assert active["lifecycle"] == "ACTIVE"
    assert count(f, m.AdminReviewTaskEntity) == 1 and count(f, m.AdminPublishRecordEntity) == 1
    nodes = f["repo"].list_component(v["knowledge_version_id"], "structure")
    chunks = f["repo"].list_component(v["knowledge_version_id"], "chunks")
    assert nodes[1]["parent_node_id"] == nodes[0]["structure_node_id"]
    assert all(
        n["regulatory_structure_node_id"] == n["structure_node_id"]
        and n["source_trace_json"]["content_hash"]
        for n in nodes
    )
    assert all(ch["structure_node_ids"] and ch["citation_refs"] for ch in chunks)
    assert count(f, b.RegulatoryStructureNodeEntity) == len(nodes) == count(f, b.CitationEntity)
    with f["sf"]() as s:
        evidence = s.scalar(
            select(b.EvidenceReferenceEntity).where(
                b.EvidenceReferenceEntity.tenant_id == f["tenant"]
            )
        )
        assert (
            "official_source" in evidence.source_ref and "original_language" in evidence.source_ref
        )


def test_failed_quality_cannot_activate(fixture):
    f = fixture
    f["repo"].update_source(f["source"], {"validation_status": "PENDING"}, 1)
    v = draft(f)
    ingest(f, v)
    assert step(f, v, "validate")["quality_status"] == "FAILED"
    assert f["repo"].list_component(v["knowledge_version_id"], "quality")[0]["status"] == "FAILED"
    with pytest.raises(ValueError):
        step(f, v, "submit-review")
    assert f["repo"].get_version(v["knowledge_version_id"])["lifecycle"] == "INGESTED"


def test_case_a_product_hierarchy_global_shared_and_permission(fixture):
    f = fixture
    a = publish(f)
    bb = publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    shared = publish(f, [binding(f, "DOMAIN_SHARED", {"product_domain": [f["domain"]]})])
    global_ = publish(f, [binding(f, "GLOBAL", {})])
    secret = publish(f, [binding(f, permissions=["read:secret"])])
    result = scope(f)
    assert set(result.filter_spec.version_filter) == {
        a["knowledge_version_id"],
        shared["knowledge_version_id"],
        global_["knowledge_version_id"],
    }
    assert (
        bb["knowledge_version_id"] not in result.filter_spec.version_filter
        and secret["knowledge_version_id"] not in result.filter_spec.version_filter
    )
    secret_binding = f["repo"].list_component(secret["knowledge_version_id"], "bindings")[0][
        "binding_id"
    ]
    assert secret_binding not in str(result.excluded_bindings)
    assert (
        result.allowed_product_ids == (f["a"],)
        and result.allowed_product_family_ids == (f["family"],)
        and result.allowed_product_tag_ids == (f["tag"],)
    )
    mixed = publish(
        f, [binding(f, dimensions={"product": [f["b"]], "product_domain": [f["domain"]]})]
    )
    assert mixed["knowledge_version_id"] not in scope(f).filter_spec.version_filter


def item(f, product, version):
    ident = uid()
    with f["sf"]() as s, s.begin():
        s.add(
            b.DataItemEntity(
                data_item_id=ident,
                tenant_id=f["tenant"],
                project_id=f["project"],
                name=ident,
            )
        )
        s.flush()
        s.add(
            c.DataItemResolutionDetailEntity(
                data_item_id=ident,
                tenant_id=f["tenant"],
                display_name="Generic item",
                confidence=1,
                validation_status="VALIDATED",
                version=version,
            )
        )
        if product:
            link_id = uid()
            s.add(b.DataItemProductLinkEntity(data_item_product_link_id=link_id,
                tenant_id=f["tenant"], data_item_id=ident, product_ref=product))
            s.flush()
            s.add(c.DataItemProductLinkDetailEntity(data_item_product_link_id=link_id,
                tenant_id=f["tenant"], data_inventory_version=version, product_definition_id=product,
                relationship_type="PRIMARY", confidence=1.0, source_trace_ids_json=[]))
    return ident


def test_case_b_multi_product_minimal_item_flow(fixture):
    f = fixture
    run = context(f, [f["a"], f["b"]], [f["a"], f["b"]])
    a = publish(f)
    bb = publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    ia = item(f, f["a"], run["version"])
    ib = item(f, f["b"], run["version"])
    unknown = item(f, None, run["version"])
    assert scope(f, subject_type="DATA_ITEM", subject_id=ia).filter_spec.version_filter == (
        a["knowledge_version_id"],
    )
    assert scope(f, subject_type="DATA_ITEM", subject_id=ib).filter_spec.version_filter == (
        bb["knowledge_version_id"],
    )
    assert scope(f, subject_type="DATA_ITEM", subject_id=unknown).review_required
    n1, n2, flow = uid(), uid(), uid()
    with f["sf"]() as s, s.begin():
        for ident in (n1, n2):
            s.add(
                b.DataFlowNodeEntity(
                    flow_node_id=ident,
                    tenant_id=f["tenant"],
                    project_id=f["project"],
                    node_type="SYSTEM",
                    display_name="Generic node",
                )
            )
        s.flush()
        s.add(
            b.DataFlowEdgeEntity(
                flow_edge_id=flow,
                tenant_id=f["tenant"],
                project_id=f["project"],
                source_node_id=n1,
                target_node_id=n2,
                flow_type="TRANSFER",
            )
        )
        s.flush()
        s.add(
            c.DataFlowEdgeDetailEntity(
                flow_edge_id=flow,
                tenant_id=f["tenant"],
                direction="SOURCE_TO_TARGET",
                confidence=1,
                validation_status="VALIDATED",
                version=run["version"],
            )
        )
        link_id = uid()
        s.add(b.DataItemFlowLinkEntity(link_id=link_id, tenant_id=f["tenant"], data_item_id=ia, flow_edge_id=flow))
        s.flush()
        s.add(c.DataItemFlowLinkDetailEntity(link_id=link_id, tenant_id=f["tenant"],
            data_inventory_version=run["version"], relationship_type="TRANSFER", confidence=1.0))
    assert scope(f, subject_type="DATA_FLOW", subject_id=flow).filter_spec.version_filter == (
        a["knowledge_version_id"],
    )


def test_case_c_conflict_fail_safe(fixture):
    f = fixture
    publish(f)
    publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    global_ = publish(f, [binding(f, "GLOBAL", {})])
    context(f, [f["a"]], [f["b"]])
    result = scope(f)
    assert result.review_required and "UNRESOLVED_PRODUCT_SCOPE" in result.unresolved_scopes
    assert result.filter_spec.version_filter == (global_["knowledge_version_id"],)


def test_case_d_document_formal_context_only(fixture):
    f = fixture
    context(f, [], [f["a"]])
    a = publish(f)
    publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    assert scope(f).filter_spec.version_filter == (a["knowledge_version_id"],)


@pytest.mark.parametrize(
    "dimension", ["jurisdiction", "jurisdiction_group", "scenario", "industry", "data_category"]
)
def test_dimension_hard_filter(fixture, dimension):
    f = fixture
    ref = (
        f["juri"]
        if dimension == "jurisdiction"
        else f["group"]
        if dimension == "jurisdiction_group"
        else f[dimension]
    )
    if dimension in {"industry", "data_category", "jurisdiction_group"}:
        with f["sf"]() as s, s.begin():
            s.add(
                c.BusinessFactEntity(
                    fact_id=uid(),
                    tenant_id=f["tenant"],
                    project_id=f["project"],
                    fact_type="GENERIC_METADATA",
                    normalized_key=dimension,
                    normalized_value_json={"metadata_refs": {dimension: [ref]}},
                    resolution_method="APPROVED_METADATA",
                    confidence=1,
                    validation_status="VALIDATED",
                    version=1,
                )
            )
    good = publish(f, [binding(f, "GLOBAL", {dimension: [ref]})])
    badref = (
        metadata(f["sf"], f["tenant"], dimension.upper()) if dimension != "jurisdiction" else uid()
    )
    if dimension == "jurisdiction":
        with f["sf"]() as s, s.begin():
            s.add(
                b.JurisdictionEntity(
                    jurisdiction_id=badref,
                    tenant_id=f["tenant"],
                    code=badref,
                    name="Other generic jurisdiction",
                )
            )
    bad = publish(f, [binding(f, "GLOBAL", {dimension: [badref]})])
    assert scope(f).filter_spec.version_filter == (good["knowledge_version_id"],)
    assert bad["knowledge_version_id"] not in scope(f).filter_spec.version_filter


def test_effective_lifecycle_and_language_exclusion(fixture):
    f = fixture
    v = publish(f)
    assert not scope(f, languages=("other",)).filter_spec.version_filter
    step(f, v, "expire")
    assert not scope(f).filter_spec.version_filter
    step(f, v, "archive")
    future = f["repo"].create_version(
        v["document_id"],
        {
            "collection_version_id": f["cv"],
            "language": "en",
            "effective_from": (date.today() + timedelta(days=1)).isoformat(),
            "provenance": {"fixture": True},
        },
    )
    ingest(f, future)
    step(f, future, "validate")
    step(f, future, "submit-review")
    step(f, future, "approve", True)
    with pytest.raises(ValueError):
        step(f, future, "publish")
    assert not scope(f).filter_spec.version_filter


def test_supersede_diff_and_immutable_snapshot(fixture):
    f = fixture
    v = publish(f)
    index = f["repo"].build_index(v["knowledge_version_id"])
    old_snapshot = f["snapshot"]
    frozen = scope(f, snapshot_id=old_snapshot)
    publish(f, doc=v["document_id"])
    assert f["repo"].get_version(v["knowledge_version_id"])["lifecycle"] == "SUPERSEDED"
    context(f, [f["b"]], [f["b"]])
    resumed = scope(f, snapshot_id=old_snapshot)
    assert resumed.filter_spec == frozen.filter_spec and resumed.allowed_product_ids == (f["a"],)
    assert not scope(f).filter_spec.version_filter
    assert count(f, k.KnowledgeVersionDiffEntity) == 1
    with f["sf"]() as s:
        pins = s.scalars(
            select(m.AnalysisSnapshotRegistryPinEntity).where(
                m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == old_snapshot
            )
        ).all()
        assert {"KNOWLEDGE_VERSION", "KNOWLEDGE_BINDING", "KNOWLEDGE_INDEX_VERSION"} <= {
            p.pin_type for p in pins
        }
        assert index["index_version_id"] in {p.version_id for p in pins}


def test_snapshot_current_permission_revocation(fixture):
    f = fixture
    publish(f, [binding(f, permissions=["read:internal"])])
    frozen = scope(f, snapshot_id=f["snapshot"])
    assert frozen.filter_spec.version_filter
    reader = RepositoryContext.user(UUID(f["tenant"]), "reader", set())
    r = PostgresKnowledgeRepository(f["sf"], reader)
    assert (
        not KnowledgeScopeResolver(r, reader)
        .resolve(f["project"], snapshot_id=f["snapshot"])
        .filter_spec.version_filter
    )
    assert (
        scope(f, snapshot_id=f["snapshot"]).filter_spec.version_filter
        == frozen.filter_spec.version_filter
    )


def test_ingestion_outbox_idempotency_retry_rollback(fixture):
    f = fixture
    v = draft(f)
    payload = inputs(f)
    r = f["repo"]
    service = KnowledgeIngestionService(r, storage=f["storage"])
    run = service.ingest(v["knowledge_version_id"], payload)
    assert (
        service.ingest(v["knowledge_version_id"], payload)["ingestion_run_id"]
        == run["ingestion_run_id"]
    )
    with pytest.raises(ValueError):
        service.ingest(v["knowledge_version_id"], dict(payload, strategy="ARTICLE"))

    class BrokenQueue:
        def enqueue(self, **kw):
            raise ConnectionError("unavailable")

    assert r.dispatch_outbox(BrokenQueue()) == 0
    sync = PostgresRegistrySyncEventRepository(f["sf"], f["ctx"])
    assert not sync.pending()
    q = RedisKnowledgeTaskQueue(get_settings().redis_url, f["tenant"], "test-worker")
    worker = KnowledgeIngestionWorker(r, service, q)
    assert worker.run_once()
    q.enqueue(task_id=UUID(run["ingestion_run_id"]), task_type="KNOWLEDGE_INGESTION")
    assert worker.run_once()
    assert count(f, k.KnowledgeChunkEntity) == 2 and count(f, k.KnowledgeIngestionRunEntity) == 1
    assert r.get_run(run["ingestion_run_id"])["status"] == "COMPLETED"
    bad = draft(f)
    badpayload = inputs(
        f,
        nodes=[
            {
                "node_type": "ARTICLE",
                "canonical_locator": "x",
                "parent_locator": "x",
                "original_text": "cycle",
            }
        ],
    )
    bad_run = service.ingest(bad["knowledge_version_id"], badpayload)
    with pytest.raises(ValueError):
        service.work(bad_run["ingestion_run_id"])
    assert (
        r.get_version(bad["knowledge_version_id"])["lifecycle"] == "DRAFT"
        and r.get_run(bad_run["ingestion_run_id"])["status"] == "FAILED"
    )
    assert count(f, k.KnowledgeChunkEntity) == 2


def test_concurrent_publish_and_optimistic_version(fixture):
    f = fixture
    v = draft(f)
    ingest(f, v)
    step(f, v, "validate")
    step(f, v, "submit-review")
    approved = step(f, v, "approve", True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: f["repo"].governance(
                    v["knowledge_version_id"], "publish", approved["record_version"]
                ),
                range(2),
            )
        )
    assert (
        all(r["lifecycle"] == "ACTIVE" for r in results)
        and count(f, m.AdminPublishRecordEntity) == 1
    )
    with pytest.raises(OptimisticConcurrencyError):
        f["repo"].governance(v["knowledge_version_id"], "expire", approved["record_version"])


def embedding_config(f):
    provider, pver, model, config, cap = [uid() for _ in range(5)]
    with f["sf"]() as s, s.begin():
        s.add(
            m.ModelProviderEntity(
                provider_id=provider,
                tenant_id=f["tenant"],
                code=provider,
                display_name="Generic fake",
                provider_type="TEST",
            )
        )
        s.flush()
        s.add(
            m.ModelProviderVersionEntity(
                provider_version_id=pver,
                tenant_id=f["tenant"],
                provider_id=provider,
                version_no=1,
                lifecycle_status="ACTIVE",
                base_url_ref=None,
                secret_ref=None,
                endpoint_config_json={},
            )
        )
        s.flush()
        s.add(
            m.ModelDefinitionEntity(
                model_definition_id=model,
                tenant_id=f["tenant"],
                provider_id=provider,
                display_name="Deterministic Test Model",
                model_id="generic-test",
            )
        )
        s.flush()
        s.add(
            m.ModelCapabilityEntity(
                model_capability_id=cap,
                tenant_id=f["tenant"],
                model_definition_id=model,
                capability="EMBEDDING",
                metadata_json={"embedding_dimension": 4},
            )
        )
        s.add(
            m.ModelDeploymentEntity(
                model_deployment_id=config,
                tenant_id=f["tenant"],
                model_definition_id=model,
                provider_version_id=pver,
                lifecycle_status="ACTIVE",
                deployment_ref="Generic test deployment",
            )
        )
    with f["sf"]() as s, s.begin():
        s.get(m.ModelProviderEntity, provider).active_version_id = pver
        s.get(m.ModelDefinitionEntity, model).active_deployment_id = config
    return config


def test_embedding_obeys_phase1c_provider_registry(fixture):
    f = fixture
    config = embedding_config(f)
    assert f["repo"].embedding_dimension(config) == 4
    with f["sf"]() as s, s.begin():
        deployment = s.get(m.ModelDeploymentEntity, config)
        model = s.get(m.ModelDefinitionEntity, deployment.model_definition_id)
        s.get(m.ModelProviderEntity, model.provider_id).enabled = False
    with pytest.raises(ValueError, match="Phase 1C registry"):
        f["repo"].embedding_dimension(config)


class FakeEmbedding:
    def embed(self, texts, *, model_config_id, dimension):
        return [[float(len(t)), 1.0, 2.0, 3.0] for t in texts]


def test_embedding_derived_indexes_and_pins(fixture):
    f = fixture
    v = publish(f)
    config = embedding_config(f)
    service = EmbeddingFoundationService(f["repo"], FakeEmbedding())
    index = service.build(v["knowledge_version_id"], config)
    assert (
        index["derived"]
        and service.build(v["knowledge_version_id"], config)["index_version_id"]
        == index["index_version_id"]
    )
    with f["sf"]() as s:
        assert s.execute(
            text("select vector_dims(embedding_vector) from embedding_records where tenant_id=:t"),
            {"t": f["tenant"]},
        ).scalars().all() == [4, 4]
        assert s.execute(
            text("select search_vector is not null from knowledge_chunks where tenant_id=:t"),
            {"t": f["tenant"]},
        ).scalars().all() == [True, True]
    scope(f, snapshot_id=f["snapshot"])
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(m.AnalysisSnapshotRegistryPinEntity).where(
                    m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == f["snapshot"],
                    m.AnalysisSnapshotRegistryPinEntity.pin_type == "EMBEDDING_CONFIG_VERSION",
                )
            ).version_id
            == config
        )


def test_embedding_bad_dimensions_rolls_back(fixture):
    f = fixture
    v = publish(f)
    config = embedding_config(f)

    class Bad:
        def embed(self, *a, **kw):
            return [[float("nan")]]

    with pytest.raises(ValueError):
        EmbeddingFoundationService(f["repo"], Bad()).build(v["knowledge_version_id"], config)
    assert count(f, k.EmbeddingRecordEntity) == 0 and count(f, k.KnowledgeIndexVersionEntity) == 0


def test_translation_review_and_original_separation(fixture):
    f = fixture
    v = publish(f)
    config = embedding_config(f)
    payload = dict(
        source_language="en",
        target_language="generic-other",
        translated_text_ref="test://reviewed-translation",
        translation_method="AI",
        model_config_id=config,
        provenance={"fixture": True},
    )
    t = f["repo"].create_translation(v["knowledge_version_id"], payload)
    assert not t["official_evidence"] and t["review_status"] == "PENDING"
    with pytest.raises(ValueError):
        f["repo"].approve_translation(t["translation_id"], 1)
    reviewed = f["reviewer"].approve_translation(t["translation_id"], 1)
    assert reviewed["review_status"] == "APPROVED" and not reviewed["official_evidence"]
    official = f["repo"].create_translation(
        v["knowledge_version_id"],
        dict(payload, translation_method="OFFICIAL", model_config_id=None),
    )
    assert f["reviewer"].approve_translation(official["translation_id"], 1)["official_evidence"]
    assert (
        f["repo"].list_component(v["knowledge_version_id"], "chunks")[0]["original_text"]
        == "Generic Official Regulation"
    )


def test_tenant_binding_rollback_and_snapshot_mismatch(fixture):
    f = fixture
    v = draft(f)
    payload = inputs(f, [binding(f, dimensions={"product": [uid()]})])
    with pytest.raises(LookupError):
        KnowledgeIngestionService(f["repo"]).ingest(v["knowledge_version_id"], payload)
    assert count(f, k.KnowledgeIngestionRunEntity) == 0 and count(f, m.KnowledgeBindingEntity) == 0
    with pytest.raises(LookupError):
        PostgresKnowledgeRepository(
            f["sf"], RepositoryContext.user(uuid4(), "outsider")
        ).formal_context(f["project"], "PROJECT", f["project"], None)
    with pytest.raises(LookupError):
        scope(f, snapshot_id=uid())


def test_real_api_contracts_and_isolation(fixture):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.routes.knowledge import router

    f = fixture
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)
    ctx = [f["ctx"]]

    @app.middleware("http")
    async def auth(request: Request, call_next):
        request.state.repository_context = ctx[0]
        return await call_next(request)

    client = TestClient(app)
    v = draft(f)
    run = client.post(
        "/api/v1/admin/knowledge-versions/" + v["knowledge_version_id"] + "/ingest", json=inputs(f)
    )
    assert (
        run.status_code == 202 and "input_json" not in run.json() and "audit_json" not in run.json()
    )
    KnowledgeIngestionService(f["repo"], storage=f["storage"]).work(run.json()["ingestion_run_id"])
    for name in ("structure", "chunks", "bindings", "quality"):
        assert (
            client.get(
                "/api/v1/admin/knowledge-versions/" + v["knowledge_version_id"] + "/" + name
            ).status_code
            == 200
        )
    response = client.post("/api/v1/projects/" + f["project"] + "/knowledge-scope/resolve", json={})
    assert (
        response.status_code == 200
        and response.json()["filter_spec"]["tenant_filter"] == f["tenant"]
    )
    assert client.get("/api/v1/projects/" + f["project"] + "/knowledge-scope").status_code == 200
    ctx[0] = RepositoryContext.user(UUID(f["tenant"]), "reader")
    assert client.get("/api/v1/admin/knowledge-sources/" + f["source"]).status_code == 403
    ctx[0] = RepositoryContext.user(uuid4(), "outsider", {"knowledge:admin"})
    assert client.get("/api/v1/admin/knowledge-sources/" + f["source"]).status_code == 404


def test_domain_selected_item_stays_specific(fixture):
    f = fixture
    run = context(f, [f["domain"]], [f["domain"]])
    a = publish(f)
    publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    ident = item(f, f["a"], run["version"])
    result = scope(f, subject_type="DATA_ITEM", subject_id=ident)
    assert result.allowed_product_ids == (f["a"],)
    assert result.filter_spec.version_filter == (a["knowledge_version_id"],)


def test_missing_phase1e_context_and_source_revocation(fixture):
    f = fixture
    publish(f)
    frozen = scope(f, snapshot_id=f["snapshot"])
    assert frozen.filter_spec.version_filter
    f["repo"].update_source(f["source"], {"validation_status": "PENDING"}, 1)
    assert not scope(f, snapshot_id=f["snapshot"]).filter_spec.version_filter
    project = uid()
    with f["sf"]() as s, s.begin():
        s.add(b.ProjectEntity(project_id=project, tenant_id=f["tenant"], name="No formal context"))
    with pytest.raises(ValueError, match="PHASE1E_FORMAL_CONTEXT_REQUIRED"):
        KnowledgeScopeResolver(f["repo"], f["ctx"]).resolve(project)


def test_controlled_url_ingestion_uses_port_and_audit(fixture):
    import json

    f = fixture
    v = draft(f)
    payload = inputs(f)
    payload.pop("nodes")
    payload["url"] = "https://generic.example/official.json"

    class Download:
        def download(self, url):
            assert url == payload["url"]
            return json.dumps({"nodes": inputs(f)["nodes"]}).encode(), {
                "request_audit": [{"host": "generic.example", "status": 200}]
            }

    service = KnowledgeIngestionService(f["repo"], storage=f["storage"], downloader=Download())
    run = service.ingest(v["knowledge_version_id"], payload)
    service.work(run["ingestion_run_id"])
    with f["sf"]() as s:
        stored = s.get(k.KnowledgeIngestionRunEntity, run["ingestion_run_id"])
        assert (
            stored.audit_json["request_audit"][0]["status"] == 200
            and stored.audit_json["content_hash"]
        )
    assert f["repo"].get_version(v["knowledge_version_id"])["lifecycle"] == "INGESTED"
    bad = draft(f)
    with pytest.raises(ValueError):
        service.ingest(
            bad["knowledge_version_id"],
            dict(payload, idempotency_key=uid(), url="https://unapproved.example/x"),
        )


def test_postgres_constraints_and_rollback(fixture):
    from sqlalchemy.exc import IntegrityError

    f = fixture
    v = publish(f)
    with pytest.raises(IntegrityError), f["sf"]() as s, s.begin():
        s.execute(
            text(
                "UPDATE knowledge_document_versions SET lifecycle='INVALID' "
                "WHERE knowledge_version_id=:id"
            ),
            {"id": v["knowledge_version_id"]},
        )
    assert f["repo"].get_version(v["knowledge_version_id"])["lifecycle"] == "ACTIVE"
    newer = draft(f, doc=v["document_id"])
    with pytest.raises(IntegrityError), f["sf"]() as s, s.begin():
        s.execute(
            text(
                "UPDATE knowledge_document_versions SET lifecycle='ACTIVE' "
                "WHERE knowledge_version_id=:id"
            ),
            {"id": newer["knowledge_version_id"]},
        )
    assert f["repo"].get_version(newer["knowledge_version_id"])["lifecycle"] == "DRAFT"
    with pytest.raises(IntegrityError), f["sf"]() as s, s.begin():
        s.execute(
            text(
                "UPDATE knowledge_structure_nodes SET parent_node_id=:missing "
                "WHERE knowledge_version_id=:id"
            ),
            {"missing": uid(), "id": v["knowledge_version_id"]},
        )
    with pytest.raises(IntegrityError), f["sf"]() as s, s.begin():
        s.execute(
            text("UPDATE knowledge_document_versions SET version=1 WHERE knowledge_version_id=:id"),
            {"id": newer["knowledge_version_id"]},
        )


def test_version_diff_all_structural_changes(fixture):
    f = fixture
    first = draft(f)
    ingest(f, first)
    second = draft(f, doc=first["document_id"])
    payload = inputs(
        f,
        nodes=[
            {
                "node_type": "ACT",
                "canonical_locator": "act",
                "original_text": "Modified generic rule",
            },
            {
                "node_type": "ANNEX",
                "canonical_locator": "act/annex",
                "parent_locator": "act",
                "original_text": "Added annex",
            },
        ],
        bindings=[binding(f, "GLOBAL", {})],
    )
    ingest(f, second, payload)
    changes = f["repo"].compare_versions(
        first["knowledge_version_id"], second["knowledge_version_id"]
    )
    assert (
        changes["added_structure_nodes"] == ["act/annex"]
        and changes["removed_structure_nodes"] == ["act/article/1"]
        and changes["modified_structure_nodes"] == ["act"]
    )
    assert changes["binding_changed"] and not changes["source_changed"]


def test_pending_translation_cannot_declare_official(fixture):
    f = fixture
    v = publish(f)
    payload = dict(
        source_language="en",
        target_language="generic-other",
        translated_text_ref="test://translation",
        translation_method="OFFICIAL",
        review_status="APPROVED",
        reviewer="fabricated",
        provenance={"fixture": True},
    )
    with pytest.raises(ValueError):
        f["repo"].create_translation(v["knowledge_version_id"], payload)
    assert count(f, k.KnowledgeTranslationEntity) == 0
