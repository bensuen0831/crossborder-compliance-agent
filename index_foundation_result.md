# Phase 1F Index Foundation Result

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

PostgreSQL chunks have a generated `search_vector` derived from normalized canonical text and a GIN index. Embedding records have a pgvector column with a dimension check. For model dimensions ≤ 2000, build creates a validated per-model partial HNSW cosine index; higher supported storage dimensions (up to 16000) retain vector storage without that HNSW index. No top-K or FTS business search is exposed.

KnowledgeIndexVersion pins knowledge version, chunking strategy, embedding config, FTS config, build state/date and canonical content hash. EmbeddingJob/Record retain chunk/model/config, dimension, embedding version, vector hash, generation time/status. Config resolves through Phase 1C ModelRegistry with active provider/model/deployment and EMBEDDING capability; dimension comes from capability metadata. Provider secrets are not returned or invoked.

EmbeddingPort is injected; tests use deterministic fake output. Bad cardinality, dimension or nonfinite values fail before persistence. Rebuild of identical canonical content/config returns the existing index version. Snapshot pins version/binding/index/config through existing registry pin infrastructure.

PASS assertions: actual vector_dims, generated FTS column, derived index identity/idempotency, HNSW foundation, bad vector rollback, disabled provider rejection and embedding config snapshot pin. Indexes are never knowledge Source of Truth.
