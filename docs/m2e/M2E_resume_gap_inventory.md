# M2-E resume gap inventory

Inspected checkout: `df2e2e0b8552ab2172f02ce2d79f1ef911660efb`.
Base: `0f5a40c5ca3a8771624fb38e9380856d79e67342`. PR27 is open/draft; working tree was clean. This inventory records source inspection and historical measured evidence, not final-head closure.

| Capability | State | Evidence / remaining work |
|---|---|---|
| R1 classification identity, bindings, rule pins, historical replay | DONE + empirically tested | Frozen R11 report/JSON:893 backend,280 architecture,25 runtime. Preserve0018 and all owning contracts. |
| IntegrationClient, OAuth, service credentials, scrypt, rotation/revocation | DONE + empirically tested | `test_m2e_identity_postgres.py`; current-head security/HTTP closure still required. |
| Canonical RepositoryContext, centralized scopes, project binding | DONE + empirically tested | Identity and real HTTP create/read/CAS/cross-client tests. No system actor shortcut. |
| External intake create/read/update/confirm | DONE + empirically tested | Canonical façade and original distinct-jurisdiction HTTP vertical slice. |
| Document upload/parse, eligible catalog, model preference | IMPLEMENTED BUT NOT CLOSED | Canonical services reused; broaden denial/idempotency acceptance. |
| Async start/status/result | IMPLEMENTED BUT NOT CLOSED | Real workflow happy/review vertical slice passes historically; lease/restart/failed-delivery projection needs tests. |
| SSE | IMPLEMENTED BUT NOT CLOSED | Canonical allowlisted projection; historical isolation test. Terminal/reconnect/revocation closure missing. |
| WebSocket | PARTIAL | Shares event DTO; real HTTP acceptance/reconnect/isolation and terminal handling missing. |
| Webhook persistence/signature/retry/SSRF | IMPLEMENTED BUT NOT CLOSED | Actual HTTP200/500/timeout/bounded failure and encrypted key tests exist. Subscription edit/admin-disabled management/event lookup closure missing. |
| Idempotency/CAS | IMPLEMENTED BUT NOT CLOSED | PostgreSQL advisory locking and canonical owners; expand mutation replay/conflict and concurrency coverage. Secrets intentionally shown once. |
| Rate limit/quota | PARTIAL | Atomic durable counters exist; OAuth authentication limits and restart/concurrent acceptance missing. |
| Audit/correlation/errors | PARTIAL | Safe envelope/operation audit exists; scope/correlation propagation and typed error matrix need closure. |
| Admin Integration UI | NOT IMPLEMENTED | Extend existing canonical frontend only; add client/binding/webhook control plane and three locales. |
| External-only OpenAPI | NOT IMPLEMENTED | Public route-only export, strict/security/error contract tests required. |
| Python/TypeScript SDK | NOT IMPLEMENTED | Transport-only typed clients, polling/upload/events helpers and build/import tests required. |
| M2-E architecture checks | NOT IMPLEMENTED | Additive checks above frozen280, with authenticated finite successor ownership evidence. |
| Migration gates | DONE + empirically tested | R11 actual PostgreSQL dual paths/equivalence/safe downgrade/refusal/re-upgrade; frozen0001–0017 identity. Rerun final closure; no new schema justified. |
| Checkpointer concurrency/restart | IMPLEMENTED BUT NOT CLOSED | Existing runtime initialization fix; dedicated parallel/restart acceptance needed. |
| Admin browser smoke | NOT IMPLEMENTED | Real backend three-locale journeys, retain all57 baseline tests; zero retries. |
| Dedicated M2-E CI | NOT IMPLEMENTED | Reuse repository-declared PostgreSQL/providers; unpublished cloud draft is not a runner dependency. |
| Full final-head regression / CI | NOT IMPLEMENTED | Historical893/280/25 are recovery evidence only. Run one full closure after product completion and exact PR-head CI. |

No new schema need has been proven. No second legal/result/event/runtime authority is authorized. Paid Internet LLM acceptance is excluded; Stage2 and Full Stage1 E2E remain unstarted. No merge/tag authorization exists.

Next action: close gateway event/security/administration gaps with focused real PostgreSQL/HTTP tests, then frontend/OpenAPI/SDK/CI. Preserve all historical R1 evidence.

## Resume implementation checkpoint

All previously PARTIAL/NOT IMPLEMENTED channel items are now implemented. Canonical Admin clients, bindings and webhooks, external-only OpenAPI, transport SDKs and dedicated CI exist. Local full checkout4467e4e measured908 backend,307 architecture,25 runtime,135 frontend and60 browser (all original57 plus M2E3),0 failures/errors/skips/deselections/retries. Migration paths/refusal, distinct-jurisdiction DOCX/RAG workflow and review, SSE/WS, local HTTP callbacks and parallel saver/restart tests passed.

Final supplementary security/contract12 tests passed; canonical/internal draft update, external read, document universe and confirmation snapshot are compared in the original real HTTP vertical fixture, before exact Stage1ResultService output comparison. These corrections add2 tests. Credential expiry acceptance uses the governed model:select scope required by canonical default AI preference; no permission bypass. Failed OAuth audit retains an unauthenticated actor while identifying the server-owned client/tenant, never treating a supplied ID as authenticated authority.

Remaining: exact final-head mandatory CI and immutable measured archive. No unpublished cloud setting is required; CI declares PostgreSQL/Redis and secret-safe protocol fixtures. Paid Internet LLM endpoints NOT EXECUTED. Main integration PENDING; Full Stage1 E2E BLOCKED; Stage2 NOT STARTED.

Exact-head checkpoint35aef76: dedicated M2E measured910 backend,307architecture,25runtime,135frontend,60browser/0retries PASS. Legacy static job exposed missing runtime markers on3 PostgreSQL cases; corrected without altering full-gate selection or product source. All mandatory CI reruns on the successor; previous SHA evidence cannot close that successor.

Final scope audit found an unexposed existing canonical successor operation: confirmed A/B/DOCX/RAG S1 plus external POST intake/supersede returned404. Existing canonical ProjectDocument persistence already owns controlled supersede. Minimal generic port/service delegation, external façade/route and SDK wrappers close the channel gap; CAS/idempotency plus new confirmed Snapshot and unchanged historical S1 are tested in the original vertical fixture. No new model/table/legal engine. Ownership enumeration explicitly adds the canonical document_upload port/service and existing external_channel adapter; all other frozen owners remain protected. Final CI reruns after source completion.
