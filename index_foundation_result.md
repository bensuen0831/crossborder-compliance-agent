# Phase 1F Index Foundation Result

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation**.

Tested SHA: `7391b9728e788b70e11885fe23d64980dcc3db37`. Run ID: `36973990791`. Attempt: `1`.
Final evidence Source of Truth: [phase1f_final_remote.json](evidence/phase1f_final_remote.json).
Artifact ID: `11212349170`. Artifact digest: `sha256:b31ac0fe52e103fa291e2c5f1356bee52a47ffd0fa0fc3b4f9774534cf43b47d`.

| Empirical assertion | Actual result |
|---|---|
| Full PostgreSQL/runtime pytest | **142 passed / 0 skipped / 0 deselected** |
| Alembic head | **0006_phase1f** |
| Phase 1F schema | **29/29 PASS** |
| Architecture executable checks | **77/77 PASS** |
| Phase 1A runtime/checkpoint/restart/resume/retry | **25/25 PASS** |
| Phase 1B / 1C / 1D / 1E schema regression | **16/16; 20/20; 15/15; 22/22 PASS** |
| Phase 1A–1E full regression | **PASS** |

Above values are independently verified through GitHub Checks measured evidence for the identified CI run; they do not reuse Phase 1E totals. The local full gate at `4e7d0d9759c42b2da91a23dea47f2cdea0243449` is separate corroborating evidence. The linked remote manifest pins the immutable pre-issuance baseline. Later governance commits contain documentation/evidence only and retain the tested implementation.

Known exclusions: Phase 1G retrieval/ranking/reranking/RAG/answer generation, classification, regulation applicability, country rules, risk and compliance paths are excluded. Ingestion currently supports approved canonical structure JSON upload or controlled HTTPS JSON sources; automatic legal PDF/DOCX import, external site crawling, actual model-provider execution and affected-project impact calculation are excluded. Storage/embedding tests use explicit adapters; PostgreSQL and Redis are real. Whitespace token counting is a deterministic foundation measure, not provider tokenizer equivalence. Local PostgreSQL 17.11/Redis 8.0.2 are separately identified from CI PostgreSQL 16/Redis 7.

Authoritative boundary: PostgreSQL canonical knowledge tables; Phase 1C source definitions/collections/bindings and model metadata are reused; Phase 1B RegulatoryStructureNode/EvidenceReference/Citation and durable admin review are reused. Object storage retains original artifacts. Registry, FTS and pgvector are derived projections/indexes. Formal Phase 1E context is the only context input.

PostgreSQL chunks have a generated `search_vector` derived from normalized canonical text and a GIN index. Embedding records have a pgvector column with a dimension check. For model dimensions ≤ 2000, build creates a validated per-model partial HNSW cosine index; higher supported storage dimensions (up to 16000) retain vector storage without that HNSW index. No top-K or FTS business search is exposed.

KnowledgeIndexVersion pins knowledge version, chunking strategy, embedding config, FTS config, build state/date and canonical content hash. EmbeddingJob/Record retain chunk/model/config, dimension, embedding version, vector hash, generation time/status. Config resolves through Phase 1C ModelRegistry with active provider/model/deployment and EMBEDDING capability; dimension comes from capability metadata. Provider secrets are not returned or invoked.

EmbeddingPort is injected; tests use deterministic fake output. Bad cardinality, dimension or nonfinite values fail before persistence. Rebuild of identical canonical content/config returns the existing index version. Snapshot pins version/binding/index/config through existing registry pin infrastructure.

PASS assertions: actual vector_dims, generated FTS column, derived index identity/idempotency, HNSW foundation, bad vector rollback, disabled provider rejection and embedding config snapshot pin. Indexes are never knowledge Source of Truth.
