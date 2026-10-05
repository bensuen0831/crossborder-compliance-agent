# Phase1I — scenario adjustment

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

`ScenarioAdjustmentConfig` / `ScenarioAdjustmentProfile` use canonical SCENARIO and SKILL identities in MetadataDefinition/Version. Required/optional inputs, required/conditional/disabled skills, required capabilities, knowledge/rule/template bindings, sufficiency-profile reference, outputs, bounded risk priorities, explicit checks, effective dates and review provenance are versioned configuration. Risk priorities are never calculated risk results.

`merge_scenario_profiles` sorts identities, merges set-valued requirements, evaluates explicit conditional input predicates and retains every profile/version. Missing required inputs produce REVIEW_REQUIRED; required/disabled skill, sufficiency profile, priority or check disagreement produces explicit conflict codes. Required and activated conditional skills cannot disappear silently. The standard pipeline cannot be replaced or reordered; no LangGraph or workflow modifications were made.

Explicit initialization pins profile/skill versions and binding digests in existing AnalysisSnapshotRegistryPin. New prompt/template dependencies require effective ACTIVE versions and the existing AdminPublishRecord. Historical replay retains exact version references; changed bindings fail closed. Knowledge bindings must remain within Phase1G's revalidated pinned scope, rule bindings within Phase1H's rule pins, and the evidence requirement must be the actual pinned Phase1G policy family.

Evidence: `tests/test_phase1i_domain.py` deterministic ordering, conflicts, conditional/missing inputs, immutable pipeline; `tests/test_phase1i_postgres.py` real publication, profile history, snapshot isolation and controlled template availability. No custom graph, risk computation or frontend.

Final measured code `b2312e9ec48bd05e3398c23f79dcfcf1faf69b9f`:356 full pytest /72 I tests PASS; canonical migration, schema, architecture and runtime gates PASS. Authoritative final measurements: [local_final_manifest.json](evidence/phase1i/local_final_manifest.json).
