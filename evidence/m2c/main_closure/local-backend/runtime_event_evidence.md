# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `21f26d74-8c73-40d4-874c-6cce2f6595d5` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `21f26d74-8c73-40d4-874c-6cce2f6595d5` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `21f26d74-8c73-40d4-874c-6cce2f6595d5` | `{"review_id": "5525c057-9f29-4f2d-b412-b58188baebab"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `21f26d74-8c73-40d4-874c-6cce2f6595d5` | `{"review_id": "5525c057-9f29-4f2d-b412-b58188baebab"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `21f26d74-8c73-40d4-874c-6cce2f6595d5` | `{"phase": "COMPLETED"}` |

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
