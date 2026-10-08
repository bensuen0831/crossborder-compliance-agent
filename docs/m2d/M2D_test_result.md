# M2-D verification contract

Focused implementation checkpoints:16 contract tests + canonical PostgreSQL decisions/CAS/auth/restart; fact/product/intake successor ownership; production API validation; C0 legal review refusal; delivery recovery; migration dual paths. D1–D4 checkpoint measured70 tests plus1 owning cross-border review. New recovery tests then measured7 PostgreSQL correction/API PASS. Review UI focused13 PASS.

D6 requires the complete backend suite (baseline727 plus all M2-D tests), zero failures/errors/skips/deselections, existing221 architecture plus21 additive checks, runtime25, frontend baseline108 plus13, type/lint/build/i18n, real3-locale M2-D scenarios and all C/B/A/M1/M0 browser regressions with0 retries. CI must test the exact PR head and report its checkout SHA.

Passing focused runs do not constitute closure. Final machine-readable measured evidence and raw logs are stored on a separate immutable evidence branch linked to the tested source head. No next entry decision is generated before complete closure.

First exact-head mandatory CI measured760 PASS/2 FAIL: the direct-worker audit insertion omitted its mandatory Snapshot FK. The owning runtime repository now derives it from the canonical WorkflowRun, validating tenant/thread. A new direct-worker audit test and the unchanged two L-B restart cases pass3/3 focused. This closure-blocking executable fix requires a new exact-head full CI gate; new M2-D tests total36, mandatory backend minimum763. No old result is counted as final closure.
