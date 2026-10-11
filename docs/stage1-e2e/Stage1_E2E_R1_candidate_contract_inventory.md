# STAGE1-E2E-R1 candidate contract inventory

## Decision and scope

**D0 investigation complete; implementation blocked pending persistence architecture approval.**

`HIGH_REASONING_ESCALATION_REQUIRED — STAGE1-E2E-R1 = BLOCKED`

Proposed, **not approved or implemented**: `0019_stage1_candidate_governance`.

The missing identity is a durable, draft-bound preparation and human authorization record which exists **before** any Snapshot/formal object, and survives later candidate→formal mapping without changing its original meaning. Existing immutable intake versions, parse provenance and post-formal resolution records do not own this identity. Storing arbitrary JSON is technically possible; the decision below concerns preserving the existing owning contracts, not a claim that PostgreSQL JSON cannot encode the data.

The stop follows the user's R1 sections 34–38 and 54: establish D0 first, stop if the existing schema cannot represent the required authority without semantic abuse, and do not create 0019 before architecture approval. No production implementation, schema change, new migration, PR, merge or tag was performed.

## Revalidated baseline

| Item | Observed value |
| --- | --- |
| HEAD / origin/main | `df3a10923734495d728981f4f319b66afadf8c71` |
| Annotated tag | `v3.7-m2e-pass` |
| Tag object | `c92daef5b47136fb14e2782c737927176d45086a` |
| Dereferenced tag | `df3a10923734495d728981f4f319b66afadf8c71` |
| Alembic head and diagnostic DB revision | `0018_phase1h_multijurisdiction_classification_identity` |
| Existing checkout | `milestone-stage1-full-e2e`, HEAD still baseline; no R1 product commit |
| Diagnostic database | Real PostgreSQL 17.11; this is not a new full regression run |

The earlier D0 files and user-owned `Phase1H_integration_closure.md` remain intact. Historical production acceptance counts 910 / 307 / 25 / 135 / 60 are baseline references, not newly measured R1 results.

## Original counterexample and current call order

The retained `evidence/stage1-full-e2e/candidate_confirmation_counterexample.json` records real PostgreSQL, HTTP, genuine DOCX and a local HTTP LLM provider. The sole confirmation request contained `expected_version`; semantic requests before confirmation were zero. Confirmation produced one semantic HTTP invocation, candidate `c58c33e7-7103-41f3-b659-76a8be4703ef`, formal fact `b8146e35-23b1-4599-8a9c-1cd7531c505b`, `VALIDATED`, and resolution `ACCEPTED / POLICY`, without an intervening candidate decision.

`infrastructure/intake_composition.py::prepare_snapshot` first freezes LLM configuration for the real Snapshot, then invokes `prepare_document_candidates`, pins documents/parses and runs context resolution. `application/context_services.py::BusinessFactNormalizationService.normalize` assigns `VALIDATED` to non-conflicting governed document candidates and writes POLICY resolution. Confidence is not an authorization gate.

The existing counterexample's zero formal flow counts are **not** proof that a submitted DataFlow failed: that diagnostic did not submit a flow. Additional candidate-family findings below are static source evidence, not new end-to-end demonstrations.

## Ten persistence questions

### 1. Can ProjectVersion.intake_json safely own the preparation and decision history?

**It can encode a typed payload, but cannot preserve the existing immutable-version contract while adding the required later events to the same version.**

`models.py::ProjectVersionEntity` has JSON `intake_json` and unique `(tenant_id, project_id, version_no)`. `ProjectIntakeContext` rejects extra fields and has no candidate-governance annex. `project_intake.py::update_intake` marks the old version SUPERSEDED, leaves its payload immutable, creates a new version and copies document links. This is also explicit in `docs/m2a/M2A_design.md` and `M2A_persistence_result.md`.

Counterexample to JSON reuse: prepare P1 against V1; append ACCEPT by an ordinary intake update; the authoritative intake is now V2, while P1 and its decision must bind V1. R1 requires such a ProjectVersion change to stale the authorization. Updating V1 JSON in place instead would change the frozen payload contract. Rebasing P1's authorization onto V2 would waive the required stale gate. Creating a private mutable JSON event stream inside V1 would therefore be an additional architecture decision, not a reuse of the current immutable intake contract.

Extending `ProjectIntakeContext` also requires explicitly excluding any server-owned fields from dynamically derived `IntakeFacts`; otherwise callers could submit authority fields. That is a security consideration for an alternative design, not a JSON storage limitation.

