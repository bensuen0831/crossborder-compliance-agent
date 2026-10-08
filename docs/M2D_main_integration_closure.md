# M2-D main integration closure

**M2-D MAIN INTEGRATION = PASS**

**POST-M2-D ENTRY = ALLOWED**

**Stage 2 = NOT STARTED**

## Source and exact-main identity

M2-C baseline `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` / `v3.6-m2c-pass`. Source PR #25, branch `milestone-m2d-human-review-resume`, tested head `d3f3db430e72fb54e2be4f2c946fa62c0276a08c`. Seven source CI runs and nine actual job checkout logs were reverified before metadata-only Draft→Ready and normal merge.

Merge and final tested main: `efda0955342de8d1ea36aa0f754d63c9b421fec8`. Parents: `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` and `d3f3db430e72fb54e2be4f2c946fa62c0276a08c`. Tested PR head is an ancestor; merged source tree is byte-identical to PR head. No squash, rebase, force push, cherry-pick or post-merge production-source change. No parallel milestone branch was merged.

Annotated tag `v3.6-m2d-pass`, object `dff211af565475765b921b9fe515c65630f93d47`, target `efda0955342de8d1ea36aa0f754d63c9b421fec8`. Created only after all measured main gates passed; remote tag type/object/commit dereference verified.

## Timeout-only recovery

Initial normal-merge main and final main are both `efda0955342de8d1ea36aa0f754d63c9b421fec8`. Initial run [37781319845](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781319845) was cancelled by the35-minute GitHub job budget. Chromium setup took14:06; no functional assertion failure was recorded. Original BLOCKED report/JSON, raw cancelled logs and annotations remain under `evidence/m2d/main_closure/` and this recovery archive.

Recovery A fresh `workflow_dispatch` [37787075090](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37787075090), attempt1, completed SUCCESS at the same actual main SHA, with all15 browser cases and0 Playwright retries. Existing six successes were independently reverified at this same SHA and combined only as expressly authorized for Recovery A. CI execution rerun is recorded separately from browser retry counts.

Recovery B was NOT REQUIRED and NOT EXECUTED. No CI fix branch/PR, workflow/test/browser/package/migration/source changes, coverage reduction, performance optimization or assertion retry.

## Exact-main measurements

Backend **763 PASS**,0 failed/errors/skipped/deselected, independently local and remote full PostgreSQL gates. All36 M2-D and40 M2-C cases executed. Test count equals the PR baseline; no hidden xfail/deselection. Nine Phase1B–J schema checks PASS. Architecture **242/242 PASS** =151+13+27+15+15+21; no permanent rule deletion. Runtime **25/25 PASS** including durable PostgreSQL checkpointer, process restart, canonical review and events, resume/idempotency and checkpoint identity.

Frontend **121 PASS**, typecheck/lint/build/i18n PASS both local and remote. zh-CN/zh-HK/en-US have0 missing owned keys and0 hard-coded UI strings. Real PostgreSQL/backend/Chromium: M2-D3/3,C3/3,B3/3,A3/3,M1 3/3,M0 36/36; **0 retries**. M2-D workflow's full D/C/B/A/M1 matrix15/15 executes on the exact main. Each locale executes approval, held request-changes, genuine document conflict/typed correction, successor result linkage and unchanged original result read.

## Migration

Single Alembic head `0015_m2d_review_governance`, down-revision `0014_m2c_formal_result_authority`. All frozen0001–0014 Git blobs unchanged. Empty fresh→0015, actual frozen M2-C commit's exact0014→0015, complete catalog equivalence, permitted empty downgrade/re-upgrade and governed-authority transactional refusal all PASS. Refusal preserves catalog and Alembic head; authoritative review data cannot be silently destructively downgraded. Dedicated local migration gate and main M2-D CI rerun independently record this policy.

## Human review and temporal contracts

Canonical ReviewTaskEntity/ReviewDecisionEntity remain authoritative; decision history is append-only. APPROVE is a governed confirmation handled by the owning stage, not a legal-fact/result editor. Same-snapshot approval reuses run/snapshot/thread and durable checkpoint, reexecutes requirement owner and records one canonical history. REQUEST_CHANGES leaves review/workflow pending without resume. Unsupported legal/missing-evidence approval remains refused.

