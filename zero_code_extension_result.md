# Phase1I — configuration-only extension

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

The PostgreSQL test publishes an additional canonical jurisdiction plus generic FILING capability and country profile through the existing metadata lifecycle. The existing outbox/RegistrySyncService produces a derived projection and is idempotent. A new validated Phase1E context/snapshot selects that jurisdiction; explicit I initialization and the same generic facade resolve the profile and NOT_APPLICABLE availability without changing Python country logic or restarting a process. The old snapshot rejects the unselected new jurisdiction.

A published new country-profile version is immediately visible through the runtime metadata API while the original applicability result retains its previously pinned profile/configuration. Scenario and capability differences live in typed payloads, not named-country classes. Generic multilingual labels similarly publish in the same version authority and are exposed through metadata APIs.

Zero-code extension configures availability and reviewed applicability rules. It does not generate or implement new legal mechanism algorithms, obligations, workflow stages, frontend translations or document generation.
