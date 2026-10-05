# Phase1I — country profiles

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

CountryProfileConfig is a typed payload on the existing governed metadata store: canonical jurisdiction, capabilities, rule packs, knowledge collections, prompt/template version references, applicability configuration references, permission scopes, dates and optional generic localized display. Publication validates same-tenant typed references and independent review; no country table or second registry authority is created.

New profile pins are explicit, effective and ACTIVE. Canonical legal versions must additionally be READY and already authorized by the existing snapshot knowledge scope; initialization revalidates current permissions over that frozen universe. A marker freezes even an empty configuration set. Country rule packs and knowledge collections narrow applicability references. Multiple country profiles for a jurisdiction return CONFLICTED; missing/expired profiles or missing bound capability versions require review. Existing snapshots retain superseded published profile versions.

Evidence: real PostgreSQL/API tests cover profiles, effective expiry, missing capability, conflicting profiles, historical replay, scoped knowledge and a second configured jurisdiction without code changes. Runtime metadata API: GET `/api/v1/metadata/country-profiles?locale=zh-HK`; all locales use the same stable code and profile identities.

Final measured code `b2312e9ec48bd05e3398c23f79dcfcf1faf69b9f`:356 full pytest /72 I tests PASS; canonical migration, schema, architecture and runtime gates PASS. Authoritative final measurements: [local_final_manifest.json](evidence/phase1i/local_final_manifest.json).
