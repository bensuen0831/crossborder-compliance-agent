# Typed routing

StageOutcomeCode is an application orchestration outcome, separate from Domain AnalysisStageResult lifecycle status. SUCCESS, NOT_APPLICABLE and EVIDENCE_SUFFICIENT advance. CONFLICTED, REVIEW_REQUIRED and LOW_CONFIDENCE enter durable review. INSUFFICIENT_INPUT, EVIDENCE_INSUFFICIENT and CAPABILITY_NOT_CONFIGURED stop with WARNING. FAILED and NON_RETRYABLE_FAILURE terminate FAILED.

EVIDENCE_INSUFFICIENT requires a persisted fallback reference; omission is a contract error. The graph retains that reference, never emits a fake obligation/path. RETRYABLE_FAILURE or explicit StageTransientFailure participates in bounded retry; business conflict never does.

Approved review re-executes the owning stage with review_ref; approval cannot skip that stage or manufacture SUCCESS. Rejection terminates FAILED. Max steps, repeated visits and graph recursion bounds prevent indefinite review/routing loops. DATA_AWARE and SCENARIO_LEVEL are orchestration modes; neither fabricates a DataItem or a classification.
