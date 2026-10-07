# M2-C local closure and final CI acceptance

Original baseline: `42571c7148456f41adb64d2528c169a357214a25` / `v3.6-m2b-pass`. C0 measured PASS checkpoint: `ee9bf85503b618f0f26f782446f9a1365f593992`, committed before C1 implementation.

| Gate | Measured local result |
|---|---|
| Mandatory backend | 727 PASS: baseline687 +40 M2-C;0 failed/errors/skipped/deselected |
| Architecture | 151 existing +13 M2-A +27 M2-B +15 C0 +15 C1 =221/221 |
| Runtime | 25/25;real PostgreSQL/durable checkpoint/restart/duplicate delivery |
| Frontend | 108 PASS;typecheck/lint/build PASS |
| Localization | zh-CN/zh-HK/en-US,494 keys each,0 missing keys/hard-coded UI strings |
| Browser | M2-C3/M2-B3/M2-A3/M1 3 +M0 36;0 retries/skips/flaky |
| Presentation correction | Additional M2-C3/3:light workspace/navy sidebar/no page overflow/0 missing keys |
| Migration | Single0014;fresh/exact verified0013 upgrade/catalog equivalence/empty downgrade-reupgrade/retained-authority refusal PASS |

`evidence/m2c/local_validation.json` contains exact source SHAs, individual browser results, all architecture/runtime assertions and frozen migration hashes. `closure_pytest.xml` includes every mandatory backend case. The local full backend tested/checkout SHA is `ed1cdb315a1f459ea6b23be68641aed6a1e2a49a`; production backend/migration bytes remain identical after the final presentation correction. Frontend source is `70b5c69d9f820918fb5561bcad403219714a8da9`; final presentation Browser tested `af0a91cbd6d63d9712cd8f7bb5da4251483d3a20`.

The original failing closure is preserved in task artifacts. Fixes release test-owned real SQLAlchemy pools, reuse governed v2 test policies, retain cross-project binary hash rejection with genuine distinct DOCX archives, and provide deterministic stable-code display fallback. No required assertion,timeout guard,legal decision,authorization or source-of-truth boundary was weakened. Frontend cases were rerun separately from Chromium load after the intermediate5000ms unit timeouts.

Final acceptance requires six successful required workflows at the exact Draft PR#24 head; the runtime workflow reruns the full backend suite at that head. Immutable final CI/checkout evidence and the M2-D entry decision are published on the separate `evidence/m2c-closure-validation` branch under `evidence/m2c/final_validation.json` and `docs/m2c/M2D_entry_decision.md`. These records must identify the tested PR head; an evidence commit does not advance that tested source. No overall PASS/entry authorization is inferred from this local-only record.
