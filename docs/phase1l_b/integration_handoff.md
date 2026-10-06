# Phase1L-B handoff

Branch/worktree: phase1l-b-full-workflow-wiring; /workspace/phase1l-b-full-workflow-wiring. Exact baseline `f1353372a1d8894535dc71765e3cd62597619fd5` / v3.6-phase1j-pass; executable source `34c75641050f7a8c5cc133fb8373e17dc71ec818`. Keep Draft PR targeting main; do not merge or integrate M1 here.

Host entry: infrastructure.workflow_formal_composition.formal_workflow_runtime returns the application delivery service plus the existing canonical factory. Supply current RepositoryContext, existing session factory/PostgreSQL URI, immutable server-prepared FormalWorkflowPlan and explicitly initialized H/I/J pins. Reconstruct the same trusted plan/request_context_ref on restart. Use factory.initial_state(run_id), then delivery.start/resume/read; do not bypass delivery serialization with direct adapter calls. Worker delivery contention and node transient failures remain distinct.

Interfaces: reuse WorkflowRuntimePort, owning E/F/G/H/I/J services, SqlWorkflowAuthorization, RuntimeOperationsPort, ReviewTask/events, RuntimeContext and PostgresSaver. Optional bounded related_result_refs/result_ref_sets extend reference transport only. Step15/16 return boundaries/projections; authoritative final/status/action details must be read through authorized J services.

Ownership: workflow/application composition, one existing runtime adapter recovery change, directly required PostgreSQL delivery guard, tests, finite ownership-check extensions and these six documents. No frontend/OpenAPI regeneration, legal-domain/API changes, migration, new registry/runtime or permanent rule. Task-specific checkpoint is artifacts/phase1l-b/phase_progress_checkpoint.md; root/M1 checkpoints preserved.

Focused L-B43 + retained L-A45 PASS; architecture151/151, K-A20/20, integrity PASS. Closure evidence is the final exact-head CI/PR artifact, with full suite and runtime25/25. Existing synchronous service cancellation boundary remains explicit. No L-C/M1/M2 work is authorized by this handoff.
