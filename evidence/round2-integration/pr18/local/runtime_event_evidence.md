# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `b7c76048-2c96-45bb-8dc0-91b1666d52b6` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `b7c76048-2c96-45bb-8dc0-91b1666d52b6` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `b7c76048-2c96-45bb-8dc0-91b1666d52b6` | `{"review_id": "9cf80b02-8c46-4986-9e00-c9ebdcafeb36"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `b7c76048-2c96-45bb-8dc0-91b1666d52b6` | `{"review_id": "9cf80b02-8c46-4986-9e00-c9ebdcafeb36"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `b7c76048-2c96-45bb-8dc0-91b1666d52b6` | `{"phase": "COMPLETED"}` |

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
