# Phase1I — country facade

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

CountryComplianceSkill uses application ports for resolve_profile, classify (read/validate existing H result), retrieve_country_evidence (revalidate existing G retrieval), resolve_capability and resolve_regulation_applicability. It does not perform ORM access, provider invocation, new retrieval selection, independent classification or rule version discovery.

Controlled assess_cross_border, assess_localization, resolve_filing_requirements, resolve_assessment_requirements, resolve_contract_requirements and resolve_regulator_requirements enforce the requested capability kind and return availability only. Their method names reserve integration boundaries; no legal obligation/path implementation is hidden behind them.

PostgresCountryComplianceRepository enforces trusted tenant, explicit applicability operation and project scope, actual project-version/snapshot/context relationships and actor-owned saved retrieval/result visibility. The facade never constructs a second workflow or regulation knowledge source. Generic country changes take effect through existing governance/outbox and canonical runtime reads without a restart.

Final measured code `b2312e9ec48bd05e3398c23f79dcfcf1faf69b9f`:356 full pytest /72 I tests PASS; canonical migration, schema, architecture and runtime gates PASS. Authoritative final measurements: [local_final_manifest.json](evidence/phase1i/local_final_manifest.json).
