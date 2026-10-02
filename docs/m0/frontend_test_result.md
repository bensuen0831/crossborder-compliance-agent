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
Exact remote run/head/result will be recorded after the final implementation is pushed and tested.
No old CI run or local hash is substituted for a new GitHub artifact digest.

Frontend fixtures are actual sanitized synthetic HTTP responses captured from the UAT backend.
Tests mutate status/contract fields only inside test code. They are not imported by the app bundle.
A malformed session, invalid DTO status or legal_decision=true is rejected at the API boundary.