Typed input corrections use existing ProjectVersion/context owners, create successor Snapshot and WorkflowRun, rerun from backend-owned requirement boundary and downstream stages. Source Snapshot/context facts/formal projection and exact document/parse pins remain immutable; successor preserves analysis_as_of_date by default. Persisted lineage links task/correction/source/successor/run/results. Original and successor result links remain accessible.

The full canonical chain also starts in a subprocess, exits REVIEW_REQUIRED, reloads its persisted ReviewTask and resumes in a fresh authorized subprocess. M2-D process-restart test reloads the PostgreSQL checkpoint in a fresh subprocess, completes owner reexecution and proves duplicate resume keeps checkpoint/history unchanged. Network/delivery retry, CAS concurrent reviewer winner, stale/version/payload conflicts, current tenant/project/role permissions and server-owned reviewer identity PASS. HTTP actor/thread/start_at/policy injection rejected. One runtime, one checkpointer, one review authority remain. M2-C formal results and M2-B temporal/version/provenance contracts pass full regression. RequiredDocument remains Stage1; no automatic Stage2 generation.

Detailed measured testcase mapping, all21 review architecture checks, runtime assertions, migration flags, JUnit and browser reports are archived with the JSON record.

## Seven new main CI runs

All selected runs are `workflow_dispatch` on actual main `efda0955342de8d1ea36aa0f754d63c9b421fec8`; none borrow PR artifacts or ephemeral merge refs. Every one of the nine runner job checkout SHAs and tested identities equals the final main SHA.

| Workflow | Run | Conclusion | Exact main / runner checkout |
| --- | --- | --- | --- |
| phase1a-runtime-smoke | [37781308907](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781308907) | SUCCESS | `efda0955342de8d1ea36aa0f754d63c9b421fec8` |
| M2D Governed Human Review | [37787075090](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37787075090) | SUCCESS | `efda0955342de8d1ea36aa0f754d63c9b421fec8` |
| M2C Formal Result Workspace | [37781328439](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781328439) | SUCCESS | `efda0955342de8d1ea36aa0f754d63c9b421fec8` |
| M2B Production Document Integration | [37781338233](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781338233) | SUCCESS | `efda0955342de8d1ea36aa0f754d63c9b421fec8` |
| M2A Production Intake | [37781347189](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781347189) | SUCCESS | `efda0955342de8d1ea36aa0f754d63c9b421fec8` |
| M1 Intake Analysis Alpha | [37781357192](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781357192) | SUCCESS | `efda0955342de8d1ea36aa0f754d63c9b421fec8` |
| M0 Knowledge & Evidence Preview | [37781368669](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37781368669) | SUCCESS | `efda0955342de8d1ea36aa0f754d63c9b421fec8` |

## Scope, limitations and entry

Retained explicit boundaries: MULTI_SUBJECT_WORKFLOW_NOT_CONFIGURED; HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED; unsupported correction targets; legacy authority read-only; partial-rerun optimizer not implemented. No generic legal editor, historical retrofit, multi-subject implementation, Stage2, Phase1K-B provider/governance work, production auth redesign, next milestone branch or Master Specification change.

Separate static-contract job intentionally selects a subset; it is not the full backend measurement. Its selection is disclosed:

```text
contract-tests	log	2026-10-08T13:06:14.5934735Z 445 passed, 7 skipped, 311 deselected, 2 warnings in 133.61s (0:02:13)
```

Local uses prepared PostgreSQL17; remote services use fresh pgvector PostgreSQL16. Browser fixtures use synthetic authorized personas and an explicit no-scan UAT file policy; no claim of production identity federation or scanning certification. Existing compiler/test warnings remain visible in raw logs and do not change measured assertions. Raw logs are losslessly gzip archived with SHA256/round-trip manifest.

Blockers: **NONE**. POST-M2-D ENTRY **ALLOWED** requires a separate next-stage scope prompt/start gate; Stage2 **NOT STARTED**. Next development must start from `efda0955342de8d1ea36aa0f754d63c9b421fec8` + `v3.6-m2d-pass`.

Evidence-only branch `integration/m2d-main-closure-evidence` descends from tested main and is not merged into main. The evidence commit is not a product baseline. Main must remain `efda0955342de8d1ea36aa0f754d63c9b421fec8` after publication. Report: `docs/M2D_main_integration_closure.md`. JSON: `evidence/m2d/main_integration_validation.json`. Recovery archive: `evidence/m2d/main_recovery/recovery_a/`; historical blocked archive retained: `evidence/m2d/main_closure/`. Existing untracked Phase1H closure file preserved. Integration closure stops here.
