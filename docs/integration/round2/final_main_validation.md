# ROUND 2 FORMAL MAIN INTEGRATION CLOSURE

**ROUND 2 FORMAL MAIN INTEGRATION CLOSURE = PASS**
**PHASE 1J REPOSITORY ENTRY = ALLOWED**

Verified 2026-10-05T16:14:43.562951+08:00. Merge order: PR18 → PR17 → PR16, merge commits only.

| # | Field | Verified result |
| ---: | --- | --- |
| 1 | Initial main SHA | 700951ebb9ebdf33e399158fd3fb53bb4a6c87e7 |
| 2 | PR18 source SHA | 14cba25353d9ab7dda84e9620ff3197d9e2a3d1d |
| 3 | PR18 final integration head | 14cba25353d9ab7dda84e9620ff3197d9e2a3d1d (unchanged) |
| 4 | PR18 merge commit | d83d8db17dd2b16b54038009d8547e290e8949ae |
| 5 | Phase1I post-merge main CI | 37277326614 SUCCESS; workflow_dispatch; exact main |
| 6 | v3.6-phase1i-pass target | d83d8db17dd2b16b54038009d8547e290e8949ae; annotated object 537fcc8f99158484d2c6fc94af22d1eac81cee28 |
| 7 | PR17 original source SHA | 6c2aacd6475af0c0533717daa54b8e48946647e1 |
| 8 | PR17 main-sync merge | 062c5fb64d0196bed7d45cfdb6d64495dd5aafcf |
| 9 | PR17 final tested head | ce54b44d5d5c48fc26d21fab679f25524ceb37c4 |
| 10 | PR17 main merge | 9f3a7da1fc92b821827a6393c7fe05dd98f65eb3 |
| 11 | Stage1-alpha post-merge main CI | Backend 37279353012 / frontend-UAT 37279356177 SUCCESS; exact main |
| 12 | PR16 original source SHA | 39be101e565fa4966e834180523f6ba47a96e5fc |
| 13 | PR16 main-sync merge | 6fc908f845fac81cd54a520708c76638e423a4fa |
| 14 | PR16 final tested head | 80e531573d0fdd687430178019601d482246823d |
| 15 | PR16 main merge | 594be84cfc471af4c12f28600b22cffb66f830f7 |
| 16 | Final main SHA | 594be84cfc471af4c12f28600b22cffb66f830f7 |
| 17 | Alembic head | 0009_phase1i (single head) |
| 18 | Architecture Rules | 1–151; exact Phase1I source; 1–139 retained |
| 19 | Executable architecture | 135/135 PASS |
| 20 | Runtime | 25/25 PASS; 45 Phase1L-A workflow/locale cases PASS |
| 21 | Backend full pytest | 487 PASS; 0 failed/errors/skipped/deselected |
| 22 | Frontend | 63 unit PASS; clean npm ci, typecheck, lint, i18n gate and production build PASS |
| 23 | Browser UAT | 36 PASS; 0 retry/flaky/failure/skip; three independent executions per scenario |
| 24 | Locales | zh-CN / zh-HK / en-US PASS; 262 keys each; 0 missing keys / hard-coded governed strings |
| 25 | LLM security | 20/20 PASS; original Gateway/policy source preserved; restricted egress/fallback/redaction boundaries tested |
| 26 | Tenant/evidence/security isolation | PASS in full PostgreSQL/API suite and real-backend browser denial/cache-purge cases |
| 27 | Migration verification | Fresh0001–0009, archived verified0008→0009, schema equivalence, empty downgrade roundtrip and authoritative-data downgrade refusal PASS;0001–0008 byte-identical |
| 28 | Conflicts and resolution | Four documentation conflicts: both source copies archived; four user-authorized integration corrections: integrity baseline, generated contracts, Phase1I approved manifest, six-path Phase1L-A owner overlay. No workflow/Gateway/domain/migration implementation edited. |
| 29 | Remaining production gaps | Auth/session, CSRF, contextual/fine-grained RBAC, Knowledge history, binary linkage, ingestion deployment, generic recovery and Rule authoring/Admin gaps remain OPEN where owner reports apply. Backend I18N_METADATA_BACKEND_GAP=RESOLVED_BY_PHASE1I; product rollout remains distinct. |
| 30 | Final tag | v3.6-round2-integration-pass; annotated object 8b92aaa5e0ccaf088e4c5389e33083a1fca5a83e; target 594be84cfc471af4c12f28600b22cffb66f830f7 |
| 31 | Phase1J Repository Entry | ALLOWED from final verified main/tag only; not implemented in this task |
| 32 | Overall | ROUND 2 FORMAL MAIN INTEGRATION CLOSURE = PASS |

Final exact-main CI: Backend [37281030481](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37281030481), frontend/UAT [37281034373](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37281034373). Source PR/synthetic-merge CI is not substituted for main evidence. Raw run/jobs/artifact metadata, downloaded reports and complete logs are under evidence/round2-integration.

## Evidence limitations

Remote canonical service versions are PostgreSQL16/Redis7. Additional local final-main validation uses PostgreSQL17.11/Redis8.0.2; it does not substitute for canonical remote evidence. GitHub artifact archive digests are reported API metadata; raw ZIP digests were not independently recomputed. Individual delivered files receive SHA256 inventory. External paid/model providers, production identity/CSRF and production deployment were not validated; security tests use deterministic adapters and UAT uses explicitly synthetic loopback personas. The static CI job selects non-runtime tests; the required full runtime suite includes all cases with zero skipped/deselected. Historical failed setup/integration attempts remain labeled and are not final PASS evidence.

Existing future Domain DTO reference declarations predate this task and remain unchanged. No Phase1J, Phase1L-B, M1, final Risk/Path/Recommendation implementation or production authentication was added. Phase1L-A future stages remain explicitly unavailable.

## Delivery and start recommendation

Closure documents are generated only after final exact-main gates and remote tag verification. They are delivered in a separate evidence-only branch so publishing this record does not change or move the tested main/tag. Phase1J must start at 594be84cfc471af4c12f28600b22cffb66f830f7 / v3.6-round2-integration-pass. This task stops at closure.
