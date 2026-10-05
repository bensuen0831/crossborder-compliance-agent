# M0 test result

Local working-tree validation, executed using Python 3.12.14, Node 24.19.0, PostgreSQL 17.11,
pgvector 0.8.0, Redis 8.0.2 and installed Chromium. CI independently uses PostgreSQL 16/Redis 7.

| Check | Executed result |
|---|---|
| TypeScript typecheck | PASS |
| ESLint | PASS |
| Production build | PASS; browser verifies demo login absent and missing session fails closed |
| Frontend unit/component/contract tests | 20 passed / 0 skipped / 0 failed |
| Real browser UAT | 3 passed: search/citation/fallback/readiness, A/B isolation, narrow/no-match |
| Independent repeated browser UAT | 9/9 passed, three executions per scenario, retries zero |
| Added backend UAT security tests | 5 passed |
| Full original regression + UAT tests | 205 passed / 0 skipped / 0 deselected / 0 failed / 0 errors |
| Phase 1G schema | 58/58 PASS |
| Architecture | 108/108 PASS |
| Runtime | 25/25 PASS |
| Earlier Phase 1B–1F schema and regressions | PASS |

Commands: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`,
`M0_CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e`, `pytest -q tests/test_m0_preview_security.py`,
and the unchanged `bash smoke/run_gate.sh` against a newly created isolated database.

`evidence/m0/local-validation.json` contains measured hashes of the current local full regression
log, JUnit XML, schema/runtime/architecture results. Local logs reside in ignored
`artifacts/m0-regression/`; they are working-tree results, not claims that the early checkpoint
SHA contains later work. Browser screenshots/JSON reside in frontend/test-results and CI artifacts.
The pushed implementation `83cd43df1245c66539ac13c8269791b8f182ebbe` has independently
completed both remote workflows successfully:

- [M0 frontend quality and real-backend UAT, run 37250600944](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37250600944): both jobs and every step succeeded, including typecheck/lint/unit/build, reproducible contract generation, five backend security tests, fresh backend/frontend start and browser E2E. The standard Playwright GitHub reporter's check annotation confirms **9 passed (36.5s)**.
- [Original regression workflow, run 37250600937](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37250600937): both jobs and every step succeeded. The empirical check annotation independently confirms **205 passed / 0 skipped / 0 deselected / 0 failures / 0 errors**, schema **58/58**, architecture **108/108**, runtime **25/25**, and unchanged Alembic head **0007_phase1g**. It records both the tested PR head and GitHub runner merge SHA, plus the runner-measured full-log hash.

`evidence/m0/remote-ci.json` records REST API run/job/artifact metadata with exact head and
server-reported artifact digests. Measured browser/regression results were retrieved through
supported check annotations. Initial full log/archive downloads were denied by the session proxy at
`results-receiver.actions.githubusercontent.com` and `productionresultssa15.blob.core.windows.net`.
Those exact hosts are saved in the environment configuration draft; Review/Save/Publish is
required for activation. Archive contents have not been inspected and their hashes have not
been independently recomputed here. Later archives were not downloaded. The table above records
executed local results; remote PASS and the explicitly quoted counts are established separately
by GitHub run/job/step conclusions and measured check annotations.
No old CI run or local hash is substituted for a new GitHub artifact digest. Evidence-only
successor commits must also pass their own PR checks before integration.

One earlier browser CI step failed on `c14c1d2` (run 37250154464), while its quality/regression
jobs passed. Raw downloads were blocked, so its original failure cause remains unconfirmed.
Application source did not change. Standard GitHub annotations and failure-only trace/screenshot
capture were added, then three independent executions per scenario passed locally and remotely,
with retries still zero. This is repeated observed acceptance, not a claimed root-cause fix.
The failed run is retained in remote-ci.json; later integration should monitor UAT stability.

Frontend fixtures are actual sanitized synthetic HTTP responses captured from the UAT backend.
Tests mutate status/contract fields only inside test code. They are not imported by the app bundle.
A malformed session, invalid DTO status or legal_decision=true is rejected at the API boundary.
