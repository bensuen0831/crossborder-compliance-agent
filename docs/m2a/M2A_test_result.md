# M2-A measured validation

Baseline `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`; preserved WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b`. Implementation source is pinned in `evidence/m2a/approved_owner_overlay.json`. Full closure/exact-head CI are required before an overall PASS.

Focused PostgreSQL/core30 PASS; preserved L-B combined51 PASS; restart/concurrency5 PASS; finite-owner/tamper14 PASS; legacy M1 API closure-fix3 PASS; selected-domain/pin1 PASS. All focused results are superseded by the required full closure gate.

Frontend92 PASS; typecheck/lint/build/i18n PASS; M2A Browser3/3, M1 Browser3/3, M0 Browser36/36, zero retries. Final full backend653/653 PASS, 0 failed/errors/skipped/deselected;33 new M2A tests PASS. Phase1B–1J schema regressions PASS. Existing Architecture151/151 + M2A13/13, Runtime25/25, K-A boundary and Stage1 integrity PASS. Exact-head remote CI remains the final certification gate. Machine results under artifacts/m2a and evidence/m2a.

The initial full gate stopped on legacy missing-host409/404 compatibility (1 failure); preserved under artifacts/m2a/closure-attempt1. The owning API compatibility fix preserves authorization and409. Full rerun is required because executable code changed. The earliest preflight used a populated DB and stopped before pytest; fresh isolated closure DB retains the checkpoint/schema separation proof. No gate was lowered.

Local backend gate tested SHA: `8d37e5b69274fb34d52bdb29d5dc49a23e7e314a`. Machine-readable measured record: `evidence/m2a/local_closure.json`; raw XML/runtime/browser artifacts are retained locally and reproduced/uploaded by exact-head CI. Browser/frontend local measurements precede the legacy API-only closure fix; final CI independently runs the full browser/frontend gates on PR HEAD.

Verified code-head CI: all four workflows SUCCESS at `21c7bc4a9ef10b00d0aad9515bc6a46c89158def`; remote runtime artifact11402294571 confirms backend653, Architecture151+13, Runtime25 and migration dual path. Three independent browser artifacts confirm M2A3/M1 3/M0 36, zero retries. See `evidence/m2a/verified_code_ci.json`. Final delivery descendant requires exact-head CI independently.
