# Phase1K-B D0 inventory — authority pending

Baseline: `efda0955342de8d1ea36aa0f754d63c9b421fec8`; annotated `v3.6-m2d-pass` object `dff211af565475765b921b9fe515c65630f93d47`, peeled to the same main commit. Alembic graph has one head: `0015_m2d_review_governance`. Dedicated branch/worktree: `phase1kb-multi-provider-llm-governance` / `/workspace/phase1kb-multi-provider-llm-governance`.

**Start Gate PASS. D0 is not approved for coding.** Both required V3.7 authority documents are absent from the verified tree and the available attachment directory. Their authoritative location has been requested. ARCHITECTURE_RULES.md was read; existing K-A contracts were inspected read-only. No implementation or migration has been changed.

| Question | Observed current contract |
|---|---|
| 1. Multiple provider instances? | Yes. `model_providers` has independent provider IDs and tenant-scoped unique codes; vendor is not the identity. |
| 2. Multiple models/deployments? | Yes. `model_definitions` uniqueness is tenant/provider/remote model ID; deployments bind model definition to provider version. Identical remote names across providers are representable. |
| 3. Secret reference? | `model_provider_versions.secret_ref` exists. Infrastructure resolves it through `SecretResolverPort`; a write-capable SecretStorePort/production store is not wired. |
| 4. Authoritative source? | Existing Phase1C PostgreSQL `model_providers`, `model_provider_versions`, `model_definitions`, `model_deployments`, capabilities/routing/health tables. ModelRegistry is their runtime projection. No additional registry/store is needed for provider multiplicity. |
| 5. Admin reuse? | `/api/v1/admin/models` create/draft update/review/approve/publish/history/impact routes use `PostgresModelAdminRepository` and existing outbox/governance. Current create couples a new provider, model and deployment; independent provider/model control-plane commands remain a gap. |
| 6. Admin frontend entry? | Existing canonical `/admin` includes the `models` resource. Reuse host, router, transport, session and generic governance UI; production provider list/secret replacement/connection/discovery/model-test UI is not present. |
| 7. Snapshot pins? | K-A writes `LLM_USAGE_POLICY` (tenant/project versions), `LLM_MODEL` (operation/model logical key; deployment version reference) and `LLM_PROMPT`. No invocation-policy or AUTO/SINGLE/MULTI preference contract is present. Exact model configuration immutability needs verification: `_model` reads definition/capability attributes as well as pinned deployment/provider version. |
| 8. OpenAI-compatible operations? | Chat, SSE chat stream, JSON-schema structured output, embeddings and health via GET `/models`. Generic REST additionally declares rerank/token count. GET `/models` currently returns a health boolean, not discovered model candidates. |
| 9. DeepSeek/Qwen/GLM compatibility? | No vendor-specific compatibility certification or approved preset exists in current code. Compatibility must be verified per endpoint, operation and remote model; vendor names alone do not establish support. No paid-provider PASS is claimed. |
| 10. K-A production gaps? | Trusted authorized input loading, protected production secret storage/resolution, durable audit sink, approved sensitive detection, provider DI, health/discovery orchestration, model selection, invocation triggers and document/retrieval enhancement wiring. Existing gateway policy/redaction/HTTP adapters remain reusable. |
| 11. Need0016? | Not proven. Existing schema already supports provider/model multiplicity. Decide only after reading V3.7 and verifying immutable model-selection/configuration pins and existing governed-version extension options. No migration created. |

Immediate interfaces inspected:

- `domain/llm_gateway.py` and `application/llm_gateway_ports.py`: typed request/result, candidate model, usage policy, authorized input, audit, provider and secret resolution ports.
- `application/llm_gateway_policy.py`, `llm_gateway_services.py`, `llm_gateway_redaction.py`: policy intersection, health/capability router, invocation/redaction/audit gate; no formal legal ownership.
- `infrastructure/llm_gateway_configuration.py`, `llm_gateway_http.py`: existing PostgreSQL registry/pins and generic/OpenAI-compatible HTTP protocol; SSRF/redirect/credential-echo defenses.
- `infrastructure/persistence/metadata_models.py`, `metadata_repositories.py`, `special_admin_repositories.py`; `interfaces/api/routes/admin_metadata.py`.
- `frontend/src/App.tsx`, `frontend/src/features/admin/resources.ts` and existing admin client.

Next action: obtain and completely read Master Specification V3.7 and Phase0 V3.7, then finish D0/freeze against that authority. Do not substitute V3.6 or start implementation, Stage2, M2-E or paid-provider invocation.
