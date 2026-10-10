# External API v1

Public authority: `sdk/openapi/external-v1.json` (OpenAPI3.1, product schema1.0.0); served at `/api/v1/external/openapi.json`. Internal/Admin/debug routes are excluded. Breaking changes require a new version, never silent mutation.

All requests use HTTPS in deployment, Bearer authentication, optional `X-Correlation-ID`. Mutations require `Idempotency-Key`. Canonical strict request schemas reject tenant/actor/policy/result/provider/state injection.

| Operation | Path under `/api/v1/external` |
|---|---|
| OAuth client credentials | POST `/oauth/token` (form) |
| Project+initial draft | POST `/projects` |
| Read/update draft | GET/PUT `/projects/{project_id}/intake` |
| Real multipart upload | POST `/projects/{project_id}/documents` |
| Parse/unlink | POST `/projects/{project_id}/documents/{document_version_id}/parse`; DELETE `/projects/{project_id}/documents/{document_version_id}` |
| Eligible models | GET `/projects/{project_id}/eligible-models` |
| Confirm | POST `/projects/{project_id}/intake/confirm` |
| Async start | POST `/projects/{project_id}/snapshots/{snapshot_id}/workflow` (empty strict body,202) |
| Status/result | GET `/workflows/{run_id}` or `/stage1-result` |
| SSE | GET `/workflows/{run_id}/events` |
| WebSocket | `/ws/workflows/{run_id}` |
| Subscriptions | `/webhook-subscriptions` and versioned subscription mutations/history/test |

Quick start: Admin creates scoped client → obtain OAuth token with `grant_type=client_credentials` (or use service credential) → create project with canonical `facts` → multipart file+expected_version → parse using returned document version and intake version → optional model preference through canonical intake update → confirm → POST empty workflow request → poll returned status_url → fetch result_url. Uploads retain canonical file policy/signature/size checks, real ParseRun/SourceTrace/resolution.

CRUD/status reads are synchronous. Analysis is async-first:202 returns project/snapshot/run/status/result/events refs. Drafts cannot manufacture snapshots or runs. Confirmation pins formal inputs/documents/knowledge/policies/models. Changed confirmed inputs require canonical successor semantics; no historical snapshot mutation.

Errors: `error_code,message,details,trace_id,retryable`; no exception/SQL/secret text. Scope/tenant/project denial is safe. Rates/quotas return429 withRetry-After. Codes include UNAUTHORIZED, FORBIDDEN, INVALID_SCOPE, PROJECT_ACCESS_DENIED, IDEMPOTENCY_CONFLICT, VERSION_CONFLICT, INVALID_INPUT, DOCUMENT_REJECTED, MODEL_SELECTION_NOT_ALLOWED, WORKFLOW_NOT_FOUND, RESULT_NOT_READY, RATE_LIMITED, QUOTA_EXCEEDED, CAPABILITY_NOT_CONFIGURED. Existing owning prerequisite failures remain controlled; no fabricated formal result.
