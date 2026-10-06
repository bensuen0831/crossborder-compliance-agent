# M2-A snapshot integration

Baseline `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`; preserved WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b`. Implementation source is pinned in `evidence/m2a/approved_owner_overlay.json`. Full closure/exact-head CI are required before an overall PASS.

Only the ConfirmProjectIntake use case can prepare an intake workflow snapshot. Canonical AnalysisSnapshot.project_version_id pins the exact confirmed payload version, analysis-as-of date, confirming actor/time and intake version. Registry pins preserve selected metadata, structured fact bindings, H rules/configuration, I/J configuration and G policies/source scope.

Existing ContextResolutionService performs structured normalization and merges genuine document-derived candidates before formal context pinning. The existing Project Intake/Context application boundary owns this preparation; nodes contain no duplicated decisions. Explicit product/domain/scenario/location/party/document references are tenant/project validated. Exact canonical E/F/G/H/I/J services prepare FormalWorkflowPlan; DATA_AWARE is not fabricated when a new project has no formal inventory. New intake uses the existing SCENARIO_LEVEL contract.

The existing snapshot provenance carries reconstructible reference-only FormalWorkflowPlan. Stable snapshot/run UUIDs derive from confirmed ProjectVersion. Fresh-process canonical START/READ reconstruct host from persisted refs; duplicate confirmation and START preserve snapshot/fact/run identities. No second graph/checkpointer/run store. Authorization and pinned metadata permissions are revalidated on use. Snapshot and LangGraph checkpoint retain distinct responsibilities.

Missing formal facts/configured required types produce INSUFFICIENT_INPUT/WARNING before applicability; conflict/review enters existing durable HITL. No I/J results are fabricated after insufficient input. Valid manual-only governed facts and available evidence reach the existing Final Path chain on actual PostgreSQL.
