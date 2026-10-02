# Phase 1F Test Result

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

**142 passed / 0 skipped / 0 deselected** in the mandatory full PostgreSQL/runtime suite. Existing 82 Phase 1A–1E tests are retained; Phase 1F adds 34 PostgreSQL/Redis tests and 26 transport/chunking tests. `scripts/verify_full_pytest.py` reads JUnit actual counts and rejects skip/deselect/failure/error/missing phase coverage. CI contract subset is supplemental and does not replace the mandatory full suite.

Required assertions cover source CRUD/soft disable, version lifecycle/effective dates, canonical hierarchy/legal identity, chunk/citation/source provenance, binding/quality/publish/supersede/expired exclusion, translation review, permission/product/jurisdiction/group/scenario/industry/data-category isolation, minimal item/flow scope, conflict/document-first fail-safe, tenant isolation, rollback, optimistic and concurrent publication, snapshot version/index/config pinning, source/permission revocation, real Redis outbox/idempotency and vector/FTS foundation.

Mandatory runtime gate uses separate processes for start→interrupt, restart→resume and duplicate resume retry, and checks 25 assertions. No regression assertion was disabled. Phase 1A official LangGraph checkpoint ownership, Phase 1B normalized Source of Truth/tenant, Phase 1C registry/admin, Phase 1D parsers/async provenance and Phase 1E resolution/review/versioning remain PASS.

Local full evidence: `/workspace/phase1f_final_gate4_evidence` (code SHA in local measured summary). Remote evidence contains JUnit, full log, schema/architecture/runtime JSON, immutable head/runner identities and file manifest. Final remote measured summary is obtained through GitHub Checks API; GitHub stores full gate log in the uploaded artifact. If archive download is restricted, that local-copy limitation must be recorded; do not substitute a local hash for the GitHub artifact digest.
