# Phase 1F Chunk & Binding Result

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation**.

Tested SHA: `1784f10409012918aae709e2a5dc492edbe272e2`. Run ID: `36968764193`. Attempt: `1`.
Final evidence Source of Truth: [phase1f_final_remote.json](evidence/phase1f_final_remote.json).
Artifact ID: `11210258936`. Artifact digest: `sha256:5fe9dcefcdd266127b5fa081bfb5f31c53dc5c33d57bbff5385d11c1ca5d07bc`.

| Empirical assertion | Actual result |
|---|---|
| Full PostgreSQL/runtime pytest | **137 passed / 0 skipped / 0 deselected** |
| Alembic head | **0006_phase1f** |
| Phase 1F schema | **29/29 PASS** |
| Architecture executable checks | **77/77 PASS** |
| Phase 1A runtime/checkpoint/restart/resume/retry | **25/25 PASS** |
| Phase 1B / 1C / 1D / 1E schema regression | **16/16; 20/20; 15/15; 22/22 PASS** |
| Phase 1A–1E full regression | **PASS** |

Above values are independently verified through GitHub Checks measured evidence for the identified CI run; they do not reuse Phase 1E totals. The local full gate at `5acbcd1813cb80a2bd3d0f92d04dc68f5d4fc3db` is separate corroborating evidence. The linked remote manifest pins the immutable pre-issuance baseline. Later governance commits contain documentation/evidence only and retain the tested implementation.

Known exclusions: Phase 1G retrieval/ranking/reranking/RAG/answer generation, classification, regulation applicability, country rules, risk and compliance paths are excluded. Ingestion currently supports approved canonical structure JSON upload or controlled HTTPS JSON sources; automatic legal PDF/DOCX import, external site crawling, actual model-provider execution and affected-project impact calculation are excluded. Storage/embedding tests use explicit adapters; PostgreSQL and Redis are real. Whitespace token counting is a deterministic foundation measure, not provider tokenizer equivalence. Local PostgreSQL 17.11/Redis 8.0.2 are separately identified from CI PostgreSQL 16/Redis 7.

Authoritative boundary: PostgreSQL canonical knowledge tables; Phase 1C source definitions/collections/bindings and model metadata are reused; Phase 1B RegulatoryStructureNode/EvidenceReference/Citation and durable admin review are reused. Object storage retains original artifacts. Registry, FTS and pgvector are derived projections/indexes. Formal Phase 1E context is the only context input.

Chunks are derived from canonical structure and retain knowledge version, node links, citation references, original/normalized text, deterministic whitespace token count, language/sequence/locator, content hash and strategy version. `knowledge_chunk_nodes` makes the provenance relation structural. Strategies: STRUCTURE_AWARE, ARTICLE, SECTION, PARAGRAPH, TABLE, SLIDING_WINDOW; windowing stays inside a canonical node.

Binding dimensions: jurisdiction/group, product domain/category/family/product/tag, scenario, industry and data category; permission scopes are a separate hard filter. Scope types PRODUCT_SPECIFIC, DOMAIN_SHARED, CROSS_PRODUCT and GLOBAL have validation boundaries. GLOBAL cannot conceal a product restriction. Non-global binding requires a bounded product dimension. All restrictive dimensions must match; sharing a domain does not rescue an incompatible explicit product.

Binding versions are reviewed with the document version and immutable after review. Changes require a new version. Effective dates, tenant ownership and approved registry references are validated. No binding schema is a classification or regulation decision.

PASS assertions: chunk/node/citation FKs and hashes, node boundaries and all strategy types; multi-dimensional binding, registry ancestry/tag resolution, tenant rejection, effective-date filtering and reviewed immutability.
