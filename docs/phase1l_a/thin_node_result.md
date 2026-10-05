# Thin nodes

Each stage validates a small StateEnvelope against current server-side authority, creates a typed StageExecutionRequest, calls its injected WorkflowStagePort, receives a typed StageExecutionResult, and returns only references/routing/count deltas. The owning service persists results before returning references. Nodes emit canonical events through existing RuntimeOperationsPort.

No SQL, ORM, provider SDK, parsing, country/product rule, model selection, risk or legal path calculation occurs in graph nodes. SqlWorkflowAuthorization and RuntimeRepository stay in infrastructure. ClassificationWorkflowStage invokes existing ClassificationService and maps its authoritative outcome into orchestration codes; no-data remains NOT_APPLICABLE with no fabricated result.

Missing service bindings explicitly stop. A stage's durable idempotency key is stable across transient attempts and changes only when a distinct resolved review is supplied. Concrete services must enforce that key or their equivalent existing snapshot/subject/version uniqueness.
