# M2-B measured validation

Local closure source: `946c3a775c4f84b3888f9fbbde1b21026bd0000e`. Approved executable owner source is recorded in `evidence/m2b/approved_owner_overlay.json`; delivery evidence changes do not alter executable bytes.

| Gate | Measured result |
|---|---|
| Full PostgreSQL backend | 687 PASS, 0 failures/errors/skips/deselections; baseline653 + M2B34 |
| Temporal prerequisite | 37 PASS, retaining original upload/parse11 and M2-A structured20 |
| Formal integration | 29 PASS |
| Crash/restart and ungoverned input | 2 PASS |
| Migration dual paths / genuine legacy backfill | 2 PASS |
| Architecture | existing151/151 + M2-A13/13 + M2-B27/27 |
| Runtime | 25/25, durable HITL/restart/duplicate resume |
| Phase1K-A / Stage1 integrity | 20/20 / PASS |
| Frontend | 97 PASS; typecheck/lint/build/i18n PASS; 0 missing owned keys |
| Browser | M2-B3, M2-A3, M1 3, M0 36; all PASS, 0 retries |

Machine-readable evidence and hashes: `evidence/m2b/local_closure_result.json`, raw reports under `evidence/m2b/local_closure/`. The M2-A browser evidence selects its three successful tests from an earlier combined report; M1 is independently certified by its corrected-manifest run. Incorrect-fixture attempts are not certified as passing gates.

First full gate measured683 PASS/4 fixture failures. Required project/version/context/flow references were added without weakening assertions or legal logic. All four focused corrections passed, followed by the required full closure retry above.

Final exact-head CI: all five required workflows SUCCESS. M2-B = PASS and M2-C ENTRY = ALLOWED. Final evidence is archived on `integration/m2b-pr-closure-evidence`, preserving the tested source branch; no M2-C implementation or merge occurs.

Final exact-head certification: [M2B_final_validation.md](M2B_final_validation.md). Tested PR HEAD `7fc94ba367884774026044bae444e6c7397b63fc`; all five required workflows SUCCESS. M2-B = PASS; no merge or next-phase implementation.
