# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `fea9a6d0-07c5-487a-a7a0-5c730c5eb2f8` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `fea9a6d0-07c5-487a-a7a0-5c730c5eb2f8` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `fea9a6d0-07c5-487a-a7a0-5c730c5eb2f8` | `{"review_id": "5e3f0cdc-dce8-47a9-8ee2-b24d332f3000"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `fea9a6d0-07c5-487a-a7a0-5c730c5eb2f8` | `{"review_id": "5e3f0cdc-dce8-47a9-8ee2-b24d332f3000"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `fea9a6d0-07c5-487a-a7a0-5c730c5eb2f8` | `{"phase": "COMPLETED"}` |

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
