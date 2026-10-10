# Idempotency, CAS and delivery

Public Idempotency-Key is normalized into canonical mutation identities: same key/payload returns existing refs; changed payload conflicts. Canonical project/intake/document/confirm/start authority is reused. Versioned updates carry expected_version; stale edits return VERSION_CONFLICT. Credential values are deliberately not replayed; metadata identity/side effects remain idempotent.

Persistent PostgreSQL advisory locks serialize absent-row idempotency and tenant/client/window/endpoint counters. Authentication failures also consume durable bounded counters. Rate/quotas are configurable IntegrationPolicy; quota/rate rejection never changes a legal result.

Technical workflow/webhook delivery uses row locks, SKIP LOCKED, durable leases and owner fencing. Expired leases can be reclaimed after process interruption; stale workers cannot complete a successor lease. Analysis deadlines and retry ceilings are separate from webhook retry ceilings; only technical retryable failures retry. Delivery invokes existing canonical START; it is not a second engine.

Official checkpointer initialization uses pg_try_advisory_lock between completed autocommit statements, with LANGGRAPH_SETUP_TIMEOUT_SECONDS (default60, bounded600). Multiple processes share the same saver schema; no parallel checkpoint store. Canonical WorkflowDelivery guards/idempotent run identity remain unchanged.
