# Phase 1L-A canonical workflow skeleton

Baseline: 700951ebb9ebdf33e399158fd3fb53bb4a6c87e7, tag v3.6-phase1h-pass, migration 0008_phase1h, rules 1–139. The exact-main baseline CI 37254295087 succeeded. Dedicated branch phase1l-a-workflow-skeleton and worktree /workspace/crossborder-phase1l-a were created from this commit; origin/main and tag were verified, the remote branch was absent and the worktree clean before coding. Architecture start gate: 118/118. M0 and the original work checkout were preserved.

REUSE: WorkflowRuntimePort, LangGraphWorkflowRuntimeAdapter, RuntimeContext, official PostgreSQL PostgresSaver/setup, WorkflowRun, AnalysisSnapshot, ReviewTask and WorkflowEvent storage. EXTEND: optional graph factory, canonical reference state and runtime operation metadata/read projection. CUSTOM_BUILD: orchestration-only stage/authorization interfaces and thin graph composition; no dependency additions. ClassificationWorkflowStage delegates to the real Phase 1H ClassificationService.

One deterministic sixteen-step semantic graph: Requirement, Formal Context, Data/Flow, Jurisdiction, Knowledge Scope, Retrieval, Sufficiency, Classification, Applicability, Obligation, Candidate Path, Risk, Recommendation, Final Path, Documents/Templates, Report. It is independent of the five-stage presenter projection. No country/product/scenario graph exists.

No legal implementation is supplied for future stages. Every unbound stage explicitly returns CAPABILITY_NOT_CONFIGURED and stops with WARNING. The default composition does not run a complete compliance workflow. Synthetic stage ports appear only in tests; a compile/order test does not demonstrate production legal analysis. Current classification delegation is available as an explicit application binding; other owning services must supply authorized persisted refs before integration.

No migration, permanent rule, rule-engine change, LLM Gateway, API, frontend or Phase 1L-B implementation. PROPOSED_FOR_PHASE1L_FINAL: formal service compositions should enforce connector cancellation/deadline behavior and durable execution idempotency; review integration should coordinate worker delivery concurrency. These are integration proposals, not allocated permanent rules.

## Locale / presentation boundary

The product supports zh-CN, zh-HK and en-US. Phase 1L-A performs no UI localization.
Workflow semantics are locale-neutral: authoritative state, events and routing use stable
codes. Workflow lifecycle status codes are WAITING, RUNNING, COMPLETED, WARNING,
REVIEW_REQUIRED and FAILED. Internal NEXT/REVIEW routing instructions and
StageOutcomeCode values remain machine codes, distinct from lifecycle statuses.
Localized labels such as “等待中”, “待人工覆核” or “Human Review Required” are never
authoritative workflow semantics.

Canonical WorkflowEvent exposes an existing stable WorkflowEventType, structured payload,
status and reason codes. The existing event adapter rejects localized/unknown lifecycle
statuses, inconsistent payload status and unstructured reason codes. Canonical skeleton
payloads remain limited to status, reason_codes and request_id. Human-readable translations
belong to Presentation/API consumers outside the Workflow Domain; no translation catalogue,
localized legal result or new presentation source of truth is introduced.

RuntimeContext may carry optional preferred_locale (zh-CN / zh-HK / en-US, default None)
solely for downstream presentation. Existing ChannelContext.locale remains the request-side
presentation preference; an application may map it to this runtime hint. Preferred locale
is not part of ExecutionIdentity, StageExecutionRequest, StageExecutionResult or
ComplianceWorkflowState. No orchestration, classification, routing, event generation or
authorization code reads it. It must not affect Rule evaluation, Regulation Applicability,
Risk, Compliance Path or AnalysisSnapshot semantics, and must not be copied into legal/domain
results. Future stage contracts cannot receive it through the canonical stage request.

Changing UI locale alone is a presentation operation: do not invoke start/resume or create
a legal decision for a language change. Locale is never written to a checkpoint or snapshot
pin. Read-only checkpoint/event projection with another locale must leave execution position
and snapshot unchanged, and must not rerun completed stages. A real review decision remains
the only reason for review resume; its checkpoint change is independent of locale.

Executable architecture tests enforce exclusion of locale from semantic contracts and from
canonical graph, classification, runtime adapter and authorization dependencies. All twelve
StageOutcomeCode routes and a complete sixteen-step synthetic port composition produce
identical state/result references, stage requests and event codes under all three locales.
These synthetic ports prove orchestration invariance, not completed future legal services.
Four real PostgreSQL cross-process review scenarios change locales before/after interrupt
and resume; checkpoint IDs/next nodes, snapshot columns and duplicate-delivery behavior are
checked explicitly. Foreign-tenant reads remain denied under every supported locale.
