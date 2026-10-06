# M2-A persistence

Baseline `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`; preserved WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b`. Implementation source is pinned in `evidence/m2a/approved_owner_overlay.json`. Full closure/exact-head CI are required before an overall PASS.

Reuse: projects, project_versions.intake_json, analysis_snapshots, api_idempotency_records, existing business_facts and context_conflicts. No ProjectIntake table or alternate Project/Snapshot/BusinessFact source.

Create captures server tenant/organization, stable project identity, creator provenance/timestamps/status/version. Draft save serializes absent idempotency keys with a transaction advisory lock, verifies expected version under the project row lock, appends a new canonical intake version, marks old version SUPERSEDED and preserves historical payload/provenance. Confirmed intake is immutable through the application; changes need a separately governed future supersede capability.

Confirmation is repeatable-read and atomic across all owning-service savepoints: audit, confirmed status, deterministic snapshot/run IDs, structured facts, context/scope/config/version pins and formal plan. Errors roll back the complete unit; concurrency serialization/deadlock has explicit409 retry semantics. No snapshot/permission authority in checkpoint JSON.

Same-value genuine document/manual input merges into one formal fact with both provenances. Conflicting values remain separate review-required facts plus existing BUSINESS_FACT_CONFLICT ContextConflict; canonical workflow creates durable ReviewTask. Unmapped fields create no fact. Published generic bindings retain exact version pins. Database guard rejects false tenant/version/actor/provenance and historical manual value mutation.
