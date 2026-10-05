# Test result

Twenty new tests cover deterministic compile/order, reference validation, unavailable boundaries, successful/no-data/insufficient/conflict/review/low-confidence/failure routes, transient retry, timeout late-result rejection, max-step/repeated-route guards, fresh authorization/revocation, canonical events and actual no-data ClassificationService behavior.

Reproduction: activate the Python 3.12 development environment, set APP_ENV=LOCAL_SERVER,
DATABASE_URL, LANGGRAPH_DATABASE_URI and REDIS_URL for an isolated PostgreSQL/pgvector + Redis
instance, and apply the existing migrations with `alembic upgrade head`. Run
`pytest -q tests/test_phase1l_a_skeleton.py tests/test_phase1l_a_contracts.py`.
For the complete gate, use a **fresh separate empty database**, distinct SMOKE_STATE_FILE and
EVIDENCE_DIR, then `bash smoke/run_gate.sh`; its post-Alembic proof requires no pre-existing
checkpoint tables. Preserve other tasks' databases and services. The subprocess helper is test-only.

Four PostgreSQL subprocess scenarios cover review-required/conflict/low-confidence approval and rejection, real durable interrupt, process restart, duplicate start/resume, forged decision actor/progress, tenant isolation and snapshot invariance. In-memory checkpointer is used only for isolated unit tests, never production runtime.

The full unchanged gate is executed on a fresh DB with all Phase 1A–1H tests included and zero skips/deselections. Final measured counts and exact remote head/run are recorded after execution; early/local working-tree validation is not substituted for final-head CI. Ruff covers all seven new Python files; original baseline files are not broadly reformatted.

Final local working-tree gate: **304 passed / 0 failures / 0 errors / 0 skipped / 0 deselected**, gate exit 0; architecture **118/118**, runtime **25/25**, Phase 1H schema **20/20**. Node/runtime/checkpointer versions are recorded in evidence/phase1l_a/local-validation.json with measured SHA256 hashes. Local services use PG17/Redis8; remote CI independently uses PG16/Redis7. New-file Ruff and git diff --check pass. Exact-head remote acceptance is pending.

Remote implementation run [37258208829](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37258208829) succeeded on exact SHA `e86a4feb7371e042cc852b200e4f6ae2f80003c7`. Its measured annotation confirms 304 passed, zero skipped/deselected/failures/errors, architecture 118/118, runtime 25/25 and 0008_phase1h. The runner checkout equals that head. Original full gate includes Phase 1A–1H and all twenty new tests. Machine metadata, measured counters and server artifact digests are in evidence/phase1l_a/remote-ci.json. Archive contents were not downloaded; no local artifact digest verification is claimed. Documentation-only successors are independently checked at their own PR head.
