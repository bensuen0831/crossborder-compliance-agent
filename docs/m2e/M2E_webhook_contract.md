# Webhook transport

Subscriptions require webhook:manage and current client authority. Events: WORKFLOW_STARTED, WORKFLOW_PROGRESS, REVIEW_REQUIRED, WORKFLOW_COMPLETED, WORKFLOW_FAILED. Canonical NODE_* progress rows project to WORKFLOW_PROGRESS; no second event source.

Payload is the bounded ExternalWorkflowEvent reference envelope, not documents/evidence/provider responses. Exact event lookup remains independent of stream batch limits. Headers X-Delivery-ID, X-Webhook-Timestamp, X-Webhook-Signature authenticate exact bytes. Signature: `sha256=` + hex HMAC-SHA256(key, delivery_id + '.' + timestamp + '.' + body). Receivers verify time tolerance/signature and deduplicate delivery_id; retry preserves delivery identity.

HMAC key is recoverable only through separate tenant-scoped encrypted northbound SecretStore (INTEGRATION_SECRET_STORE_ROOT/KEY or injected factory). DB holds secret_ref only. No provider secret/key sharing. Create/rotate shows once; subsequent GET/idempotent metadata replay does not reveal it.

Callback validates scheme/credentials/host/DNS/IP before connection. EXTERNAL accepts globally routable addresses only; private callbacks require governed INTERNAL host allowlist. Sender connects to validated resolved IP and retains host/TLS authority; redirects are not followed. No global SSRF bypass. URL/event edits use CAS and revalidation.

Durable delivery history/attempt count/status; bounded exponential backoff, timeout, final failure, disable/revocation and rotated-key behavior. Callback failure cannot rollback canonical results. Test event is a transport-only reference; never a fabricated legal decision.
