# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `3827eb31-c9b7-45d6-b7a8-1d590985d833` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `3827eb31-c9b7-45d6-b7a8-1d590985d833` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `3827eb31-c9b7-45d6-b7a8-1d590985d833` | `{"review_id": "bce485e6-e2ce-4177-95fd-96e5b63a1fac"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `3827eb31-c9b7-45d6-b7a8-1d590985d833` | `{"review_id": "bce485e6-e2ce-4177-95fd-96e5b63a1fac"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `3827eb31-c9b7-45d6-b7a8-1d590985d833` | `{"phase": "COMPLETED"}` |

## Counts

~~~json
{
  "NODE_COMPLETED": 1,
  "REVIEW_REQUIRED": 1,
  "WORKFLOW_COMPLETED": 1,
  "WORKFLOW_RESUMED": 1,
  "WORKFLOW_STARTED": 1
}
~~~

## Raw LangGraph Boundary

- persisted raw-key hits: `[]`
- public DTO raw fields: `none` = `True`
- API layer imports raw LangGraph/checkpointer internals: `False`
