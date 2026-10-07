# M2-A API contract

Baseline `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`; preserved WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b`. Implementation source is pinned in `evidence/m2a/approved_owner_overlay.json`. Full closure/exact-head CI are required before an overall PASS.

| Operation | Canonical route | Input / result |
|---|---|---|
| Create project + initial draft | POST /api/v1/projects | CreateProjectFromIntake → IntakeView (201) |
| Read latest or historical intake | GET /api/v1/projects/{id}/intake?version=N | IntakeView |
| Save immutable next draft version | PUT /api/v1/projects/{id}/intake | UpdateIntakeDraft(expected_version, idempotency_key, canonical facts) |
| Confirm, prepare exact snapshot/run | POST /api/v1/projects/{id}/intake/confirm | ConfirmProjectIntake(expected_version) → IntakeView |
| Existing START | POST /api/v1/projects/{id}/snapshots/{snapshot}/workflow | Existing empty extra-forbidden WorkflowStart |
| Existing READ | GET /api/v1/workflows/{run} | Existing reference-only WorkflowView |

IntakeFacts derives from ProjectIntakeContext; authority/provenance/version fields are excluded. All requests reject extra fields. Text/reference collections are bounded. Status codes DRAFT/CONFIRMED/SUPERSEDED remain locale-neutral; formal result codes remain owned downstream. Browser cannot supply tenant, policy, decisions, snapshot/run IDs or confirmation boolean authority.

Current trusted tenant/actor/action permissions and project creator or explicit project grant are checked at every operation. Exact project permissions are derived only after intake access revalidation. Unknown/unauthorized resources return404; stale/idempotency/serialization conflict409; invalid confirmed facts/binding422. Authorized legacy projects without a host plan retain409. Duplicate requests preserve canonical identities.

Existing Metadata/Registry APIs supply scenarios/products/jurisdictions/data types; one minimal DATA_CATEGORY projection was added. Existing generic localization/fallback is reused. Generated M2A schemas/types and shared AJV runtime validation live under frontend/src/api; no new transport.
