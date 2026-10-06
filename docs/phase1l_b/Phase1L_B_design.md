# Phase1L-B workflow composition

Baseline `f1353372a1d8894535dc71765e3cd62597619fd5`, v3.6-phase1j-pass; migration0010_phase1j; Rules1–155. Start Gate PASS: exact remote main/tag, J main CI37337618576 SUCCESS, absent L-B branch, clean dedicated worktree and existing canonical runtime. Source `3efe583225765370a02e50310ff2d4cf9f7f9139`.

Reuse CanonicalGraphFactory → LangGraphWorkflowRuntimeAdapter → official PostgresSaver. FormalWorkflowStages is an application composition over existing E/F/G/H/I/J services/read ports; formal_workflow_runtime assembles dependencies. WorkflowDeliveryService delegates the existing runtime through a tenant-scoped PostgreSQL delivery guard. It creates no graph/checkpointer/result authority.

The trusted host supplies FormalWorkflowPlan reconstructed from its original request/context references and exact owning-service pins on restart. E context run, subject, classification scheme/item refs, applicability bindings and G query are fixed; host-controlled query/source languages are independent of UI locale. H/I/J policy initialization remains explicit prerequisite work owned by those services. The plan is never a client-authoritative legal input or copied into checkpoint state. Plan-aware authorization checks fresh existing workflow identity before any runtime side effect.

L-A state contracts gain optional bounded UUID reference sets for multiple classifications/applicability results, while retaining primary result_ref compatibility and old checkpoint defaults. Existing graph/state versions remain compatible: no existing fields or meanings change. State/events contain refs and routing metadata only. No evidence/result bodies, services, secrets or legal calculations enter graph state.

No frontend/API/domain/migration/rule changes. Existing adapter gains non-interrupted checkpoint recovery; finite Git-object approval reassigns only that existing runtime file to L-B. Earlier manifests and J approvals remain intact.
