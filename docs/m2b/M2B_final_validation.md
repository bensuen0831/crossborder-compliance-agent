# M2-B final exact-PR-head validation

**M2-B = PASS**. Tested source/runner checkout: `7fc94ba367884774026044bae444e6c7397b63fc`. Branch `milestone-m2b-document-binary-integration`, Draft [PR23](https://github.com/bensuen0831/crossborder-compliance-agent/pull/23) → main; unmerged. Original baseline `da2d420602d9c71991bcae4ffd3d33c9b3497d25` / `v3.6-m2a-pass`; preserved WIP `d78c310137415c6b06c8b0f7e945b4ed65820ab3` remains ancestor.

| Required gate | Exact-head measured result |
|---|---|
| PostgreSQL full backend | 687 PASS; 0 failed/errors/skipped/deselected; M2-B34 |
| Architecture | 151/151 +M2-A13/13 +M2-B27/27 |
| Runtime / durable HITL / restart / duplicate resume | 25/25 PASS |
| Phase1K-A / Stage1 integrity | 20/20 / PASS |
| Frontend | 97 PASS; typecheck/lint/build/i18n PASS; 0 missing owned keys |
| Real browser | M2-B3 +M2-A3 +M1 3 +M0 36 PASS; 0 retries |
| Migration | Single0013 head; fresh/exact0011/equivalence/empty down-up/retention-refusal PASS |
| Required CI | Five workflows SUCCESS at exact source HEAD |

Runtime artifact explicitly distinguishes GitHub's ephemeral PR merge ref from `tested_pr_head_sha == runner_checkout_sha == 7fc94ba367884774026044bae444e6c7397b63fc`. No evidence is borrowed from a previous head. M2-B/M2-A/M1 notices and checkout logs plus M0 raw browser/checkout logs agree. All required CI links, raw artifacts, phase B–J schema results, changed-file list and SHA256 hashes are in `evidence/m2b/final_validation.json` and `exact_head_ci/`.

- [M2B Production Document Integration](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37579548733): SUCCESS
- [M1 Intake Analysis Alpha](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37579548663): SUCCESS
- [M2A Production Intake](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37579548681): SUCCESS
- [M0 Knowledge & Evidence Preview](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37579548677): SUCCESS
- [phase1a-runtime-smoke](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37579548757): SUCCESS

Known scoped capabilities remain explicit: canonical multi-subject batch execution is unavailable and stops before legal decisions, with conflict/review priority; canonical cross-project same-binary identity is rejected409; required scanning without a provider fails closed. These gaps do not claim production provider/auth/deployment onboarding.

Final documents/evidence are committed only on `integration/m2b-pr-closure-evidence`, descended from the tested source head. This preserves the source PR SHA and its CI identity. No M2-B merge, M2-C implementation, production auth redesign or later-phase work occurs.
