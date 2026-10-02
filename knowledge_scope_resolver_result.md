# Phase 1F Scope Resolver Result

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

PermissionScopeResolver, ProductScopeResolver, JurisdictionScopeResolver, ScenarioScopeResolver, IndustryScopeResolver and DataCategoryScopeResolver compose KnowledgeScopeResolver. They return KnowledgeScope / KnowledgeFilterSpec for PROJECT, DATA_ITEM or DATA_FLOW. The returned allowed binding/version set is a hard boundary for future Phase 1G queries.

Filter sequence: tenant → permission → lifecycle → version/effective date → product → jurisdiction → scenario → industry → data category → language. Unauthorized exclusion reports contain reason codes without private binding IDs. Only ACTIVE knowledge is allowed unless an existing snapshot pins historically approved knowledge. Future/non-effective, unreviewed, disabled or revoked sources are excluded.

Phase 1E context input: completed ContextResolutionRun, ProductScopeResolution, ScenarioContext, JurisdictionContext, validated DataItem/flow details, system/device/party context and validated formal BusinessFact registry references. Industry/data-category/group dimensions require structured formal metadata_refs; text inference is excluded. Missing context fails with PHASE1E_FORMAL_CONTEXT_REQUIRED.

Snapshot pins use existing AnalysisSnapshotContextPin and AnalysisSnapshotRegistryPin tables. Saved scope/formal context are immutable; resume does not recalculate new project context. Current permission/source revocation can narrow the result. Optimistic concurrency and parent-row serialization protect publication and scope pinning.

PASS assertions: every dimension hard filter, language/effective exclusion, Cases A–E, missing formal context, historical version retention, permission revocation, source revocation and index/config pins. No vector/FTS ranking, reranker, provider SDK or LLM call occurs.
