# Snapshot versus checkpoint

AnalysisSnapshot remains immutable reproducibility authority; checkpoint is execution position only. SqlWorkflowAuthorization loads the existing WorkflowRun, snapshot, pinned ProjectVersion and Project rows under the current RepositoryContext, checks tenant/current operation permissions and active project/snapshot, and returns the authoritative execution identity.

Saved identity must exactly match that fresh identity. Client thread IDs, saved tenant/project IDs and checkpoint refs never authorize a request. Reads, stream_events, start and resume are gated. Cross-tenant checkpoint/event access fails, as do changed snapshot identity and forged initial progress.

Resume changes review/execution state, not AnalysisSnapshot or its configuration pins. The trusted application composition must retain its original opaque execution-context reference/mode across process restart and construct a fresh authenticated RepositoryContext for each operation. No ConversationThread or legal result version is conflated with the runtime thread.
