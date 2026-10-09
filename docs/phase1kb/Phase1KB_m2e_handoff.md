# M2-E northbound contract boundary — freeze only

Entry decision: M2-E EXTERNAL AGENT API ENTRY = ALLOWED after Phase1K-B exact-head closure PASS at `d74bca4b61178637f24302d8b1fa6baa4f05ea59`; all eight CI workflows SUCCESS. See `Phase1KB_final_exact_head_validation.md`. No M2-E implementation exists in this task. Stage1 full E2E remains blocked until M2-E main closure; Stage2 NOT STARTED.

| Future contract | Required boundary |
|---|---|
| ExternalAnalysisInput | Typed canonical intake fields and client idempotency key; server tenant/actor/project authority; no policy/final-result injection. |
| ExternalDocumentUpload | Authorized project/draft CAS, binary stream, configured file/security policy; canonical DocumentVersion/ParseRun/SourceTrace. |
| ExternalModelSelectionPreference | MINIMAL/STANDARD/ENHANCED and AUTO/SINGLE/MULTI_MODEL with registered model IDs only; advisory until current backend eligibility revalidation. |
| ExternalAnalysisStart | Confirmed authorized exact snapshot and idempotency; immutable model/input pins; canonical delivery/runtime only. |
| ExternalAnalysisStatus | Authorized run/project/snapshot correlations and canonical stable events, no raw LangGraph state. |
| ExternalStage1Result | Existing owning formal results/presentation contract; legal ownership and historical temporal semantics unchanged. |
| WebhookEvent | Stable event ID/version, tenant integration binding, run/snapshot refs; authenticated delivery/idempotency and bounded retries; no credentials/evidence body by default. |
| IntegrationClientCredentialBoundary | Third-party-to-agent identity separate from agent-to-provider secret; no provider key/base URL/unregistered model accepted northbound. |
| IdempotencyBoundary | Existing project/intake/document/start keys and CAS authority; channel never selects an alternate legal engine. |

All northbound operations must enter the same authenticated Application Use Cases as Web UI, revalidate permission on every operation, and preserve the exact Knowledge Scope, Snapshot and M2-D Review authority. External client never calls RuleEngine/LangGraph/Provider directly. Model preferences are frozen on confirmation; changing them requires a successor analysis. LLM-derived candidates/explanations never become evidence/legal authority. Southbound provider credentials remain write-only SecretStorePort data and are never external integration credentials.

## Canonical contract bindings (frozen, not new endpoints)

| Northbound name | Existing typed authority / permitted payload |
|---|---|
| ExternalAnalysisInput | `CreateProjectFromIntake(name, idempotency_key, facts: IntakeFacts)`; updates use `UpdateIntakeDraft(expected_version, idempotency_key, facts)`, confirmation uses `ConfirmProjectIntake(expected_version)`. `IntakeFacts` derives the single `ProjectIntakeContext` minus server authority fields. |
| ExternalDocumentUpload | Existing draft-document multipart stream and `DraftDocumentRequest` CAS/idempotency; response `DocumentInputsView` with canonical document/version/parse identities. No base64 JSON or client storage key. |
| ExternalAnalysisStart | Existing empty, extra-forbid `WorkflowStart`; authorized project/snapshot route identities, no client run/policy/fact injection. |
| ExternalAnalysisStatus | Existing `WorkflowView`: run/project/snapshot IDs, stable status, step, bounded result references/reasons and review/fallback references. |
| ExternalStage1Result | Existing snapshot-scoped `Stage1ComplianceResult` from `Stage1ResultService`; presentation locale never changes owning legal results. |
| WebhookEvent | Versioned envelope over canonical `WorkflowEventDTO`; event ID/code, integration subscription identity, tenant/run/snapshot correlation, result refs, creation timestamp and signature/delivery metadata. Never raw LangGraph state or provider output. |

Future external schemas must reject unknown authority fields, use the same server-owned `TenantContext`/`PermissionContext`, and retain canonical command validation, optimistic concurrency, idempotency and current authorization. Integration credentials are scoped/revocable northbound identities; they never resolve or expose southbound provider secrets. M2-E owns gateway credentials, webhook persistence/retries and production endpoints; none are implemented here. Published discovery and model selection remain governed control-plane/use-case operations, not external registry writes.
