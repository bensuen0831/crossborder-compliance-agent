"""Phase 1H consumes actual authorized Phase 1G evidence, without another retrieval."""

from uuid import UUID

import pytest
from phase1g_fixtures import publish
from test_phase1f_postgres import context, item
from test_phase1f_postgres import fixture as fixture
from test_phase1g_persistence_postgres import policies, query, service

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.classification_evidence import (
    ExistingClassificationEvidence,
)

pytestmark = pytest.mark.runtime_smoke


def test_existing_pack_refs_are_subject_and_actor_scoped(fixture):
    f = fixture
    run = context(f, [f["a"]], [f["a"]])
    subject = item(f, f["a"], run["version"])
    v = publish(f)
    f["repo"].build_index(v["knowledge_version_id"])
    repo, p, _ = policies(f)
    response = service(f, repo).retrieve(query(f, p, subject_type="DATA_ITEM", subject_id=subject))
    pack = response["rag_context_pack"]["evidence_pack"]
    assert pack["items"]
    ctx = repo.context
    consumer = ExistingClassificationEvidence(f["sf"], ctx)
    refs, types, packs = consumer.references(f["project"], f["snapshot"], subject)
    assert refs and types and pack["evidence_pack_id"] in packs
    other_actor = RepositoryContext.user(
        UUID(f["tenant"]), "unrelated-actor", set(ctx.permission.scopes)
    )
    assert ExistingClassificationEvidence(f["sf"], other_actor).references(
        f["project"], f["snapshot"], subject
    ) == ((), (), ())
    assert consumer.references(f["project"], f["snapshot"], None) == ((), (), ())
