# Phase1L-B durable review/recovery

Reuse L-A ensure_review_task → durable ReviewTask/event → interrupt → PostgreSQL checkpoint → externally authorized decision → idempotent resolution → owning-stage re-execution. Requirement confirmation is workflow review only; approval never clears a formal conflict/tie/unknown input or changes pinned legal results. Persisted formal review outcomes remain blocking until resolved through the owning contract/new snapshot when required.

Both DATA_AWARE and SCENARIO_LEVEL pass actual cross-process requirement-confirmation interrupt/resume through final path. Duplicate start/resume preserves checkpoint/result/review counts. Current tenant/project/snapshot/request refs, source access and actor permissions are revalidated; checkpoint data cannot grant access.

Non-HITL recovery uses the same adapter: an existing checkpoint with pending tasks and no interrupts resumes via invoke(None), instead of silently returning RUNNING. A process exit after obligation persistence but before its node checkpoint recovers through final with exactly one authority per J stage. Human interrupts are never consumed by start().

A transaction advisory delivery lock serializes concurrent callers of the existing runtime. Bounded lock contention raises WorkflowDeliveryRetryableFailure, separate from StageTransientFailure/node retries. Locks release on error/process exit; no lease/checkpoint table is introduced.
