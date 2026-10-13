# R3 remote CI timeout diagnosis and bounded recovery

Exact source292fc6e9 has8 SUCCESS/2 CANCELLED. Both cancelled jobs have the
GitHub check annotation **"The job has exceeded the maximum execution time of
45m0s"**. Runtime run38269072883 lasted45m22s; KB run38269072760 lasted45m24s.
Executed checkout logs, not workflow metadata alone, print the exact source SHA.
No failed assertion appears in either mandatory-job log.

Runtime completed all991 tests and reached Gate complete at cancellation. KB
continued from87% to94% before cancellation. Same-source complete full jobs:
M2E38269072739 =60m13s, R1 recovery38269072901 =57m15s, both SUCCESS. The M2E
artifact measures991 PASS / zero failed/errors/skipped/deselected. These are
diagnosis references, not new-source closure evidence.

Both jobs invoke `smoke/run_gate.sh`: migrations/schema, durable runtime25,
full pytest and architecture/ownership. Several required workflows intentionally
repeat that full regression in independent jobs. There is no duplicate full
pytest call inside each mandatory job. The supplementary contract job is a
subset check and does not substitute for full backend measurement.

The longest measured tests are independent Web/API business journeys153–156s;
the complete successful run does not show a deadlock. Progress and successful
same-source completion support wall-clock budget exhaustion. No manual or
concurrency cancellation is indicated; the explicit timeout annotation is the
cause. Runner starvation is not asserted without resource telemetry.

Recovery changes only the two backend budgets45→75 minutes, aligning with the
already successful75-minute full-backend workflows and allowing bounded margin
above the measured60m13s. Frontend and contract budgets, assertions, PostgreSQL,
coverage and retries0 remain unchanged. No broad caching/parallelism redesign is
included. Actual new-head successful runs and job checkout proof are required
before R2 REMOTE CI COMPLETION = PASS; status remains PENDING until measured.

Safe diagnostics and log digests: evidence/stage1-full-e2e/r3/ci_diagnostics.json.
Raw logs remain private, outside the repository. Stage2 NOT STARTED.

## Measured recovery result

Commit `180ec61bae0546305a69f25a5988e91980c35327`: 10/10 workflows SUCCESS, 15/15 jobs verified by executed checkout `git log -1 --format=%H`. Run IDs and per-job proof are in `evidence/stage1-full-e2e/r3/ci_references.json`. This completes R2 REMOTE CI COMPLETION only; it is not evidence for a later R3 final head.

## Additive SDK execution environment

The R3 full Python suite now runs a real TypeScript SDK HTTP journey. Four complete backend jobs install Node 24 and only the TypeScript compiler version already locked in frontend/package-lock.json. This avoids rebuilding the whole frontend to provide a compiler. It changes no tests, assertions, browser retries or product dependencies. Dedicated acceptance jobs separately measure business coverage and retained candidate/history/security cases; full regression remains mandatory in the existing workflows.

## R3 exact-head regression diagnosis (a01f19b5)

The four full-backend jobs completed with 1011 PASS and the same one retained
Phase1H failure: unauthorized classification result reads returned 403 instead
of the established resource-concealing 404. This is a functional HTTP contract
regression, not a timeout. The owning project-read adapter now translates only
project authorization refusal to not-found; the canonical stage reader continues
to enforce its own action permissions. No test expectation was changed.

Dedicated business-contracts succeeded. The browser job passed the three review
cases but nine completed-result cases exhausted the 180-second per-test budget
at the final result reread, after workflow/result/UI assertions had progressed.
Local identical-source journeys all passed (12/12, 18.2 minutes, retries zero).
The test previously navigated again to an already open result workspace, reloaded
immediately, and issued an additional full-result read while the workspace's
historical revalidation was running. Recovery observes the actual reload HTTP
response and compares the same complete result JSON, eliminating those duplicate
reads while retaining reload, UI, provenance, locale and console assertions.
The test/job budgets and retries remain unchanged. New exact-head evidence is
required; failed runs are retained and cannot be reported as closure PASS.
