# Phase 1F Scope Resolver Result

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

PermissionScopeResolver, ProductScopeResolver, JurisdictionScopeResolver, ScenarioScopeResolver, IndustryScopeResolver and DataCategoryScopeResolver compose KnowledgeScopeResolver. They return KnowledgeScope / KnowledgeFilterSpec for PROJECT, DATA_ITEM or DATA_FLOW. The returned allowed binding/version set is a hard boundary for future Phase 1G queries.

Filter sequence: tenant → permission → lifecycle → version/effective date → product → jurisdiction → scenario → industry → data category → language. Unauthorized exclusion reports contain reason codes without private binding IDs. Only ACTIVE knowledge is allowed unless an existing snapshot pins historically approved knowledge. Future/non-effective, unreviewed, disabled or revoked sources are excluded.

Phase 1E context input: completed ContextResolutionRun, ProductScopeResolution, ScenarioContext, JurisdictionContext, validated DataItem/flow details, system/device/party context and validated formal BusinessFact registry references. Industry/data-category/group dimensions require structured formal metadata_refs; text inference is excluded. Missing context fails with PHASE1E_FORMAL_CONTEXT_REQUIRED.

Snapshot first freezes a project-bounded PROJECT scope version/binding set; every later item/flow scope refines that frozen set and never receives the project union as its retrieval candidate set. An empty frozen set cannot refresh into future ACTIVE knowledge. Concurrent initial creation reapplies the losing actor permission filter. The root universe includes only validated Phase 1E inventory product links bounded by the selected product domain/category/family. Product hierarchy/tag projections are frozen in that root so later subjects retain historical registry relations. Index/config pins are written once with the initial set. Snapshot pins use existing AnalysisSnapshotContextPin and AnalysisSnapshotRegistryPin tables. Saved scope/formal context are immutable; resume does not recalculate new project context. Current permission/source revocation can narrow the result. Optimistic concurrency and parent-row serialization protect publication and scope pinning.

PASS assertions: every dimension hard filter, language/effective exclusion, Cases A–E, missing formal context, historical version retention, permission revocation, source revocation and index/config pins. No vector/FTS ranking, reranker, provider SDK or LLM call occurs.
