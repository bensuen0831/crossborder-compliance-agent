# INTEGRATION HANDOFF

1. Task / Track: Phase 1L-A — canonical compliance workflow skeleton only.
2. Branch / Worktree: phase1l-a-workflow-skeleton; /workspace/crossborder-phase1l-a.
3. Base SHA: 700951ebb9ebdf33e399158fd3fb53bb4a6c87e7; v3.6-phase1h-pass; baseline CI 37254295087 SUCCESS.
4. Tested implementation SHA: e86a4feb7371e042cc852b200e4f6ae2f80003c7; exact-head CI 37258208829 SUCCESS. Pre-locale final closure SHA 2064459e828758bda2587ce3c51352c8c450d8df passed exact-head CI 37258670920. The subsequent locale supplement is a production code change; its own exact-head CI is recorded in PR #16 checks and the final delivery report. Local evidence is explicitly working-tree validation.
5. PR: #16 https://github.com/bensuen0831/crossborder-compliance-agent/pull/16, DRAFT targeting main; never merge automatically.
6. New files: eight Python files listed in files_created_modified.md, thirteen delivery documents and measured evidence.
7. Modified files: application/ports.py, workflows/langgraph_adapter.py, workflows/runtime_context.py, workflows/events.py, persistence/runtime_operations.py, persistence/repositories.py; shared runtime integration only.
8. Migration: NONE; 0008_phase1h remains head; Phase 1I owns potential 0009.
9. API / DTO: no HTTP API or authoritative domain DTO change; new typed application stage/identity/outcome contracts and reference state, with optional non-checkpointed RuntimeContext.preferred_locale only.
10. Config / Registry: execution policy/factory bindings only; no business registry/source of truth.
11. Dependencies: NONE.
12. Architecture Rules: unchanged 1–139; 118 executable checks.
13. Tests added: 45, including 25 locale invariance/architecture/event tests and four strengthened real PostgreSQL subprocess review scenarios.
14. Local results: full fresh-DB unchanged gate exit 0; 329 passed, zero skipped/deselected/failures/errors; architecture 118/118, runtime 25/25, Phase 1H schema 20/20; new Python files and modified event/runtime-context files Ruff PASS. Measured working-tree hashes in evidence/phase1l_a/local-validation.json.
15. Historical remote CI before locale supplement: run 37258208829, https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37258208829, SUCCESS on implementation SHA e86a4feb7371e042cc852b200e4f6ae2f80003c7. Measured check annotation: 304 passed, zero skipped/deselected/failures/errors; architecture 118/118, runtime 25/25, migration head 0008_phase1h; runner checkout equals tested head. Metadata and empirical summary are in evidence/phase1l_a/remote-ci.json; raw archive digests were not independently recomputed.
16. Interfaces consumed: WorkflowRuntimePort, RuntimeContext, existing RuntimeOperationsPort, PostgresSaver, RepositoryContext, WorkflowRun/ReviewTask/AnalysisSnapshot/WorkflowEvent, Phase 1H ClassificationService.
17. Interfaces provided: CanonicalGraphFactory, validated reference state, StageExecutionRequest/Result, authorization/stage ports, policies, ClassificationWorkflowStage, tenant-scoped canonical event projection.
18. Risks: future services remain unavailable; no full workflow/legal result. Application bindings must enforce reference authorization, stable execution context, service deadlines and durable idempotency. Synchronous callable preemption and distributed queue leases are not implemented. Shared runtime extensions must be coordinated with parallel tracks.
19. Merge order: depends only on Phase 1H; no Phase 1I/1J domain type or migration dependency. Coordinate the six shared runtime files with stage1-alpha; do not merge automatically.
20. Post-merge tests: unchanged full fresh-DB smoke/run_gate.sh, architecture, no migration drift, subprocess review/resume, exact-head CI and owning-service bindings when available.
21. UAT: canonical requirement review → durable interrupt → fresh process approval → rerun owning stage → next unconfigured service WARNING; rejection FAILED; duplicate delivery inert. This is orchestration acceptance, not legal workflow acceptance.
22. Status: PHASE 1L-A WORKFLOW SKELETON = PASS on verified implementation. Keep PR #16 DRAFT; never merge automatically. The locale supplement requires its own exact-head checks, distinct from the historical implementation proof. Locale-neutral semantics are specified in Phase1L_A_design.md; all three locales are presentation-only, outside routing, legal results, snapshots and authorization. No full Phase 1L, Phase 1L-B or Phase 1M entry decision; stop at Phase 1L-A.
