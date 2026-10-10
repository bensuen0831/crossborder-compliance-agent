# Security boundaries

Northbound credential != southbound provider credential. External strict bodies cannot supply tenant/actor/permission/result/policy/state/checkpoint/provider endpoint/key/model authority. Registered eligible model preferences reuse Phase1KB policy/catalog/router and immutable snapshot pins.

Current authority is checked on each use; snapshots never grant permission. Scope reductions/revocations immediately deny access; wrong client/tenant cannot read or stream another project's results. Persisted opaque token digest, salted credential hash and encrypted webhook SecretStore satisfy distinct secret semantics.

Server limits JSON/request/upload size, timeout, async deadline, authentication attempts, rate/quota and stream bounds. Upload validation is canonical M2-B policy. EXTERNAL callbacks retain SSRF guards; INTERNAL requires deployment governance. Sensitive error/audit logging is allowlisted metadata only; no SQL/exception/secret/document bodies. Correlation IDs are bounded and sanitized.

Closure artifacts contain sanitized measured JSON/JUnit only, no fixture secrets/provider input logs/browser traces. Secret-bearing Admin browser tests disable traces/screenshots and remove one-time output before failure DOM capture.

Remaining deployment responsibilities: TLS, protected persistent encrypted secret root/key, governed callback allowlist/file/security policy, Admin auth/SSO/session ingress, rate/timeout policy injection and operational backups. No production auth/host redesign in M2-E. Mandatory acceptance uses local protocol-realistic providers; paid Internet LLM NOT EXECUTED.
