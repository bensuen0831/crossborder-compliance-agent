# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `4c63a801-b0f9-4f5a-965b-748c067c57bd` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `4c63a801-b0f9-4f5a-965b-748c067c57bd` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `4c63a801-b0f9-4f5a-965b-748c067c57bd` | `{"review_id": "593a9cb6-3e57-4c2f-bb9a-4b99e085c4ea"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `4c63a801-b0f9-4f5a-965b-748c067c57bd` | `{"review_id": "593a9cb6-3e57-4c2f-bb9a-4b99e085c4ea"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `4c63a801-b0f9-4f5a-965b-748c067c57bd` | `{"phase": "COMPLETED"}` |

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