### 2. Can CandidateResolutionEntity own both pre-confirm authorization and later formal mapping?

**No under its current identity and version semantics.** It owns candidate→formal resolution, unique `(tenant_id, candidate_type, candidate_id, version)`. Its `version` belongs to context resolution, not a draft/preparation revision. There is no preparation identity, ProjectVersion identity, actor field or edited-value record.

`context_repositories.py::save_candidate_resolution` returns an identical existing row and rejects any changed state with `IMMUTABLE_CANDIDATE_RESOLUTION_REWRITE`. A pre-confirm row with `formal_object_id = NULL` and USER_CONFIRMATION cannot later be changed to include the newly created formal object at the same unique identity. Using another version would overload the context-version namespace; using a synthetic formal-object type would overload candidate→formal mapping.

A real-adapter probe tried to replace the retained counterexample's POLICY mapping with USER_CONFIRMATION and no formal ID. It was rejected; before/after row digests were identical. This probe verifies the actual guard. The reverse sequence, pre-authorization then formal mapping, follows from the same unique key and immutable state comparison; it was not presented as a separately executed workflow.

### 3. Is BusinessFactResolutionEntity an authorization record?

**No.** It links a candidate fact to a formal BusinessFact and is written by `save_business_fact` during normalization. Unique `(tenant_id, candidate_fact_id, version)` uses the formal/context version. A nullable business_fact_id does not add draft, preparation, actor/time, decision revision, or edit-override semantics. Keep this mapping owner; do not redefine it as consent.

### 4. Does DocumentParseRun provenance cover the required manifest?

**It covers source extraction lineage and must be reused for that purpose; it does not own draft-wide authorization.** `document_parse_run_details` belongs to one DocumentVersion/ParseRun, with unique document parse version. A parse can be reused by multiple draft versions. Its semantic provenance records invocation group and request/model/deployment references, but not the complete draft/config/candidate universe or independent user decisions.

`record_semantic_provenance` only permits the current genuine RUNNING ParseRun. Writing later ACCEPT/REJECT/EDIT into a completed parse would redefine parser output and conflate document extraction with project authorization. Splitting a multi-document manifest across parse JSON would add an undeclared aggregate owner and omit preparation attempts that fail before a usable parse result.

### 5. Why does AuditEvent require run and Snapshot identities?

The columns `workflow_run_id` and `analysis_snapshot_id` are non-null `VARCHAR(36)`, not UUID/FK columns. The LLM gateway's typed request/result/audit contracts require a real Snapshot UUID. `PostgresGatewayAudit.record` joins the actual Snapshot, tenant and ProjectVersion/project, reads its real workflow identity and registry pins, and rejects an absent Snapshot with RESOURCE_NOT_FOUND.

A rolled-back PostgreSQL insertion with both identities NULL failed SQLSTATE `23502` on `workflow_run_id`. An LLMRequest without Snapshot also failed typed validation. **These checks alone do not prove that the JSON audit table cannot record a draft event**; they prove that the current Snapshot-scoped LLM persistence contract cannot directly accept a properly absent identity.

### 6. Is there already canonical pre-snapshot audit?

**Yes, an important existing convention exists.** `integrations.py::audit` writes EXTERNAL_OPERATION into the same `audit_events`, serializing absent run/Snapshot references as empty strings and putting project/actor/operation in provenance JSON. No fake ProjectVersion-as-Snapshot UUID is required by that existing adapter. The diagnostic database inspected in this run had no EXTERNAL_OPERATION rows, so this finding is verified source behavior, not a new external-audit execution.

This convention must be accounted for in any audit change. It is not a typed DRAFT_PREPARATION LLM scope, and does not supply the missing preparation/decision aggregate identity. Turning audit event payloads into the authoritative operational preparation/decision store would be a separate event-sourced ownership redesign: confirm would reconstruct business authorization from an audit log rather than a candidate-governance owner. It is not selected as a shortcut. Do not create a second generic audit store; extend/reuse the existing audit authority.

Workflow events require a run. Registry sync events are delivery/outbox records. Knowledge change events belong to KnowledgeVersion governance. Admin review/publish records belong to metadata governance. M2-D ReviewTask/ReviewDecision govern formal workflow review and are explicitly excluded from pre-formal candidate authorization.

### 7. Can LLMRequest / LLMResult / GatewayAuditEvent represent draft scope now?

