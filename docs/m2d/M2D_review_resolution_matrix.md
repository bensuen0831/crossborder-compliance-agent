# Backend review resolution matrix

| Pinned owner/type/reason | Actions | Resolution |
|---|---|---|
| Canonical v2 requirement, explicit requirement_review=true, no conflict/unresolved facts | APPROVE, REJECT, REQUEST_CHANGES | Same snapshot; approval re-executes requirement owner |
| Exact pinned BUSINESS_FACT_CONFLICT | SUBMIT_CORRECTION, REJECT, REQUEST_CHANGES | Context-owner selected immutable source value; successor snapshot and full run |
| Exact pinned PRODUCT_CONTEXT_CONFLICT | SUBMIT_CORRECTION, REJECT, REQUEST_CHANGES | Product owner selects governed source scope; successor snapshot and full run |
| Missing facts / input-changing clarification | ADD_INFORMATION, REQUEST_CHANGES, REJECT | Typed intake owner command; new input version and successor |
| Evidence insufficient / unknown / legal result review | REQUEST_CHANGES, REJECT | No APPROVE; new evidence through existing document/intake owner is required |
| Legacy v1 / unsupported type/target / multi-subject | read-only | Existing explicit capability gap |

Permissions: tenant + exact project grant + workflow:review, role enforced by a backend capability scope. Server derives actor; no client roles/thread IDs. APPROVE never changes fact/evidence sufficiency. REQUEST_CHANGES remains PENDING and never invokes resume. REJECT remains a governed review boundary, never an infrastructure failure. Every action uses CAS plus actor-bound request idempotency and immutable canonical ReviewDecision history.

No country/product/legal decision branches. Frontend renders backend allowed_actions. Input correction never consumes a same-snapshot resume token. Reexecution starts at the complete canonical pipeline; optimization is out of scope.
