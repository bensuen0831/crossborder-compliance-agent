# Authorized review API

All routes use existing `/api/v1`, RepositoryContext, typed Pydantic contracts and generated AJV-validated frontend contracts. Server derives actor, tenant and canonical run/thread identity.

| Route | Contract |
| --- | --- |
| GET /reviews | authorized SQL filtering before pagination: canonical status, project, type, stage, date; CREATED_ASC/DESC; offset/limit |
| GET /reviews/{id} | ReviewView, compact refs, canonical choices/provenance, immutable history, server allowed_actions and lineage |
| POST /reviews/{id}/decisions | APPROVE/REJECT/REQUEST_CHANGES, expected_record_version, actor-bound idempotency_key, optional audit comment |
| POST /reviews/{id}/corrections | discriminated SELECT_BUSINESS_FACT / SELECT_PRODUCT_SCOPE / CLARIFY_INTAKE, exact target, CAS/idempotency |
| POST /reviews/{id}/resume | no body or strict empty object; reload original immutable approval, same canonical delivery |
| POST /reviews/{id}/successor/start | no body or strict empty object; authorize recorded successor lineage and idempotently deliver its canonical run |

Unknown/client authority fields fail runtime validation (422). Unauthorized/missing resources share REVIEW_NOT_FOUND (404). CAS, invalid action, resolved replay and idempotency-payload conflicts are typed409; transient delivery lock contention is WORKFLOW_DELIVERY_BUSY503. Raw checkpoint blobs, SQL internals, secrets and thread controls are not exposed. Existing START/READ/result APIs remain canonical.
