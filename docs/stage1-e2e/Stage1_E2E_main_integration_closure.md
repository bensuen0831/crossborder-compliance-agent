# Stage1 Full Business E2E — main closure BLOCKED

STAGE1 MAIN INTEGRATION = MERGED_BUT_CLOSURE_BLOCKED
STAGE1 RELEASE CLOSURE = BLOCKED
REASON = EXACT_MAIN_M2E_CI_WALL_CLOCK_TIMEOUT

PR #28 was authorized and normally merged. Previous main: `df3a10923734495d728981f4f319b66afadf8c71`.
Validated PR head: `25b2cb34be24578c74ea7ed4931f9534ff0289f3`. Actual main/merge commit: `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`.
Parents are exactly previous main and validated PR head; their merge tree equals
the PR tree. No evidence commit entered main, and no production source changed.
PR #28 is MERGED; this report does not imply that the merge was undone.

| Gate | Measured exact-main result |
|---|---|
| Backend | 1012 PASS; failed/errors/skipped/deselected = 0 |
| Architecture | 361/361 PASS |
| Runtime | 25/25 PASS |
| Frontend | 142 PASS; typecheck/lint/build/i18n PASS |
| Browser | 77/77 PASS; retained 65 plus 12 new journeys; retries 0 |
| Four outcomes / locale matrix | 4/4 and 12/12 PASS |
| Candidate/DataFlow/DOCX/RAG/LegalSupport | PASS |
| Web/API parity and actual HTTP SDK smoke | PASS |
| Review/resume/successor/security | PASS |
| Original saved V2 history | 15/15 reads, 12/12 recovered, complete digests unchanged |
| Migration | 0020 sole head; fresh/exact0019/equivalence/safe downgrade/refusal/re-upgrade PASS |
| Frozen migrations | 0001–0019 byte-identical |
| Mandatory main CI | 10/11 SUCCESS; M2E CANCELLED |
| Actual runner checkout | 18/18 MATCH exact main |
| Release tag | NOT CREATED; v3.7-stage1-e2e-pass does not exist |

Acceptance measurements are **L1 SYNTHETIC_GOVERNED technical/business E2E**.
Their PASS does not override the failed mandatory workflow or authorize release.
All 1012 backend test IDs and the original 65 browser identities are retained.
The supplementary non-runtime contract subset reports 535 PASS / 7 skipped /
470 deselected and is not used as full PostgreSQL evidence.

## Exact blocker

[M2E run 38357981677](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357981677)
job `mandatory-backend`, job ID `115165231861`, was cancelled at its configured
75-minute wall-clock limit. Duration: **4518 seconds (75m18s)**.
GitHub annotation: “The job has exceeded the maximum execution time of 1h15m0s”.
Cancelled step: `Full mandatory PostgreSQL runtime, registry, real HTTP providers,
security and migration`. It ran from 14:40:43 to 15:55:14 Asia/Shanghai.
Last successful setup step: `Locked compiler for mandatory real TypeScript SDK
business acceptance`. Full pytest then completed **1012 PASS in 4367.74s** at
15:54:04 Asia/Shanghai. The architecture rule check began at 15:54:15 and the
additive M2-A boundaries at 15:54:19; cancellation followed at 15:55:14.
No assertion failure was observed. Actual forward progress is documented through
99%, 100%, the pytest summary and post-pytest boundary checks. A hang, deadlock or
resource starvation is not established by the available logs. The blocker is
execution-budget exhaustion after pytest, not a demonstrated legal/product failure.
The remaining owning-boundary/aggregation workflow did not complete, so M2E
cannot be reported SUCCESS. Original cancelled evidence is retained by run/job
identity, annotation, timestamps and raw-log digest; raw logs remain private.

## Local environment diagnostics retained

The first local additional browser run used the wrong historic database in its
normalizer while its HTTP backend used the new isolated database. It failed three
DIRECT normalizations; nine unexecuted cases were recorded when stopped. An
actual rule-hit identity counterexample established the mismatch. A complete
clean 12-case execution on a fresh matching database passed without changing
source, assertions, timeout or retries=0. These diagnostics remain archived.
An initial M0 12-case probe was rejected by the coverage guard; the existing
--repeat-each=3 invocation then executed the full 36, with all original IDs retained.

## Recovery boundary

No automatic rerun, timeout increase, source fix, test skip, assertion change,
force push, history rewrite, tag or next-phase work was performed after the
mandatory main timeout. A separate timeout recovery should first run one clean
M2E execution on the same frozen main with unchanged gates. If it times out again,
diagnose a bounded CI-only correction through a reviewed PR and normal merge,
then repeat full exact-main closure on that new SHA. Do not tag the incomplete main.

Independent blocked evidence branch: `evidence/stage1-main-closure-060cbb5-blocked`, parent `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`.
Its commit is not the product baseline. Paid Internet LLM, Real Regulatory
Knowledge acceptance and Production Business UAT remain NOT EXECUTED.
Retained boundaries include MULTI_SUBJECT_WORKFLOW_NOT_CONFIGURED,
HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED, unsupported correction targets,
legacy read-only authority and no partial-rerun optimizer. No new migration or
legal capability was added. Stage 2 = NOT STARTED. Next-phase entry remains BLOCKED.

## Main CI references

- [Stage1 Full Business E2E Acceptance / 38358002892](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38358002892) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [Stage1 R1 Candidate Governance Recovery / 38357996775](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357996775) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [Phase1KB Multi-provider LLM Governance / 38357990932](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357990932) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [phase1a-runtime-smoke / 38357986507](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357986507) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2E External Agent API Gateway / 38357981677](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357981677) — cancelled; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2D Governed Human Review / 38357976869](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357976869) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2C Formal Result Workspace / 38357971959](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357971959) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2B Production Document Integration / 38357967430](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357967430) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2A Production Intake / 38357961602](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357961602) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M1 Intake Analysis Alpha / 38357956862](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357956862) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M0 Knowledge & Evidence Preview / 38357952092](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357952092) — success; checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
