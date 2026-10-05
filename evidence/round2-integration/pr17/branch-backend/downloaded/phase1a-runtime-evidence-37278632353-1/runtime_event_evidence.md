# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `71c35e29-6a51-4a58-92c5-0ccff0fca297` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `71c35e29-6a51-4a58-92c5-0ccff0fca297` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `71c35e29-6a51-4a58-92c5-0ccff0fca297` | `{"review_id": "71af08a8-c1bf-474a-88a5-b0067d7eaefe"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `71c35e29-6a51-4a58-92c5-0ccff0fca297` | `{"review_id": "71af08a8-c1bf-474a-88a5-b0067d7eaefe"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `71c35e29-6a51-4a58-92c5-0ccff0fca297` | `{"phase": "COMPLETED"}` |

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
