# Phase1K-B contract freeze

Baseline `efda0955342de8d1ea36aa0f754d63c9b421fec8`; pre-development documentation head `e2fe4820337ac07fac7ca45e16aff597f81242b6`. D0 PASS precedes executable changes. Draft PR #26 targets main.

Reuse the K-A LLMService, ModelUsagePolicyService, ModelRouter, redaction, HTTP adapters, Phase1C PostgreSQL provider/model/deployment/governance, PromptRegistry, canonical audit and SnapshotRegistryPin. Application invocation orchestration is a use case over this gateway, never another gateway/runtime/registry. All legal owners remain unchanged.

Invocation policy is a typed payload in existing governed MetadataVersion, kind `LLM_INVOCATION_POLICY`. Tenant/project usage policies intersect as before. A trigger permits candidate/derived work only; formal decision purposes and Stage2 triggers are denied. Unknown data protection labels remain internal-only; unavailable trusted redaction blocks external invocation.

Provider instances have independent IDs. Protocol selects a thin infrastructure adapter; vendor presets never choose business/legal behavior. Independent provider configuration uses immutable existing provider versions and canonical review/publish/outbox. Models reference those versions; deployment `configuration_json` freezes remote name, capabilities, operations, token limits and priority. Current enablement/access/health are revalidated separately. This missing immutable payload justifies one additive `0016_phase1kb_multi_provider_llm_governance`; frozen0001–0015 remain byte-identical.

SecretStorePort extends the existing resolver boundary. A protected encrypted local adapter requires an externally supplied key and private configured root; no implicit key generation, plaintext metadata or credential response. Other secret backends implement the same port. Replacement creates a new immutable reference/provider version. Audit stores identities/status only. Provider errors expose stable sanitized codes.

Draft AI preferences belong to the existing typed intake; confirmation freezes selection, exact deployments/provider versions, usage/invocation policies and prompts into the canonical snapshot before enhancement. Unconfigured LLM capability is recorded and remains unavailable for that snapshot; future metadata must not silently activate it. SINGLE never falls back to another model; MULTI requires ENHANCED and server-policy bounded2..N calls, independently audited, with candidate/derived outcomes only.

Document enhancement runs at the existing confirmation preparation boundary before formal context pinning. It uses genuine parsing/provenance and candidate validation/resolution, never patches a completed snapshot's input universe. Query expansion is one bounded retry after owned sufficiency says insufficient; the exact same snapshot/scope/filter policies remain authoritative. LLM words cannot become Evidence/LegalBasis.

K-B gates are measured sequentially. Stage2 generation and M2-E code are excluded. Full regression and exact-head CI are required before final PASS.
