# Phase 1F Knowledge Ingestion Result

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation**.

Tested SHA: `4e7d0d9759c42b2da91a23dea47f2cdea0243449`. Run ID: `36973419700`. Attempt: `1`.
Final evidence Source of Truth: [phase1f_final_remote.json](evidence/phase1f_final_remote.json).
Artifact ID: `11213170166`. Artifact digest: `sha256:be40b7ccc016e51895c067b3779783aa921450505f2fd52b64457ff36db99b03`.

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

POST ingest creates a durable PostgreSQL ingestion run and `registry_sync_events` outbox event and returns 202. Redis Streams delivers tenant-specific tasks. `KnowledgeIngestionWorker` dispatches pending outbox events, claims/reclaims tasks, invokes canonicalization/chunking/persistence and acknowledges after durable completion. Retry after completion is a no-op. Queue delivery failure retains the pending outbox. The Phase 1C registry consumer explicitly excludes knowledge ingestion events.

`ControlledDownloaderPort` isolates external fetch. The supplied HTTPS adapter validates scheme/credentials/host/port, all DNS addresses, public IP policy, TLS hostname, redirect chain, timeout, MIME, encoding, length/size, content and source hashes and request audit. Connections use validated pinned IPs. Canonical uploads and approved URL imports enter INGESTED, never ACTIVE. Original JSON is stored through ObjectStoragePort before relational canonicalization.

PASS assertions: durable outbox retry, real Redis delivery/ack, duplicate task idempotency, idempotency payload mismatch, invalid hierarchy rollback, URL source matching/port audit, private IPv4/IPv6/mixed DNS rejection, redirect revalidation, MIME/size/truncation/encoding rejection and connection cleanup.

Operational entry: `python scripts/knowledge_ingestion_worker.py --tenant-id <UUID> --once`; object storage must be configured. Approved URL host configuration is explicit. The pinned transport requires deployment egress for those approved source hosts; proxy-only deployments may inject a different ControlledDownloaderPort without changing domain services. No actual external site download or S3 deployment readiness is claimed by test adapters.
