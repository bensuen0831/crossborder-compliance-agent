# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `66a17b2d-a9f2-4b62-8ec9-330668273f5e` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `66a17b2d-a9f2-4b62-8ec9-330668273f5e` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `66a17b2d-a9f2-4b62-8ec9-330668273f5e` | `{"review_id": "22b716a5-aedc-4491-b6df-7985bd2d45fa"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `66a17b2d-a9f2-4b62-8ec9-330668273f5e` | `{"review_id": "22b716a5-aedc-4491-b6df-7985bd2d45fa"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `66a17b2d-a9f2-4b62-8ec9-330668273f5e` | `{"phase": "COMPLETED"}` |

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
