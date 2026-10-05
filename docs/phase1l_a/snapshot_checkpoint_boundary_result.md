# Snapshot versus checkpoint

AnalysisSnapshot remains immutable reproducibility authority; checkpoint is execution position only. SqlWorkflowAuthorization loads the existing WorkflowRun, snapshot, pinned ProjectVersion and Project rows under the current RepositoryContext, checks tenant/current operation permissions and active project/snapshot, and returns the authoritative execution identity.

Saved identity must exactly match that fresh identity. Client thread IDs, saved tenant/project IDs and checkpoint refs never authorize a request. Reads, stream_events, start and resume are gated. Cross-tenant checkpoint/event access fails, as do changed snapshot identity and forged initial progress.

Resume changes review/execution state, not AnalysisSnapshot or its configuration pins. The trusted application composition must retain its original opaque execution-context reference/mode across process restart and construct a fresh authenticated RepositoryContext for each operation. No ConversationThread or legal result version is conflated with the runtime thread.

Presentation locale is not part of that stable execution identity. Four real PostgreSQL
restart scenarios now switch zh-CN / zh-HK / en-US at durable interrupt, read/duplicate
start, real decision resume and duplicate resume. Read-only locale changes preserve the
exact checkpoint ID, values, next-node position and review count. A real decision changes
the checkpoint; subsequent locale switches/duplicate resume leave it unchanged. Every
AnalysisSnapshot column, including legal/config/evidence pins, is compared before and after.
Foreign-tenant checkpoint/event reads remain denied for all three locales. No locale-driven
legal decision, snapshot rewrite or stage rerun is introduced.
