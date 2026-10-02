# Phase 1F Knowledge Quality & Governance Result

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation**.

Tested SHA: `70da467edc4881034ed919434ac38e39e0b8132e`. Run ID: `36968097285`. Attempt: `1`.
Final evidence Source of Truth: [phase1f_final_remote.json](evidence/phase1f_final_remote.json).
Artifact ID: `11210791229`. Artifact digest: `sha256:d04a97683672551979ed02ee1405a28a087fd2d5d94e5ef5419466cffad6303f`.

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

Lifecycle: DRAFT → INGESTED → VALIDATED → PENDING_REVIEW → APPROVED → ACTIVE → SUPERSEDED/EXPIRED → ARCHIVED. Explicit administrative actions validate transitions and expected record_version. Failed quality remains INGESTED and cannot enter review/publish. Publication rechecks quality, independent review and effective date.

Seven quality assertions: validated/enabled source, nonempty canonical structure/chunks, structured citations, content hash/ACTIVE collection version, consistent language, binding provenance and complete version/artifact/node provenance. The contract supports PASS/WARNING/REVIEW_REQUIRED/FAILED; this deterministic first gate emits PASS or FAILED. Warning heuristics are excluded.

Review reuses AdminChangeSet, AdminReviewTask and AdminPublishRecord. The original author and system worker cannot approve. Binding approval occurs within the reviewed version transaction. Concurrent repeat publish yields one publication record; publish of a new version supersedes the previous one and records a diff/event.

PASS assertions: invalid transitions, quality failure boundary, independent reviewer, publish/supersede/expiry, one ACTIVE index, duplicate publish idempotency, optimistic stale rejection and transaction rollback. No second knowledge review subsystem exists.
