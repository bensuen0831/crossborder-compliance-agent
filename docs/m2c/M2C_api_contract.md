# M2-C formal results and projection API

All authoritative contracts use stable codes, canonical tenant/project/snapshot identities, exact upstream references, policy/version pins, evidence/legal basis, digests and audit provenance. C0 owns the two immutable results; C1 only reads them.

| Capability | Existing/additive route | Authority |
|---|---|---|
| Execute Cross-border / Document Requirement | `POST /api/v1/projects/{project_id}/formal-authority-results` | Typed reference-only owning request; server prepares governed inputs |
| Read C0 result | `GET /api/v1/formal-authority-results/{stage}/{result_id}` | Current authorization and exact pinned recomputation |
| Canonical START | `POST /api/v1/projects/{project_id}/snapshots/{snapshot_id}/workflow` | Existing reference-only START contract, unchanged |
| Canonical READ | `GET /api/v1/workflows/{run_id}` | Existing M1 nine-reference contract, unchanged |
| Stage 1 workspace projection | `GET /api/v1/workflows/{run_id}/stage1-result` | Read-only `Stage1ComplianceResult` v2 |

C0 status/requirement semantics and policy governance are defined in `M2C0_design.md`. Legal transfer status is never inferred from Final Path. Requirement level is never inferred from template availability. Stage2 generation is absent.

The additive projection includes exact project/context version, pinned document versions/parse runs, inventory/flows, classification, applicability/regulations, obligations, Cross-border Assessment, candidates, risk, recommendation, Final Path, regulatory document requirements, original-language legal basis/evidence and current review/run state. Missing stages remain null. Subject IDs and formal context versions must agree. Unassessed inventory receives no invented authority.

The endpoint accepts only the run identifier. Server reconstructs the same authorized pinned plan and revalidates child readers. Unauthorized tenant/project/run, revoked access or inconsistent result scope returns 404; not-started workflow returns 409. No ORM, raw checkpoint, provider client, binary or secret is exposed.

Historic canonical v1 is supported through the same factory and readers, preserving 16-step semantics. Missing C0 authority is reported as `HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED`; it never loads newly published policies into an old snapshot. v2 executes 17 steps and requires C0 refs before completion.

The frontend M2C OpenAPI/TypeScript client is generated directly from the additive backend endpoint and runtime-validated by the existing AJV transport. M1 export remains restricted to its unchanged START/READ schemas. UI locale controls labels only; official source text and authoritative codes remain unchanged.
