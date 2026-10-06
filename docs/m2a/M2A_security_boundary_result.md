# M2-A security boundaries

Baseline `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`; preserved WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b`. Implementation source is pinned in `evidence/m2a/approved_owner_overlay.json`. Full closure/exact-head CI are required before an overall PASS.

Trusted RepositoryContext supplies tenant, organization and current permissions; browser facts cannot supply them. Every create/read/save/confirm/START/READ checks current tenant/project/actor/action authority. Snapshot never grants permissions. Exact project action grants derive from revalidated canonical creator provenance or an existing explicit grant. Registry pin permissions are rechecked on host reconstruction/read/use.

Optimistic expected-version conflict prevents silent overwrite. Idempotency is tenant+actor scoped, payload fingerprinted and serialized; duplicate confirmation has deterministic snapshot/run refs. REPEATABLE READ concurrent transactions return409 for a fresh retry. Historical confirmed fact provenance/value is protected by PostgreSQL trigger.

Real PG tests cover cross-tenant/other-actor/current-permission denial; malformed browser authority; unknown metadata/document/party references; rollback; provenance tenant/version/actor/value tamper; duplicate/restart and no fabricated formal decisions. Genuine document evidence is never silently replaced by manual facts. Conflict uses ContextConflict/ReviewTask, not an M2 store.

Production authentication/CSRF/RBAC/host redesign is out of scope. Browser UAT uses the existing explicitly enabled loopback-only trusted session adapter, never frontend tenant headers.
