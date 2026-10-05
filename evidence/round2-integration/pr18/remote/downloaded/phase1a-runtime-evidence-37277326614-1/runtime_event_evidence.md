# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `0966f80a-e1e6-47ba-9797-03c853507b6f` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `0966f80a-e1e6-47ba-9797-03c853507b6f` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `0966f80a-e1e6-47ba-9797-03c853507b6f` | `{"review_id": "bfc431e9-5da9-4d03-9e50-c24e4104c5b5"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `0966f80a-e1e6-47ba-9797-03c853507b6f` | `{"review_id": "bfc431e9-5da9-4d03-9e50-c24e4104c5b5"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `0966f80a-e1e6-47ba-9797-03c853507b6f` | `{"phase": "COMPLETED"}` |

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
