# Durable human review

The workflow review node reuses existing ReviewTask storage, uniqueness and official interrupt()/Command(resume). RuntimeOperationsPort/SqlRuntimeOperations/RuntimeRepository add optional review_type/reason metadata; existing smoke defaults remain byte-for-byte behavior compatible. Canonical review type is WORKFLOW_STAGE_REVIEW.

Pre-interrupt task creation and canonical events use stable keys. Replay creates no second ReviewTask/event. Fresh server authorization checks tenant, workflow, actor, workflow:review permission and matching review; decisions use the unchanged ReviewDecisionDTO including required provenance. Resolved contradictory decisions are rejected by authorization.

Real subprocess tests start and exit at a durable PostgreSQL interrupt, start a new process, resume approval or rejection, and repeat resume. They verify task count remains one and snapshot/identity refs remain pinned. Simultaneous delivery concurrency still belongs to the owning queue/application idempotency integration; this skeleton does not claim a new distributed worker lease.
