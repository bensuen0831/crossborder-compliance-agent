# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `b2d5b406-dfa2-45fc-a37c-f548097771ad` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `b2d5b406-dfa2-45fc-a37c-f548097771ad` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `b2d5b406-dfa2-45fc-a37c-f548097771ad` | `{"review_id": "f4a3a318-641a-447c-a8a5-79a2f67bffe7"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `b2d5b406-dfa2-45fc-a37c-f548097771ad` | `{"review_id": "f4a3a318-641a-447c-a8a5-79a2f67bffe7"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `b2d5b406-dfa2-45fc-a37c-f548097771ad` | `{"phase": "COMPLETED"}` |

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
