# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `c07bbb59-d7a1-4405-ba92-833214163d28` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `c07bbb59-d7a1-4405-ba92-833214163d28` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `c07bbb59-d7a1-4405-ba92-833214163d28` | `{"review_id": "f47b7208-97cc-4232-b955-135f5e48c795"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `c07bbb59-d7a1-4405-ba92-833214163d28` | `{"review_id": "f47b7208-97cc-4232-b955-135f5e48c795"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `c07bbb59-d7a1-4405-ba92-833214163d28` | `{"phase": "COMPLETED"}` |

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
