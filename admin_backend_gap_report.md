# ADMIN_BACKEND_GAP

All gaps below are observed in base `f563e5067308e7eab6d3f89321b8b30da7c39044`. No competing backend platform or `0008` migration was added. “Blocking” refers to the indicated product capability, not to building/testing the isolated frontend foundation.

| ID | Exact missing/limited field or contract | Why needed / affected resources | Blocking | Recommended owner |
|---|---|---|---|---|
| AUTH-01 | Browser login/session/logout contract and trusted request-context middleware; APIs require `request.state.repository_context` | Admin login and server-computed effective grants cannot be created by this UI | Yes: production browser demo | Track C + identity/security integration |
| RBAC-01 | Knowledge governance requires only `knowledge:admin`; no separate review/approve/publish/archive grants | Direct HTTP callers need operation-specific backend authorization | Yes: full requested Knowledge RBAC | Phase 1F/1G security owners |
| RBAC-02 | RepositoryContext has tenant/user/permission, optional organization; no department/project/resource permission API | Host effective grants do not prove server enforcement for these dimensions | Yes: full contextual RBAC | Security/application foundation |
| LIST-01 | No `GET /api/v1/admin/{resource}` with draft/search/filter/pagination; `/metadata/*` lists active projections only | Discover/review all drafts and complete operational queues | Yes: complete admin discovery | Phase 1C |
| VERSION-01 | No `POST /admin/{resource}/{definition_id}/versions` for most Phase 1C Admin resources | Create a new version of an existing definition, rather than a new identity | Yes: complete version maintenance | Phase 1C |
| PAYLOAD-01 | Governed artifact `_row_dict` omits `payload_json`/template/prompt content; Model deployment history omits editable payload and `version_no` | Safely reload/edit/compare persisted versions after navigation | Yes: those persisted editors/diffs; session-created draft edits work | Phase 1C |
| HISTORY-01 | No Knowledge document versions list, source/document/collection lists, version diff or audit-event API | Knowledge history and full audit evidence | Yes: complete Knowledge browsing/history | Phase 1F |
| WORKER-01 | Existing ingestion requires S3 artifact storage and a tenant-bound `KnowledgeIngestionWorker`; FastAPI starts publication only | Queued imports require a deployed ingestion consumer, storage and downloader policy | Yes: production end-to-end ingestion demo | Phase 1F deployment/integration |
| UPLOAD-01 | No binary Document Intelligence upload→Knowledge ingestion/link contract | PDF/Word/other binary upload in Knowledge operations | Yes: binary Knowledge upload; canonical text/URL imports supported | Phase 1D + 1F |
| SECURITY-01 | No Knowledge write contract/registry for sensitivity/confidentiality, external-model eligibility, download/export permissions, retention/legal-hold refs | Render governed policy values and persist security profiles without guessing | Yes: full security profile | Phase 1F + security policy owners |
| METADATA-01 | No Admin routes for product domains/tags, regulation metadata, skills or dedicated country config; no list endpoints for other Knowledge dimensions | Full initial resource coverage and metadata-only extensions | Yes: these resource operations | Phase 1C/1F; Regulation contract with Phase 1H |
| SCHEMA-01 | No shared server resource/form-schema/permission catalog endpoint | Receive descriptors and scoped policy options from authoritative config | Yes: arbitrary new resource forms without integration code | Phase 1C + Track C shared client |
| STATUS-01 | Runtime readiness endpoint exists for Knowledge versions only; no per-resource registry publication event-status API | Show actual sync outcome for ordinary metadata | Yes: generic sync status, not Knowledge status | Phase 1C registry owners |
| RECOVERY-01 | No Admin reindex/retry endpoint | Authorized recovery controls | No: existing worker retries automatically | Phase 1G operations |
| RULE-01 | Future Phase 1H Rule Admin contract has not been integrated | Consume Rule authoring contract without competing implementation | Intentional boundary | Phase 1H |

Production browser sign-in and artifact-store credentials must be provided through the deployment's supported authentication/environment settings, not chat or client-side configuration. Test context injection and the test artifact store are explicitly not production implementations.
