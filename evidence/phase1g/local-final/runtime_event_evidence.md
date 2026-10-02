# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `ef536715-a783-4eee-acf9-6e34aa4baaf6` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `ef536715-a783-4eee-acf9-6e34aa4baaf6` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `ef536715-a783-4eee-acf9-6e34aa4baaf6` | `{"review_id": "1a57e733-fd64-4149-943f-342615e859a2"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `ef536715-a783-4eee-acf9-6e34aa4baaf6` | `{"review_id": "1a57e733-fd64-4149-943f-342615e859a2"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `ef536715-a783-4eee-acf9-6e34aa4baaf6` | `{"phase": "COMPLETED"}` |

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
