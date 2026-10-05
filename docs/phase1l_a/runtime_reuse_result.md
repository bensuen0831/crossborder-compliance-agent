# Phase 1A runtime reuse

Default adapter construction still compiles the original node_a → node_b interrupt → node_c smoke graph. Its state, nodes, event keys and recursion configuration remain unchanged. Optional canonical factory injection selects an additional graph definition inside that same adapter, not a second runtime.

Both graph definitions use the same official PostgreSQL PostgresSaver/setup and existing workflow/review/event tables. No checkpointer Alembic revision or second schema exists. Existing migration head remains 0008_phase1h; ARCHITECTURE_RULES.md and rules 1–139 remain unchanged.

The unchanged smoke/run_gate.sh performs start in one process, resume in another and duplicate retry in a third, plus all schema/runtime/backend regressions. The final implementation is checked with this gate on an isolated fresh PostgreSQL database and on exact-head remote CI.
