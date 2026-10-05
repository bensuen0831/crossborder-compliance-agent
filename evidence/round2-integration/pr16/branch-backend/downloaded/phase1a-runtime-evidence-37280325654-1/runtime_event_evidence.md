# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `5e15ca42-6b9f-41bf-acee-5edda301f0eb` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `5e15ca42-6b9f-41bf-acee-5edda301f0eb` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `5e15ca42-6b9f-41bf-acee-5edda301f0eb` | `{"review_id": "69a19132-92cb-4bcb-8335-053e3ccf904d"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `5e15ca42-6b9f-41bf-acee-5edda301f0eb` | `{"review_id": "69a19132-92cb-4bcb-8335-053e3ccf904d"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `5e15ca42-6b9f-41bf-acee-5edda301f0eb` | `{"phase": "COMPLETED"}` |

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
