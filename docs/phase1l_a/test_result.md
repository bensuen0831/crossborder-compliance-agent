# Test result

Forty-five new tests (including twenty-five locale boundary tests) cover deterministic compile/order, reference validation, unavailable boundaries, successful/no-data/insufficient/conflict/review/low-confidence/failure routes, transient retry, timeout late-result rejection, max-step/repeated-route guards, fresh authorization/revocation, canonical events and actual no-data ClassificationService behavior.

Reproduction: activate the Python 3.12 development environment, set APP_ENV=LOCAL_SERVER,
DATABASE_URL, LANGGRAPH_DATABASE_URI and REDIS_URL for an isolated PostgreSQL/pgvector + Redis
instance, and apply the existing migrations with `alembic upgrade head`. Run
`pytest -q tests/test_phase1l_a_skeleton.py tests/test_phase1l_a_contracts.py tests/test_phase1l_a_locale.py`.
For the complete gate, use a **fresh separate empty database**, distinct SMOKE_STATE_FILE and
EVIDENCE_DIR, then `bash smoke/run_gate.sh`; its post-Alembic proof requires no pre-existing
checkpoint tables. Preserve other tasks' databases and services. The subprocess helper is test-only.

Four PostgreSQL subprocess scenarios cover review-required/conflict/low-confidence approval and rejection, real durable interrupt, process restart, duplicate start/resume, forged decision actor/progress, tenant isolation and snapshot invariance. In-memory checkpointer is used only for isolated unit tests, never production runtime.

The full unchanged gate is executed on a fresh DB with all Phase 1A–1H tests included and zero skips/deselections. Final measured counts and exact remote head/run are recorded after execution; early/local working-tree validation is not substituted for final-head CI. Ruff covers the eight new Python files plus modified event/runtime-context files; original baseline files are not broadly reformatted.

Final local working-tree gate: **329 passed / 0 failures / 0 errors / 0 skipped / 0 deselected**, gate exit 0; architecture **118/118**, runtime **25/25**, Phase 1H schema **20/20**. Node/runtime/checkpointer versions are recorded in evidence/phase1l_a/local-validation.json with measured SHA256 hashes. Local services use PG17/Redis8; remote CI independently uses PG16/Redis7. Ruff on new Python files and modified event/runtime-context files, plus git diff --check, pass. Final-head remote evidence is provided by PR #16 checks and the delivery report.

Historical pre-locale implementation run [37258208829](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37258208829) succeeded on exact SHA `e86a4feb7371e042cc852b200e4f6ae2f80003c7`. Its measured annotation confirms 304 passed, zero skipped/deselected/failures/errors, architecture 118/118, runtime 25/25 and 0008_phase1h. The runner checkout equals that head. Original full gate includes Phase 1A–1H and the initial twenty orchestration tests. Machine metadata, measured counters and server artifact digests are in evidence/phase1l_a/remote-ci.json. Archive contents were not downloaded; no local artifact digest verification is claimed. The locale supplement changes production contracts/events and is independently checked at its own exact PR head; this historical run does not validate those changes.

Locale supplement validation: **25 new tests PASS**, all twelve outcome routes under each
of zh-CN / zh-HK / en-US, full sixteen-step synthetic completion/ref invariance, identical
stage requests/event codes, executable architecture exclusion, localized-semantic rejection
and stable six-status acceptance. The four existing PostgreSQL subprocess tests additionally
switch all three locales at interrupt and after real resume, compare exact checkpoint
IDs/values/next positions, all snapshot columns, duplicate delivery and foreign-tenant denial.
The fresh local gate used phase1l_a_locale_20261005 and artifacts/phase1l-a-locale with
SMOKE_STATE_FILE=/tmp/phase1l_a_locale_smoke.json; exit code 0. Local evidence remains
working-tree validation against the recorded parent; it is not claimed as final-head CI.
