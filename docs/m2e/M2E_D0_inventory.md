# M2-E D0 inventory

Start gate PASS: clean `main` and `origin/main` both `0f5a40c5ca3a8771624fb38e9380856d79e67342`; annotated `v3.7-phase1kb-pass` object `b5aacaf6af0ab526de25f6d06d195ef4ece92727` peels to that exact commit. Single Alembic head0016. Dedicated branch/worktree `milestone-m2e-external-agent-api` created directly from this commit. No history rewrite or prior WIP modification.

Required V3.7 Master/Phase0/change-summary, architecture rules, K-B handoff/model selection, M2-A/C APIs and M2-D review/correction/resume/successor contracts inspected. Their historical pending notes are superseded by the user's verified main/tag, not treated as new architecture. Paid Internet LLM endpoints remain NOT EXECUTED.

| # | Question / current authority |
|---|---|
|1|FastAPI composition: `interfaces/api/main.py`; canonical workflow/intake/document/review composition: `interfaces/api/workflow_app.py`. Extend this one app.|
|2|`dependencies.get_repository_context` receives trusted `request.state.repository_context`.|
|3|Authentication is deployment/channel-owned before this dependency; there is no OAuth implementation. External Bearer authentication must produce canonical RepositoryContext without trusting browser identity headers.|
|4|`domain/security.py` PermissionContext; existing owners validate action scopes and exact project grants, tenant/creator provenance. Central external scope mapping will derive these same capabilities only after live client/project-binding checks.|
|5|`application/intake_services.ProjectIntakeService.create(CreateProjectFromIntake)` via `infrastructure/intake_composition.intake_service`.|
|6|`application/document_upload` / `document_input_composition.document_input_service`; existing stream/file/scan/storage/type policy and DocumentInputsView.|
|7|`ProjectIntakeService.confirm(ConfirmProjectIntake)` and existing `prepare_snapshot` pin owners.|
|8|`routes/workflow.start` invokes canonical `formal_workflow_runtime` / WorkflowDeliveryService. Existing START delivers synchronously; external202 needs durable technical delivery scheduling around that same application runtime.|
|9|`WorkflowReadProjection` plus authorized runtime view behind canonical `WorkflowView`.|
|10|`application/stage1_result.Stage1ResultService`; canonical route reconstructs pinned readers without recomputing legal results.|
|11|`domain/contracts.WorkflowEventDTO`; runtime persists canonical events in `workflow_events`. External projection will allowlist compact fields only.|
|12|`application/llm_model_catalog`, composition and `routes/llm_models`: existing EligibleModelCatalog and ModelUsagePolicy/Router.|
|13|Canonical `IntakeFacts.ai_model_preference`, `llm_snapshot_pins.freeze_llm_configuration`; confirmed snapshots cannot be mutated.|
|14|Canonical create/update/upload use actor-scoped api_idempotency_records and CAS; confirmation/run/delivery are canonical identity-idempotent. Public header adaptation adds payload comparison for otherwise header-less operations using the existing API-idempotency authority.|
|15|Existing document parse task/Redis queue, publication outbox, WorkflowDelivery guards and canonical events are reusable foundations. New technical delivery jobs do not hold graph state or create runs/decisions.|
|16|No webhook subscription/delivery persistence, signing or sender exists.|
|17|No IntegrationClient/ServiceAccount/project-binding persistence exists; ApiIdempotencyEntity already has api_client_id namespace.|
|18|No OAuth2 Client Credentials adapter or one-way credential-hashing utility. Use mature stdlib scrypt, revocable opaque short-lived tokens, current credential-generation checks; service credentials converge on the same client/context.|
|19|No rate/quota adapter exists. Add centrally configured atomic PostgreSQL counters, scoped tenant/client/endpoint-class; separate from compliance decisions.|
|20|0017 necessary: integration clients, hashed credentials/tokens, project bindings, encrypted-reference webhook subscriptions, durable delivery attempts/jobs and governance counters. No second business/permission/result/registry store. Frozen0001–0016 unchanged.|

## Approved implementation boundary

External `/api/v1/external` is a versioned façade over the same application use cases; admin Integrations uses the existing host. Authenticated actor is `integration:<client_id>`. Live client scope/credential and tenant/project binding are checked on every operation, event poll and worker execution. No system context, alternate engine, LLM/provider direct invocation, raw checkpoint contract or third-party ReviewDecision is permitted.

Reuse canonical DTOs and shared orchestration composition; factor existing route orchestration into application-facing composition only when needed, preserving internal contracts. Durable delivery job pins canonical run/context references and revalidates current authority; existing runtime owns all legal execution/checkpoint/retry semantics. Events are projections from the existing canonical event rows, not another event source. Webhook outbox/delivery references these events, signs exact bounded envelopes with a northbound encrypted SecretStore reference, retries independently and never rolls back workflow results.

OAuth/client/service secrets persist only scrypt hashes; token bearer values persist only non-reversible random-token digests and have TTL/revocation checks. Webhook HMAC requires recoverable key material: reuse encrypted SecretStorePort with a distinct northbound factory/namespace, never plaintext DB or southbound provider access. Production secret-store configuration must fail closed when unavailable. Endpoint validation reuses existing SSRF-governed transport boundaries; no redirects or private EXTERNAL destinations. Rate/quota and idempotency are server-owned, atomic and restart-safe.

D0 INVENTORY = PASS. This is an inventory/design gate; empirical security, parity, migration and full closure remain pending.
