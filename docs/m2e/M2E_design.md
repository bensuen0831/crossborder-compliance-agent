# M2-E production integration channel

Base main `0f5a40c5ca3a8771624fb38e9380856d79e67342`, tag `v3.7-phase1kb-pass`. Resume starts at `df2e2e0b8552ab2172f02ce2d79f1ef911660efb`; R1 source `6655b6cbe7711b68979ee7862aa70416f432d850` remains the owning baseline.

External transport → live Integration identity/scopes/project binding → RepositoryContext → canonical Intake, Documents, Snapshot, WorkflowRuntimePort and Stage1ResultService. No new compliance engine, graph, legal owner, checkpoint authority or model registry. Workflow delivery is a durable technical job; canonical runtime owns execution/recovery. SSE/WS/webhook project canonical WorkflowEventDTO rows.

R1 jurisdiction identity and exact historical pins remain frozen. A single host-owned session factory prevents request-created pools. Official PostgresSaver setup uses an autocommit nonblocking advisory lock with a configurable deadline; a blocked lock transaction must not deadlock concurrent index initialization. Only the setup method changed in the runtime adapter.

0017 integration infrastructure and0018 classification identity are unchanged. No0019. Stage2, paid LLM acceptance, production auth/host redesign and full business E2E matrix remain excluded.
