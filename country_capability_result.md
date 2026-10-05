# Phase1I — generic capability boundaries

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

Typed capabilities: CLASSIFICATION, CROSS_BORDER, LOCALIZATION, FILING, IMPACT_ASSESSMENT, CONTRACT and REGULATOR. Country configuration binds capability identities, rule packs, knowledge collections/templates, required inputs and availability. The generic resolver exposes CONFIGURED, NOT_APPLICABLE, CAPABILITY_NOT_CONFIGURED, INSUFFICIENT_INPUT or REVIEW_REQUIRED with profile/capability versions and existing formal references.

Classification consumes the existing Phase1H formal result; the API validates its actual project, snapshot, item, jurisdiction and context version. Other capabilities expose configured availability/discovery only. Every CapabilityResult carries `legal_obligation=False`; future facade methods cannot produce filing, assessment, contract or regulator obligations. Missing or conflicting capability configuration is never inferred from the country name. Data-specific operations without a formal item return NOT_APPLICABLE (or the explicit insufficient-input policy).

All seven kinds have tests. Runtime metadata/API tests cover capability discovery, scope denials, governed resource dependencies and scenario-only no-data behavior. No named-country class, root graph or core jurisdiction if/else exists.
