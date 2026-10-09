# M2-E northbound contract boundary — freeze only

Entry decision: PENDING Phase1K-B exact-head closure. No M2-E implementation exists in this task. Stage1 full E2E remains blocked until M2-E main closure; Stage2 NOT STARTED.

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
