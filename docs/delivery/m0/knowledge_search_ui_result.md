# Knowledge search UI result

Knowledge search uses the existing POST `/api/v1/projects/{project_id}/knowledge/retrieve`.
The request contains snapshot ID, policy ID, query, unique idempotency key, PROJECT subject and
languages. It cannot submit an allowed scope, tenant or product filter. Query length and empty
input are validated by the library Form and by the backend.

Projects/snapshot/policy bundles come from the trusted presentation session. Metadata labels
come from `/api/v1/metadata/{products,scenarios,jurisdictions}`. Context is resolved by the existing
GET `/api/v1/projects/{project_id}/knowledge-scope?analysis_snapshot_id=...`. Product, Scenario,
Jurisdiction and Product Domain selectors are read-only because frozen analysis pins must not
silently change. No frontend hard-coded business options exist.

Fresh-start real UAT uses actual PostgreSQL FTS and published synthetic canonical knowledge.
The default UAT policy is lexical-only; it does not claim production embeddings or model output.
Authorized queries returned two allowed items, not the equally searchable permission-restricted
version. No-match search returned zero evidence with typed actionable guidance. Queries, source
bodies and credentials are not written to application debug logs.
