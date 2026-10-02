# Phase 1F Actual API Contracts

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

Routes below are introspected from the implemented FastAPI router, not copied from a design proposal.

| Method | Actual route | Handler |
|---|---|---|
| POST | `/api/v1/admin/knowledge-sources` | `create_source` |
| GET | `/api/v1/admin/knowledge-sources/{source_id}` | `get_source` |
| PATCH | `/api/v1/admin/knowledge-sources/{source_id}` | `update_source` |
| POST | `/api/v1/admin/knowledge-documents` | `create_document` |
| POST | `/api/v1/admin/knowledge-documents/{id}/versions` | `create_version` |
| GET | `/api/v1/admin/knowledge-versions/{id}` | `get_version` |
| POST | `/api/v1/admin/knowledge-versions/{id}/ingest` | `ingest` |
| POST | `/api/v1/admin/knowledge-versions/{id}/validate` | `knowledge_validate` |
| POST | `/api/v1/admin/knowledge-versions/{id}/submit-review` | `knowledge_submit-review` |
| POST | `/api/v1/admin/knowledge-versions/{id}/approve` | `knowledge_approve` |
| POST | `/api/v1/admin/knowledge-versions/{id}/publish` | `knowledge_publish` |
| POST | `/api/v1/admin/knowledge-versions/{id}/supersede` | `knowledge_supersede` |
| POST | `/api/v1/admin/knowledge-versions/{id}/expire` | `knowledge_expire` |
| POST | `/api/v1/admin/knowledge-versions/{id}/archive` | `knowledge_archive` |
| GET | `/api/v1/admin/knowledge-ingestion-runs/{id}` | `get_run` |
| GET | `/api/v1/admin/knowledge-versions/{id}/structure` | `knowledge_structure` |
| GET | `/api/v1/admin/knowledge-versions/{id}/chunks` | `knowledge_chunks` |
| GET | `/api/v1/admin/knowledge-versions/{id}/bindings` | `knowledge_bindings` |
| GET | `/api/v1/admin/knowledge-versions/{id}/quality` | `knowledge_quality` |
| POST | `/api/v1/projects/{project_id}/knowledge-scope/resolve` | `resolve` |
| GET | `/api/v1/projects/{project_id}/knowledge-scope` | `project_scope` |
| GET | `/api/v1/data-items/{subject_id}/knowledge-scope` | `data_item_knowledge_scope` |
| GET | `/api/v1/data-flows/{subject_id}/knowledge-scope` | `data_flow_knowledge_scope` |

Request DTOs use extra=forbid, UUID identities, explicit input source, limits and lifecycle expected_record_version. Response contracts are KnowledgeSource, DocumentDTO, VersionDTO, RunDTO, StructureDTO, ChunkDTO, KnowledgeBinding, KnowledgeQualityResult and KnowledgeScope. Responses are DTO/dict projections; ORM instances are not returned. Ingestion response excludes its queued input/audit data. Errors: 401 missing trusted context, 403 admin permission, 404 scoped absence, 409 stale version, 422 invalid input/lifecycle. Knowledge permission is read from server-injected RepositoryContext, never client headers.

Admin requires knowledge:admin or system for ingestion; independent human review still excludes system/self approval. Runtime requires tenant-scoped formal project/subject context and binding permissions. Runtime GET returns a resolved scope projection; POST resolves and snapshots when requested. Durable worker is deployed separately with configured TaskQueuePort/ObjectStoragePort; API does not execute ingest synchronously or use LangGraph.

PASS assertions: real PostgreSQL TestClient 202, typed structure/chunk/binding/quality payloads, scope response, tenant 404 and unauthorized admin 403. Registry API regression remains PASS. Translation/index operations are application/repository foundation methods; extra translation/index HTTP routes are excluded from this release.