**No in their current typed contracts/adapters; an owning-contract extension is required.** Each requires `analysis_snapshot_id: UUID`. Introduce a discriminated SNAPSHOT / DRAFT_PREPARATION scope without a fake Snapshot or run. Draft scope may invoke DOCUMENT_CANDIDATE_EXTRACTION only. Snapshot query expansion/explanation/formal-time invocation retain their existing exact pins.

`PostgresLLMConfiguration(draft_catalog=True)` is an eligibility/catalog path: it suppresses pin persistence and cannot be reused as an invocation authorization bypass. `PinnedDocumentInput` also requires confirmed/superseded project input plus real Snapshot document/parse pins today. Draft preparation needs an authorized document input adapter over the exact draft document universe.

### 8. Can idempotency and task persistence be reused?

**Yes for their existing roles.** `api_idempotency_records` can hold request hashes and response references using existing tenant/actor/operation scoping, transaction locks and conflict behavior. It cannot itself store a preparation manifest or decision history in its bounded response_ref. Existing DOCUMENT_PARSE tasks can continue owning native parsing and parse retries; they are document-scoped, not whole-draft authorization records. Execution idempotency remains workflow-run scoped.

### 9. Can no-DB-change append-only actor/time/decision/provenance audit be done?

**Audit events can encode actor/time and structured draft provenance; this does not solve the missing canonical operational authority.** A no-schema implementation would additionally have to choose between mutable intake-version annexes, pre/post resolution namespace overloading, parse mutation, or promoting audit payloads into a new operational event store. Each changes an established owner or identity contract. No existing typed owner reviewed provides a draft-bound immutable preparation plus independent append-only human decisions while preserving the existing roles.

No user-defined immutability triggers were found on the inspected tables; existing immutability is also enforced by application owners. Lack of a trigger is **not** used alone as a reason to require a migration.

### 10. Is 0019 actually needed under the retained contracts?

**The proposed compatible path needs a new preparation/decision identity, so it crosses the user's 0019 approval gate.** Minimum design: add a draft CandidatePreparation owner and append-only CandidateDecision owner, retain candidate/source tables and candidate→formal mappings, and extend the existing canonical gateway/audit scope without inventing a Snapshot. Exact scope and alternatives are in `Stage1_E2E_R1_candidate_governance_design.md`.

The alternative of an authoritative JSON audit event stream or mutable intake annex would need explicit architecture approval to redefine those responsibilities; it is not silently treated as an approved NO NEW MIGRATION design. This inventory does not claim that every possible event-sourced JSON redesign is mathematically impossible.

## All candidate families: bypass inventory

| Candidate family | Current owning behavior | Required recovery boundary |
| --- | --- | --- |
| BusinessFactCandidate | Governed, non-conflicting document candidate normalizes to VALIDATED; POLICY mapping | User-authorized preparation universe only; unresolved blocks; reject excludes; edit preserves original |
| CandidateDataItem | Source-traced candidates normalize/merge into canonical item/detail; POLICY mapping | Same authorization boundary for document-derived input; merge only within authorized universe |
| CandidateDataFlowNode | Trace and identity checks can create formal nodes with POLICY mapping | Explicit candidate decisions before formal node creation |
| CandidateDataFlowEdge | Requires resolved nodes, direction and item links; structurally complete candidates may create edges/links with POLICY mapping | Structural sufficiency is not consent; document-derived flow input uses the same gate |
| ProductContextCandidate | Explicit user selection is separate; detected DOCUMENT_DERIVED scope may become effective when no selected scope | Review document-derived detected product candidates before use; typed product selection keeps its existing submission contract |

The present LLM edge output may lack direction and fail closed; that is not proof of an authorization gate. No new legal, country, workflow, review or Stage1 result authority is needed. Explicit structured user input remains directly confirmable when there are no unresolved document candidates.

## Evidence and limits

See `evidence/stage1-full-e2e/r1_schema_inventory.json` for introspected column/nullability/unique/FK/check metadata, rolled-back NULL audit probe, immutable-resolution probe and typed request failure. See `r1_candidate_governance.json` for digests and the stop decision.

These are D0 schema/adapter diagnostics and retained original HTTP/DOCX counterexample evidence. They are not recovery acceptance, a fresh full regression, browser acceptance, CI acceptance or paid Internet provider acceptance. Migration, implementation and focused recovery tests have not been executed.
