# Security integration result

B service source remains identical to its tested source; ModelUsagePolicy precedes routing/provider invocation, restricted knowledge denies external routing, redaction proof is required and validated before external calls, failure blocks the provider, and secret_ref resolution stays inside provider transport. No Agent hard-codes a provider/model, and no LLM becomes formal legal authority or writes RuleHit/Classification.

Full Python regression includes LLM internal-only routing, external redaction-required routing/failure, restricted external denial, policy intersection, fallback/streaming constraints, secret/error/audit negative tests, H authorization and Classification rules. The explicit LLM boundary checker passes 20/20. Historical B frozen manifest is preserved; only the pinned H baseline is approved by the separate integration validation manifest, with migration additions prohibited.

The canonical M0 trusted-session boundary remains authoritative. The loopback adapter requires M0_LOCAL_UAT=1, trusted server manifest identities, HttpOnly/SameSite cookies, loopback/Host/Origin checks, no browser tenant/scope injection, and no-store responses. The synthetic PROJECT persona strips all Admin scopes on the server. API tests and real-browser requests prove 403 on approve/publish/archive and Rule detail/validation; unimplemented recovery returns 404. Tenant B cannot read A retrieval runs or evidence.

Admin presentation requires optional validated trusted admin_context, both effective grants and backend scopes. Identity switches clear state. Shared transport emits sanitized HTTP status errors and safe trace IDs; raw server validation strings are hidden. No secret values/API keys/raw logs are added to UI contracts, no secret_ref is resolved by the UI, and no fake production authentication is provided.

Limits: coarse knowledge:admin is still not fine-grained contextual backend RBAC; deployment identity/CSRF integration and security metadata remain upstream gaps. Ingestion remains disabled unless the trusted deployment confirms its infrastructure capability. See the gap matrix for owners.

Multilingual security: locale changes neither tenant/session/context nor request authority. Error rendering localizes safe status messages and hides arbitrary backend error detail. Official original_text, citation identifiers and snapshot IDs remain unchanged; locale-switch browser assertions reject any extra API write. Backend-managed names remain authoritative and untranslated when localized metadata is unavailable.
