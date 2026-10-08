# M2-D main integration closure — BLOCKED

**M2-D MAIN INTEGRATION = BLOCKED**

**POST-M2-D ENTRY = BLOCKED**

**Stage 2 = NOT STARTED**

## Identity and merge

Baseline `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` / v3.6-m2c-pass. Source PR#25, tested `d3f3db430e72fb54e2be4f2c946fa62c0276a08c`. Remote main/head/base freeze and seven source successes/nine exact checkout logs passed. Metadata-only Draft→Ready and normal merge completed to `efda0955342de8d1ea36aa0f754d63c9b421fec8`, parents `0dc005e583465a4604a5d40a369cb5fc2f0ccbef`, `d3f3db430e72fb54e2be4f2c946fa62c0276a08c`. Source ancestor and identical tree proved. Main has no post-merge source changes. No other milestone PR merged.

## Exact-main measurements and blocker

Local fresh PostgreSQL gate: backend763 PASS,0 failed/errors/skips/deselections;36 M2-D cases and40 M2-C cases included. Architecture242/242 PASS; runtime25/25 PASS; frontend121 PASS with typecheck/lint/build/i18n PASS (561 keys/locale;0 missing/hard-coded strings). Canonical review/append-only history, same-snapshot owner reexecution, request-changes, process restart, idempotency/CAS/authorization, successor lineage/date and historical Snapshot/result/document/parse-pin immutability all passed locally.

Single Alembic0015_m2d_review_governance after0014; historical0001–0014 unchanged. Fresh, exact frozen0014 upgrade, full schema equivalence, empty downgrade/re-upgrade and retained-authority transactional refusal PASS. Nine B–J schema checks PASS.

Completed exact-main browser runs verify C/B/A/M1 each3 and M0 36 with0 retries. **M2-D browser completion is not verified.** Local/PR PASS cannot substitute seven successful exact-main CI runs.

- EXACT_MAIN_CI_TIMEOUT: M2D Governed Human Review, run37781319845, cancelled; The job has exceeded the maximum execution time of 35m0s; Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, actions/setup-node@v4, actions/setup-python@v5, actions/upload-artifact@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/; The operation was canceled.; "The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026. For more information, see https://github.com/actions/runner-images/issues/14748"

The M2-D Chromium setup step took14:06 (13:09:21→13:23:27 UTC); browser matrix started13:23:27. Source PR's same setup took00:32. This observed CI setup delay is recorded separately from production correctness; no production defect is asserted from timeout alone. No CI retry, skip, budget change or PASS tag was used to bypass the failed gate.

| Workflow | Run | Status | Conclusion |
| --- | --- | --- | --- |
| phase1a-runtime-smoke | [37781308907](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781308907) | completed | success |
| M2D Governed Human Review | [37781319845](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781319845) | completed | cancelled |
| M2C Formal Result Workspace | [37781328439](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781328439) | completed | success |
| M2B Production Document Integration | [37781338233](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781338233) | completed | success |
| M2A Production Intake | [37781347189](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781347189) | completed | success |
| M1 Intake Analysis Alpha | [37781357192](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781357192) | completed | success |
| M0 Knowledge & Evidence Preview | [37781368669](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781368669) | completed | success |

Every captured completed job checkout equals `efda0955342de8d1ea36aa0f754d63c9b421fec8`. In-progress job completion/results are not asserted; JSON records snapshot statuses. No PR artifact is reused as main evidence. Separate static-contract selection counts are disclosed here and are not full-backend counts: contract-tests	log	2026-10-08T13:06:14.5934735Z 445 passed, 7 skipped, 311 deselected, 2 warnings in 133.61s (0:02:13). Full local JUnit and raw CI logs/annotations preserve measured limitations and test warnings; lossless gzip logs have SHA256 manifest.

## Retained scope and stop

MULTI_SUBJECT_WORKFLOW_NOT_CONFIGURED; HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED; unsupported correction targets; legacy authority read-only; partial-rerun optimizer not implemented remain explicit nonblocking scope boundaries.

No Stage2/next milestone branch, production code fix on main, provider/auth redesign, generic result editor, historical retrofit, multi-subject or specification change. The requested v3.6-m2d-pass tag was **not created**. `efda0955342de8d1ea36aa0f754d63c9b421fec8` is the legitimate merged source, **not an approved M2-D main release baseline**. Next-stage entry remains blocked; further release work requires a new explicit start instruction respecting failed-gate policy. Do not reset/rewrite the completed normal merge.

Evidence-only `integration/m2d-main-closure-evidence` descends from `efda0955342de8d1ea36aa0f754d63c9b421fec8` and is not merged into main. Report: docs/M2D_main_integration_closure.md. JSON: evidence/m2d/main_integration_validation.json. Main remains `efda0955342de8d1ea36aa0f754d63c9b421fec8`; the evidence commit is not a product baseline. Existing untracked Phase1H closure file preserved. Stop after this blocked closure record.
