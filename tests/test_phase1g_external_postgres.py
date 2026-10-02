"""Runtime external provenance, trust scope and reproducible website snapshots."""

import hashlib
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from test_phase1f_postgres import binding, metadata, publish
from test_phase1f_postgres import fixture as fixture
from test_phase1g_persistence_postgres import query, service

from crossborder_compliance.application.external_evidence_services import (
    ExternalEvidenceAugmentationService,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)
from crossborder_compliance.infrastructure.retrieval_test_adapters import (
    DeterministicEvidenceGapQueryPlanner,
    RegistrySourceDiscoveryAdapter,
)

pytestmark = pytest.mark.runtime_smoke


def external_setup(f, tier="T1_PRIMARY_OFFICIAL", permissions=(), **policy_extra):
    r = PostgresRetrievalRepository(f["sf"], f["ctx"])
    authority = metadata(f["sf"], f["tenant"], "AUTHORITY")
    source = r.create_source(
        dict(
            collection_id=f["col"],
            code=authority,
            source_type="OFFICIAL_LEGISLATION",
            authority_ref=authority,
            canonical_url="https://generic.example/approved-external.json",
            jurisdiction_refs=[f["juri"]],
            trust_level="APPROVED",
            language="en",
            validation_status="VALIDATED",
            provenance={"approved": True},
        )
    )
    trusted = r.create_policy(
        "trusted_source",
        dict(
            source_rules=[
                dict(
                    source_id=source["source_id"],
                    authority_ref=authority,
                    source_tier=tier,
                    jurisdiction_ids=[f["juri"]],
                    permission_scopes=list(permissions),
                    scope_type="PRODUCT_SPECIFIC",
                    dimensions={"product": [f["a"]]},
                )
            ]
        ),
    )
    r.publish_policy("trusted_source", trusted["policy_version_id"], 1)
    suff = r.create_policy("sufficiency", {})
    r.publish_policy("sufficiency", suff["policy_version_id"], 1)
    policy = r.create_policy(
        "retrieval",
        dict(
            vector_weight=0,
            lexical_weight=1,
            sufficiency_policy_id=suff["policy_id"],
            trusted_source_policy_id=trusted["policy_id"],
            external_augmentation_enabled=True,
            **policy_extra,
        ),
    )
    r.publish_policy("retrieval", policy["policy_version_id"], 1)
    body = dict(
        authority_ref=authority,
        jurisdiction_ids=[f["juri"]],
        language="en",
        effective_from=date.today().isoformat(),
        publication_date=date.today().isoformat(),
        nodes=[dict(canonical_locator="article/1", original_text="Generic official evidence")],
    )

    class Download:
        calls = 0

        def download(self, url):
            self.calls += 1
            raw = json.dumps(body).encode()
            return raw, {
                "content_hash": hashlib.sha256(raw).hexdigest(),
                "canonical_url": url,
                "request_audit": [{"approved": True}],
            }

    downloader = Download()
    external = ExternalEvidenceAugmentationService(
        r,
        f["ctx"],
        DeterministicEvidenceGapQueryPlanner(),
        RegistrySourceDiscoveryAdapter(r),
        lambda *args: downloader,
    )
    return r, policy, body, downloader, external


def test_verified_external_pin_reuse_not_active_and_citation_chain(fixture):
    f = fixture
    r, p, body, d, external = external_setup(f)
    result = service(f, r, external=external).retrieve(query(f, p))
    rag = result["rag_context_pack"]
    assert rag["knowledge_sufficiency"]["status"] == "SUFFICIENT"
    assert rag["fallback_guidance_context"] is None
    evidence = rag["evidence_pack"]["items"][0]
    assert evidence["external_evidence_id"] and evidence["citation_id"]
    assert evidence["knowledge_document_id"] is None
    assert (
        rag["evidence_pack"]["manifest"]["external_artifacts"][0]["content_hash"]
        == evidence["content_hash"]
    )
    body["nodes"][0]["original_text"] = "Website changed later"
    resumed = service(f, r, external=external).retrieve(query(f, p))
    assert d.calls == 1
    assert (
        resumed["rag_context_pack"]["evidence_pack"]["items"][0]["original_text"]
        == "Generic official evidence"
    )
    with f["sf"]() as s:
        row = s.scalar(
            select(g.RuntimeExternalEvidenceEntity).where(
                g.RuntimeExternalEvidenceEntity.tenant_id == f["tenant"]
            )
        )
        assert row.status == "VERIFIED" and not row.active_knowledge
        assert (
            s.scalar(
                select(func.count())
                .select_from(k.KnowledgeDocumentEntity)
                .where(k.KnowledgeDocumentEntity.tenant_id == f["tenant"])
            )
            == 0
        )


@pytest.mark.parametrize(
    "case", ["expired", "authority", "hash", "permission", "T4", "timeout", "bad_structure"]
)
def test_external_rejection_never_empty_guidance(fixture, case):
    f = fixture
    r, p, body, d, external = external_setup(
        f,
        tier="T4_UNVERIFIED_WEB" if case == "T4" else "T1_PRIMARY_OFFICIAL",
        permissions=("private:read",) if case == "permission" else (),
    )
    if case == "expired":
        body["effective_to"] = (date.today() - timedelta(days=1)).isoformat()
    if case == "authority":
        body["authority_ref"] = "untrusted"
    if case == "bad_structure":
        body["nodes"] = []
    if case == "hash":

        def bad(url):
            return json.dumps(body).encode(), {"content_hash": "0" * 64}

        d.download = bad
    if case == "timeout":

        def timeout(url):
            raise TimeoutError("test deadline")

        d.download = timeout
    result = service(f, r, external=external).retrieve(query(f, p))["rag_context_pack"]
    assert result["knowledge_sufficiency"]["status"] == "INSUFFICIENT"
    assert not result["evidence_pack"]["items"]
    assert result["fallback_guidance_context"]["operational_next_steps"]
    if case in ("permission", "T4"):
        assert d.calls == 0


def test_sufficient_internal_does_not_download(fixture):
    f = fixture
    r, p, body, d, external = external_setup(f)
    f["source"] = r.create_source(
        dict(
            collection_id=f["col"],
            code="internal-" + f["a"],
            source_type="OFFICIAL_LEGISLATION",
            authority_ref=body["authority_ref"],
            canonical_url="https://generic.example/internal.json",
            jurisdiction_refs=[f["juri"]],
            language="en",
            trust_level="APPROVED",
            validation_status="VALIDATED",
            provenance={"approved": True},
        )
    )["source_id"]
    v = publish(f, [binding(f, dimensions={"product": [f["a"]], "jurisdiction": [f["juri"]]})])
    r.build_index(v["knowledge_version_id"])
    result = service(f, r, external=external).retrieve(query(f, p))["rag_context_pack"]
    assert result["knowledge_sufficiency"]["status"] == "SUFFICIENT"
    assert not result["external_augmentation_metadata"]["attempted"] and d.calls == 0
