# Stage1 Main R2 — M2-E timeout recovery

STAGE1-MAIN-R2 = PASS
M2E CI RECOVERY = PASS
RECOVERY PATH = A / SAME-SHA CLEAN RETRY
MAIN CODE CHANGE = NONE

Original/final exact main: `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`. Original normal PR #28 merge ancestry
remains unchanged. No CI-only PR was needed; Path B was not executed.
One clean main workflow_dispatch execution ran M2-E at its unchanged 75-minute
limit: [run 38380317555](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38380317555).
Both mandatory-backend and canonical-frontend-browser are SUCCESS, with actual
executed checkout logs proving `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`. Full backend summary:
1012 passed, 20 warnings in 2799.99s (0:46:39).
All post-test M2-A/M2-B boundaries, additive architecture and closure aggregation
completed successfully; pytest alone was not accepted as workflow success.

## Original timeout retained

Original [run 38357981677](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357981677),
job 115165231861, completed full pytest 1012 PASS in 4367.74 seconds and reached
post-test architecture/M2-A checks, but exceeded 75 minutes. Job duration was
75m18s. M2-A completion was not observed, M2-B was not reached, and M2-E
architecture/closure aggregation was skipped after cancellation.
GitHub's execution-time annotation confirms budget exhaustion; assertion failure
was not observed. The PostgreSQL lock-timeout service message occurred during
the suite, which later completed all 1012 tests. Its bounded delivery contention
negative test passed; the message is not evidence of deadlock. No runner resource
starvation is established by available telemetry. Original evidence branch
`evidence/stage1-main-closure-060cbb5-blocked` remains at `e2d7c5f82930e6161b0bc2596d5e5d7b6ff2f3b9`; its content
and historical BLOCKED decision were not overwritten.

## Exact-main selection and unchanged coverage

The original ten successful main workflows were revalidated against current
GitHub run/job status and their hash-verified actual checkout logs. They were not
rerun. Those ten plus the new complete M2-E execution produce 11/11 SUCCESS and
18/18 actual checkout MATCH. All source/test/fixture content remains unchanged;
647 exact committed Git-blob digests match the validated main and working tree.
Full test-ID manifests retain all 1012 backend IDs and all 65 original browser
identities; the 12 business/locale journeys remain additive (77 total, retries 0).
The supplementary non-runtime contract subset's 535 PASS / 7 skipped / 470
deselected stays separately disclosed and is not full PostgreSQL evidence.
No tests, assertions, fixtures, policies, ownership checks, migrations, product
code, browser retries or time limits changed. Transient read-only GitHub API
responses interrupted monitoring briefly; monitoring resumed on the same run
without another CI execution or credential replacement.

Annotated release tag `v3.7-stage1-e2e-pass` targets `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`. Tag object:
`3144c1d2400cd228305348a6a315acedd5857cdb`. Closure evidence is archived separately on
`evidence/stage1-main-closure-060cbb5`; main was not advanced for documentation.
Acceptance is L1 SYNTHETIC_GOVERNED technical/business E2E only.
Paid Internet LLM, Real Regulatory Knowledge acceptance and Production Business
UAT remain NOT EXECUTED. Stage 2 = NOT STARTED.
