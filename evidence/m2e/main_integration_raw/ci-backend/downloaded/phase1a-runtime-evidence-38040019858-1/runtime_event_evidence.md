# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `429703c5-c2ac-48c3-9a01-fe1fce057720` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `429703c5-c2ac-48c3-9a01-fe1fce057720` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `429703c5-c2ac-48c3-9a01-fe1fce057720` | `{"review_id": "f1ffded2-bfdd-4d05-be1a-e005368e9f9b"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `429703c5-c2ac-48c3-9a01-fe1fce057720` | `{"review_id": "f1ffded2-bfdd-4d05-be1a-e005368e9f9b"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `429703c5-c2ac-48c3-9a01-fe1fce057720` | `{"phase": "COMPLETED"}` |

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
