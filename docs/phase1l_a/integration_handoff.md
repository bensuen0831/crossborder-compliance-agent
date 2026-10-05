# INTEGRATION HANDOFF

1. Task / Track: Phase 1L-A — canonical compliance workflow skeleton only.
2. Branch / Worktree: phase1l-a-workflow-skeleton; /workspace/crossborder-phase1l-a.
3. Base SHA: 700951ebb9ebdf33e399158fd3fb53bb4a6c87e7; v3.6-phase1h-pass; baseline CI 37254295087 SUCCESS.
4. Final tested SHA: recorded in final delivery and exact-head PR checks; local validation is working-tree evidence.
5. PR: DRAFT targeting main; link will be recorded after creation; never merge automatically.
6. New files: seven Python files listed in files_created_modified.md, thirteen delivery documents and measured evidence.
7. Modified files: application/ports.py, workflows/langgraph_adapter.py, persistence/runtime_operations.py, persistence/repositories.py; shared runtime integration only.
8. Migration: NONE; 0008_phase1h remains head; Phase 1I owns potential 0009.
9. API / DTO: no HTTP API or authoritative domain DTO change; new typed application stage/identity/outcome contracts and reference state only.
10. Config / Registry: execution policy/factory bindings only; no business registry/source of truth.
11. Dependencies: NONE.
12. Architecture Rules: unchanged 1–139; 118 executable checks.
13. Tests added: 20, including four real PostgreSQL subprocess review scenarios.
14. Local results: full fresh-DB unchanged gate exit 0; 304 passed, zero skipped/deselected/failures/errors; architecture 118/118, runtime 25/25, Phase 1H schema 20/20; seven new Python files Ruff PASS. Measured working-tree hashes in evidence/phase1l_a/local-validation.json.
15. Remote CI: exact final head required before PASS; recorded in final delivery/PR checks.
16. Interfaces consumed: WorkflowRuntimePort, RuntimeContext, existing RuntimeOperationsPort, PostgresSaver, RepositoryContext, WorkflowRun/ReviewTask/AnalysisSnapshot/WorkflowEvent, Phase 1H ClassificationService.
17. Interfaces provided: CanonicalGraphFactory, validated reference state, StageExecutionRequest/Result, authorization/stage ports, policies, ClassificationWorkflowStage, tenant-scoped canonical event projection.
18. Risks: future services remain unavailable; no full workflow/legal result. Application bindings must enforce reference authorization, stable execution context, service deadlines and durable idempotency. Synchronous callable preemption and distributed queue leases are not implemented. Shared runtime extensions must be coordinated with parallel tracks.
19. Merge order: depends only on Phase 1H; no Phase 1I/1J domain type or migration dependency. Coordinate the four shared runtime files with stage1-alpha; do not merge automatically.
20. Post-merge tests: unchanged full fresh-DB smoke/run_gate.sh, architecture, no migration drift, subprocess review/resume, exact-head CI and owning-service bindings when available.
21. UAT: canonical requirement review → durable interrupt → fresh process approval → rerun owning stage → next unconfigured service WARNING; rejection FAILED; duplicate delivery inert. This is orchestration acceptance, not legal workflow acceptance.
22. Status: pending final exact-head CI closure. No Phase 1L-B or Phase 1M entry decision; stop at Phase 1L-A.
