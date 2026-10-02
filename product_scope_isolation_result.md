# Phase 1F Product Scope Isolation Result

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

| Mandatory case | Executable assertion |
|---|---|
| A: Effective Product A | A-specific + compatible DOMAIN_SHARED + GLOBAL allowed; B-specific excluded |
| B: Multi-product | DataItem A only A; DataItem B only B; DataFlow linked to A only A |
| C: Context conflict | UNRESOLVED_PRODUCT_SCOPE / review_required; only compatible global scope, no product broadening |
| D: No explicit selection | Document-formalized Phase 1E effective A is used; B excluded |
| E: Unauthorized | Secret binding/version excluded before similarity; exclusion does not expose its ID |

Product ancestry and tags are registry driven. A data item linked to a specific product beneath a selected project domain remains specific. If an item has no compatible product binding, it becomes unresolved rather than inheriting the entire multi-product project pool. A binding containing both B and a shared domain is rejected for item A because all restrictions must match.

PASS evidence: test_case_a_product_hierarchy_global_shared_and_permission, test_case_b_multi_product_minimal_item_flow, test_case_c_conflict_fail_safe, test_case_d_document_formal_context_only, test_domain_selected_item_stays_specific. Product A/B names and references exist in generic test metadata only. No search-all fallback or business-value routing is implemented.
