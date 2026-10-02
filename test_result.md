# Phase 1F Test Result

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

**137 passed / 0 skipped / 0 deselected** in the mandatory full PostgreSQL/runtime suite. Existing 82 Phase 1A–1E tests are retained; Phase 1F adds 29 PostgreSQL/Redis tests and 26 transport/chunking tests. `scripts/verify_full_pytest.py` reads JUnit actual counts and rejects skip/deselect/failure/error/missing phase coverage. CI contract subset is supplemental and does not replace the mandatory full suite.

Required assertions cover source CRUD/soft disable, version lifecycle/effective dates, canonical hierarchy/legal identity, chunk/citation/source provenance, binding/quality/publish/supersede/expired exclusion, translation review, permission/product/jurisdiction/group/scenario/industry/data-category isolation, minimal item/flow scope, conflict/document-first fail-safe, tenant isolation, rollback, optimistic and concurrent publication, snapshot version/index/config pinning, source/permission revocation, real Redis outbox/idempotency and vector/FTS foundation.

Mandatory runtime gate uses separate processes for start→interrupt, restart→resume and duplicate resume retry, and checks 25 assertions. No regression assertion was disabled. Phase 1A official LangGraph checkpoint ownership, Phase 1B normalized Source of Truth/tenant, Phase 1C registry/admin, Phase 1D parsers/async provenance and Phase 1E resolution/review/versioning remain PASS.

Local full evidence: `/workspace/phase1f_gate3_evidence` (code SHA in local measured summary). Remote evidence contains JUnit, full log, schema/architecture/runtime JSON, immutable head/runner identities and file manifest. Final remote measured summary is obtained through GitHub Checks API; GitHub stores full gate log in the uploaded artifact. If archive download is restricted, that local-copy limitation must be recorded; do not substitute a local hash for the GitHub artifact digest.
