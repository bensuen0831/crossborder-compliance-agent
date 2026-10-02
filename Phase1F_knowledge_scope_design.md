# Phase 1F Knowledge & Scope Design

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation**.

Tested SHA: `5acbcd1813cb80a2bd3d0f92d04dc68f5d4fc3db`. Run ID: `NOT_VERIFIED — final documentation CI pending`. Attempt: `NOT_VERIFIED`.
Final evidence Source of Truth: [phase1f_final_remote.json](evidence/phase1f_final_remote.json).
Artifact ID: `NOT_VERIFIED`. Artifact digest: `NOT_VERIFIED`.

| Empirical assertion | Actual result |
|---|---|
| Full PostgreSQL/runtime pytest | **137 passed / 0 skipped / 0 deselected** |
| Alembic head | **0006_phase1f** |
| Phase 1F schema | **29/29 PASS** |
| Architecture executable checks | **77/77 PASS** |
| Phase 1A runtime/checkpoint/restart/resume/retry | **25/25 PASS** |
| Phase 1B / 1C / 1D / 1E schema regression | **16/16; 20/20; 15/15; 22/22 PASS** |
| Phase 1A–1E full regression | **PASS** |

Above values are actual full-suite evidence, not prior Phase 1E totals. Before the final remote manifest is issued, they refer to the local measured gate at `5acbcd1813cb80a2bd3d0f92d04dc68f5d4fc3db`; remote identifiers remain NOT_VERIFIED. After issuance, the linked immutable CI baseline is authoritative. Later governance commits must be documentation only and retain the same implementation.

Known exclusions: Phase 1G retrieval/ranking/reranking/RAG/answer generation, classification, regulation applicability, country rules, risk and compliance paths are excluded. Ingestion currently supports approved canonical structure JSON upload or controlled HTTPS JSON sources; automatic legal PDF/DOCX import, external site crawling, actual model-provider execution and affected-project impact calculation are excluded. Storage/embedding tests use explicit adapters; PostgreSQL and Redis are real. Whitespace token counting is a deterministic foundation measure, not provider tokenizer equivalence. Local PostgreSQL 17.11/Redis 8.0.2 are separately identified from CI PostgreSQL 16/Redis 7.

Authoritative boundary: PostgreSQL canonical knowledge tables; Phase 1C source definitions/collections/bindings and model metadata are reused; Phase 1B RegulatoryStructureNode/EvidenceReference/Citation and durable admin review are reused. Object storage retains original artifacts. Registry, FTS and pgvector are derived projections/indexes. Formal Phase 1E context is the only context input.

The platform separates ingestion/publication from runtime permission scope. No similarity query, ranking, LLM call or legal conclusion occurs in the scope pipeline.

```mermaid
flowchart TD
  Source[Registry-governed Source] --> Ingest[Durable Ingestion Outbox / Redis Worker]
  Ingest --> Canonical[Versioned Canonical Structure / Legal Node Extension]
  Canonical --> Chunks[Structure-aware Chunks / Citation Provenance]
  Chunks --> Bind[Versioned Bindings]
  Bind --> Quality[Seven Quality Assertions]
  Quality --> Review[Existing Durable Admin Review]
  Review --> Active[Approved Publication / ACTIVE]
  Context[Phase 1E Formal Context / Immutable Snapshot] --> Scope[KnowledgeScopeResolver]
  Active --> Scope
  Scope --> Filter[Hard Filter Contract for Phase 1G]
  Active --> Index[Derived FTS / Embedding Index Foundation]
```

Domain contracts: `domain/knowledge.py`. Application services/ports: `application/knowledge_services.py`, `application/knowledge_ports.py`. PostgreSQL adapters: `infrastructure/persistence/knowledge_models.py`, `knowledge_repositories.py`. Controlled transport/queue: `knowledge_download.py`, `knowledge_worker.py`. API and migration are separate adapters.

Each lifecycle mutation locks the parent document then refreshes the version under row lock. Independent human approval is required; worker credentials cannot approve. A unique partial index enforces one ACTIVE version per document. Publish supersedes the previous ACTIVE version and emits change/diff records. Snapshot scope persists formal context, versions, bindings, indexes and embedding configuration identities; resume uses those historical identities while rechecking current permissions and source revocation.

PASS evidence: complete tests/test_phase1f_postgres.py (29 tests) and tests/test_phase1f_download_chunking.py (26 tests), schema gate and architecture gate. Mandatory Cases A–E are explicit tests.
