# M2-A design

Baseline: `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1` (`v3.6-m1-phase1lb-pass`). Original WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b` preserved.

API → ProjectIntakeService → existing Project repository port/adapter → canonical `projects`, `project_versions.intake_json`, `analysis_snapshots`. Draft updates append immutable payload versions with optimistic concurrency. Confirmation uses one repeatable-read transaction, authorized owner services and joined savepoints; failed preparation rolls everything back. Snapshot/run identities derive deterministically from the exact confirmed version.

Confirmed structured input converges on existing `business_facts` at ContextResolutionService, before context pinning. Governed BUSINESS_FACT_TYPE MetadataVersion payload optionally contains `structured_intake_binding: {field_path, value_type}`. Existing definition-to-definition MetadataBinding cannot identify structured fields; this minimal versioned payload extends the existing registry rather than introducing a binding store. Reviewed/published/effective, authorized mappings only; unknown fields do not fabricate facts. Values and field identity are never country/product/scenario-specific Python mappings.

Document input retains Candidate → Resolution → BusinessFact with genuine document SourceTrace. Structured input uses the existing ProvenanceDTO (`USER_INPUT`) carrying exact intake version, field path, original value, confirmation actor/time and snapshot audit reference. Same values retain both sources on one authoritative fact; differing values generate existing BUSINESS_FACT_CONFLICT / ContextConflict and durable review.

Missing facts or required configured fact types stop at INSUFFICIENT_INPUT/WARNING in the application orchestration boundary. Phase1I/J engines, canonical graph/runtime/checkpointer remain unchanged. No authoritative decisions or fact payloads in graph state.

Migration0011 adds structured provenance on existing BusinessFact plus a database provenance/immutability guard; no table or source of truth added. Empty downgrade is supported; retained manual authority requires explicit archive/export before downgrade.

Existing four-step H5/root/router/query client/transport/i18next remain canonical. Browser sends bounded canonical facts, expected version and idempotency key; no tenant/policy/result/run authority. Locale is presentation only. Binary upload, visualization, review UI/resume, LLM providers, production auth/host and Stage2 remain excluded.
