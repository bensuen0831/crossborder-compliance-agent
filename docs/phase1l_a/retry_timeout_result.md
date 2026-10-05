# Retry and timeout boundaries

WorkflowExecutionPolicy composes WorkflowRetryPolicy and WorkflowTimeoutPolicy with recursion/max-step/repeated-visit bounds. Only explicit transient failures are retried. Every attempt reauthorizes; attempts share a stable service idempotency key. Exhaustion emits a structured failure, and business/missing capability/conflict routes are not infrastructure retries.

StageExecutionRequest carries timeout_seconds. Concrete connectors/application services must honor their deadline/cancellation behavior. The synchronous skeleton detects a late return and rejects it; it cannot preempt an arbitrary hung synchronous callable. It does not claim hard cancellation or change LLM Gateway/provider timeout policy. This limit is explicit and must be addressed when production connectors are composed.

Queue/process delivery retry is separate: an existing checkpoint prevents duplicate start and terminal repeated resume is inert. Review replay uses durable existing uniqueness. Stage side effects must be idempotent through owning services; no second retry/idempotency store is introduced.
