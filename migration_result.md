# Phase 1F Migration Result

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

Alembic head = **0006_phase1f**; down_revision = **0005_phase1e**. Migration is frozen PostgreSQL DDL and does not import mutable application models. Fourteen new tables plus six knowledge_bindings extension columns reuse existing Phase 1B/C tables. FK/unique/check constraints, one ACTIVE document partial unique index, generated FTS/GIN and vector dimension constraint are included.

New tables: knowledge_documents; knowledge_document_versions; knowledge_structure_nodes; knowledge_chunks; knowledge_chunk_nodes; knowledge_ingestion_runs; knowledge_quality_results; knowledge_translations; knowledge_index_versions; embedding_jobs; embedding_records; knowledge_change_events; knowledge_version_diffs; knowledge_scope_resolutions.

Reused: knowledge_source_definitions; knowledge_collections/versions; knowledge_bindings; regulatory_structure_nodes; evidence_references; citations; admin_change_sets/review_tasks/publish_records; registry_sync_events; analysis_snapshot_context_pins/registry_pins; Phase 1E contexts and Phase 1C model metadata. No parallel source/review/legal/classification tables are added. Downgrade drops extension columns/tables in dependency order; shared pgvector extension is preserved. Downgrade is a schema operation that removes Phase 1F data, not a runtime undo operation.

PASS evidence: fresh upgrade 0001→0006 on real PostgreSQL; Phase 1F schema 29/29; all prior schema gates unchanged in assertion count, with current-head allowlists extended. Runtime checkpointer tables remain owned by LangGraph setup, not Alembic. Ingestion/lifecycle/index rollback and stale/concurrent writes are separately tested.

Empty isolated PostgreSQL migration round-trip: upgrade 0006_phase1f → downgrade 0005_phase1e → re-upgrade 0006_phase1f, all exit codes 0. See evidence/phase1f/local_final_gate/migration_roundtrip_result.json.
