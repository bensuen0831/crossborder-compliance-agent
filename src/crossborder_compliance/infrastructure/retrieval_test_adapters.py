"""Explicit deterministic test adapters, never default production model execution."""

import hashlib
from uuid import uuid4

from crossborder_compliance.domain.retrieval import ExternalEvidenceCandidate


class DeterministicFakeReranker:
    def rerank(self, query_text, candidates, *, model_config_id=None):
        return tuple((c.chunk_id, c.hybrid_score) for c in candidates)


class DeterministicTestEmbedding:
    def embed(self, texts, *, model_config_id, dimension):
        return [
            [
                float(hashlib.sha256(text.lower().encode()).digest()[i % 32] + 1)
                for i in range(dimension)
            ]
            for text in texts
        ]


class DeterministicWikiGenerator:
    def generate(self, sources):
        return "\n".join(f"{s['canonical_locator']}: {s['heading']}" for s in sources)


class DeterministicEvidenceGapQueryPlanner:
    def plan(self, query_text, gaps):
        return (query_text + " " + " ".join(gaps.missing_topics),)


class RegistrySourceDiscoveryAdapter:
    def __init__(self, repository):
        self.repository = repository

    def discover(self, queries, policy):
        return tuple(
            ExternalEvidenceCandidate(
                candidate_id=str(uuid4()),
                source_id=rule.source_id,
                source_url=self.repository.source(rule.source_id)["canonical_url"],
            )
            for rule in policy.source_rules[: policy.maximum_sources]
        )
