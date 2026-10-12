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
