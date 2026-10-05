# Versioned resource admin result

The shared page supports Jurisdiction, Business Scenario, Product, Knowledge Collection, Template, Prompt and Model Admin endpoints. Resource identity/display fields and contract-specific metadata fields generate the create/edit form; descriptors can be supplied by the integrated host. Rule operations are deliberately unavailable.

Implemented operations: active-registry list/search, history lifecycle filtering, draft creation, supported draft editing, version inspection, submit-review, approve/reject, publish, supersede/archive, version history, comparison of returned fields, and backend impact preview. Knowledge adds its existing `INGESTED`/`VALIDATED` stages, expire and the restricted archive transition. Buttons reflect each API family's actual transitions, not a fabricated universal state machine.

The list contains active registry data for resources with a metadata list endpoint. There is no complete draft/search endpoint, so an operator can open a known definition ID. Definition IDs are retained separately from jurisdiction config overlay IDs. Missing model history version numbers are shown as unknown rather than inferred.

Artifact/model projections omit their editable payload. Newly created drafts retain their submitted payload in component memory, while externally loaded payload-less drafts cannot be edited. This prevents blind overwrites. Scenario/Product and jurisdiction history expose payload where supported. Comparison shows payload only when both versions return it; full audit history, clone-version creation and complete draft discovery remain backend gaps.

Validated through lifecycle rendering, create/edit/review/approve/publish, optimistic revisions, conflict-input retention, contextual control visibility and real PostgreSQL-backed metadata API tests. See `frontend_test_result.md` for measured outcomes.
