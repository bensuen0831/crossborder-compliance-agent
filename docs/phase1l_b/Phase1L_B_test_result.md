# Phase1L-B tests

Executable source `34c75641050f7a8c5cc133fb8373e17dc71ec818`. Focused L-B43 PASS:28 contract/routing/real formal-service delegation cases;8 actual PostgreSQL workflow/security/restart/parallel-delivery/lock-timeout/crash cases;7 ownership-authentication cases. Retained L-A45 PASS in the focused recovery gate. Ruff and diff checks PASS.

Measured focused gates: Architecture151/151; Phase1K-A20/20; Stage1 integrity PASS. Rules1–155, migrations0001–0010 and frontend remain unchanged. No0011 exists.

The complete closure gate is the exact-head Draft PR mandatory backend CI, including full pytest with zero failed/errors/skipped/deselected; B–J and L-B coverage; all schema regressions; single0010; runtime25/25; architecture151/151; security/ownership/idempotency; J migration dual paths. Exact tested head/run/conclusion and measured counts are recorded in PR checks/body and the uploaded runtime-evidence artifact. Closure is certified only after those exact-head empirical artifacts pass; focused results do not replace that gate.

Focused logs/checkpoint: artifacts/phase1l-b/. No manual frontend/browser matrix or later-phase test scope added.

Closure-blocking executable fix: the first CI37400069345 passed on e4e5777, but a new actual PostgreSQL counterexample showed Sufficiency accepting a different authorized subject in the same project/snapshot. Added explicit retrieval-subject and context/scope-reference checks plus3 regressions; focused43 PASS. One permitted exact-head full repeat certifies the corrected executable source. No other full rerun is required.
