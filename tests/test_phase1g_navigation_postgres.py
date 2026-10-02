from uuid import uuid4

import pytest
from test_phase1f_postgres import binding, metadata, publish, scope
from test_phase1f_postgres import fixture as fixture

from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.retrieval_navigation import (
    PostgresRetrievalNavigationRepository,
)
from crossborder_compliance.infrastructure.retrieval_test_adapters import DeterministicWikiGenerator

pytestmark = pytest.mark.runtime_smoke


def test_wiki_draft_review_runtime_boundary(fixture):
    f = fixture
    v = publish(f, [binding(f, permissions=["read:internal"])])
    r = PostgresRetrievalNavigationRepository(f["sf"], f["ctx"])
    reviewed = PostgresRetrievalNavigationRepository(f["sf"], f["reviewer"].context)
    wiki = r.generate_wiki(
        "Generic Wiki", [v["knowledge_version_id"]], DeterministicWikiGenerator()
    )
    assert wiki["lifecycle"] == "DRAFT" and not wiki["official_evidence"]
    scoped = scope(f, snapshot_id=f["snapshot"])
    with pytest.raises(LookupError):
        r.runtime_wiki(scoped, wiki["wiki_page_id"])
    with pytest.raises(ValueError):
        r.wiki_action(wiki["wiki_version_id"], "publish", 1)
    r.wiki_action(wiki["wiki_version_id"], "validate", 1)
    r.wiki_action(wiki["wiki_version_id"], "submit-review", 2)
    with pytest.raises(ValueError):
        r.wiki_action(wiki["wiki_version_id"], "approve", 3)
    reviewed.wiki_action(wiki["wiki_version_id"], "approve", 3)
    r.wiki_action(wiki["wiki_version_id"], "publish", 4)
    runtime = r.runtime_wiki(scoped, wiki["wiki_page_id"])
    assert runtime["lifecycle"] == "ACTIVE" and not runtime["legal_basis"]


def test_graph_provenance_review_and_bad_source_rollback(fixture):
    f = fixture
    v = publish(f)
    r = PostgresRetrievalNavigationRepository(f["sf"], f["ctx"])
    reviewed = PostgresRetrievalNavigationRepository(f["sf"], f["reviewer"].context)
    with f["sf"]() as s:
        n = r.rows(
            s,
            k.KnowledgeStructureNodeEntity,
            k.KnowledgeStructureNodeEntity.knowledge_version_id == v["knowledge_version_id"],
        )[0]
        evidence = r.get(s, b.CitationEntity, n.citation_id).evidence_id
    payload = dict(
        source_knowledge_id=v["document_id"],
        source_knowledge_version_id=v["knowledge_version_id"],
        source_evidence_id=evidence,
        jurisdiction_id=f["juri"],
        node_type="STRUCTURE",
        display_name="Generic graph node",
        confidence=1,
    )
    node = r.create_graph("node", payload)
    assert node["status"] == "DRAFT" and not node["legal_applicability"]
    with pytest.raises(ValueError):
        r.create_graph("node", dict(payload, source_knowledge_id=str(uuid4())))
    r.graph_action("node", node["graph_node_id"], "submit-review", 1)
    with pytest.raises(ValueError):
        r.graph_action("node", node["graph_node_id"], "approve", 2)
    assert reviewed.graph_action("node", node["graph_node_id"], "approve", 2)["status"] == "ACTIVE"
    target = r.create_graph("node", payload)
    relation = metadata(f["sf"], f["tenant"], "GRAPH_RELATION_TYPE")
    edge = r.create_graph(
        "edge",
        dict(
            {key: val for key, val in payload.items() if key not in ("node_type", "display_name")},
            source_node_id=node["graph_node_id"],
            target_node_id=target["graph_node_id"],
            relation_type_ref=relation,
        ),
    )
    assert edge["inferred"] and edge["derived"] and not edge["legal_applicability"]
