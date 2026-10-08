# Phase 1A.1 Runtime Event Evidence

## Canonical Event Sequence

| # | Event | Node | Tenant | Payload |
|---:|---|---|---|---|
| 1 | `WORKFLOW_STARTED` | `` | `ad5e9194-5fd5-41e3-812b-aa7ff45a3b95` | `{}` |
| 2 | `NODE_COMPLETED` | `node_a` | `ad5e9194-5fd5-41e3-812b-aa7ff45a3b95` | `{"phase": "A_DONE"}` |
| 3 | `REVIEW_REQUIRED` | `node_b` | `ad5e9194-5fd5-41e3-812b-aa7ff45a3b95` | `{"review_id": "2b180858-798c-4b93-a356-08a8b2cd0b0d"}` |
| 4 | `WORKFLOW_RESUMED` | `node_b` | `ad5e9194-5fd5-41e3-812b-aa7ff45a3b95` | `{"review_id": "2b180858-798c-4b93-a356-08a8b2cd0b0d"}` |
| 5 | `WORKFLOW_COMPLETED` | `node_c` | `ad5e9194-5fd5-41e3-812b-aa7ff45a3b95` | `{"phase": "COMPLETED"}` |

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
