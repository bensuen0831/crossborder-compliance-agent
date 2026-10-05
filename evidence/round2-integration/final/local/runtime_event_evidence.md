# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `a20aa5cc-4aa9-4a48-9dd0-57f6a2cf909c` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `a20aa5cc-4aa9-4a48-9dd0-57f6a2cf909c` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `a20aa5cc-4aa9-4a48-9dd0-57f6a2cf909c` | `{"review_id": "821943f3-c048-486b-bec3-e17da751fd3f"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `a20aa5cc-4aa9-4a48-9dd0-57f6a2cf909c` | `{"review_id": "821943f3-c048-486b-bec3-e17da751fd3f"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `a20aa5cc-4aa9-4a48-9dd0-57f6a2cf909c` | `{"phase": "COMPLETED"}` |

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
