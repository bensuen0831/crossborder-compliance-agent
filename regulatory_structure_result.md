# Phase 1F Regulatory Structure Result

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

Official legislation/regulator sources create existing `regulatory_structure_nodes` rows. `knowledge_structure_nodes.regulatory_structure_node_id` is a unique one-to-one extension of that canonical identity, carrying parent hierarchy, sequence, locator/number, heading, original/normalized text, language, effective date, source trace, provenance and citation. ACT/ARTICLE/SECTION/etc are stable technical node types. Nonlegal policy sources use canonical knowledge nodes without pretending to be official legal evidence.

No Article or Section authoritative table is added. Official legal structure requires a canonical source jurisdiction. Parent locators are validated for existence, duplicates and cycles before persistence; FK and unique locator constraints provide database enforcement.

PASS assertions: hierarchy, canonical legal identity equality, source jurisdiction, citation/evidence chain, parent FK rollback, duplicate-version constraint and structure-aware chunk boundary preservation. Legal interpretation/applicability is excluded.
