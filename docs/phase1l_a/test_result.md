# Test result

Twenty new tests cover deterministic compile/order, reference validation, unavailable boundaries, successful/no-data/insufficient/conflict/review/low-confidence/failure routes, transient retry, timeout late-result rejection, max-step/repeated-route guards, fresh authorization/revocation, canonical events and actual no-data ClassificationService behavior.

Four PostgreSQL subprocess scenarios cover review-required/conflict/low-confidence approval and rejection, real durable interrupt, process restart, duplicate start/resume, forged decision actor/progress, tenant isolation and snapshot invariance. In-memory checkpointer is used only for isolated unit tests, never production runtime.

The full unchanged gate is executed on a fresh DB with all Phase 1A–1H tests included and zero skips/deselections. Final measured counts and exact remote head/run are recorded after execution; early/local working-tree validation is not substituted for final-head CI. Ruff covers all seven new Python files; original baseline files are not broadly reformatted.

Final local working-tree gate: **304 passed / 0 failures / 0 errors / 0 skipped / 0 deselected**, gate exit 0; architecture **118/118**, runtime **25/25**, Phase 1H schema **20/20**. Node/runtime/checkpointer versions are recorded in evidence/phase1l_a/local-validation.json with measured SHA256 hashes. Local services use PG17/Redis8; remote CI independently uses PG16/Redis7. New-file Ruff and git diff --check pass. Exact-head remote acceptance is pending.
