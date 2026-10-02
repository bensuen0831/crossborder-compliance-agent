# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `fb2a7fdc-123d-4f00-926d-4abcd3336c6a` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `fb2a7fdc-123d-4f00-926d-4abcd3336c6a` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `fb2a7fdc-123d-4f00-926d-4abcd3336c6a` | `{"review_id": "667ab2f8-70fe-401f-8a27-a06b9b3e0b82"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `fb2a7fdc-123d-4f00-926d-4abcd3336c6a` | `{"review_id": "667ab2f8-70fe-401f-8a27-a06b9b3e0b82"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `fb2a7fdc-123d-4f00-926d-4abcd3336c6a` | `{"phase": "COMPLETED"}` |

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
