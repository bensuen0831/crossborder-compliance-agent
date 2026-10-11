# STAGE1-E2E-R1 candidate governance design

## Status

**Architecture proposal only.** `0019_stage1_candidate_governance` is NOT APPROVED. No migration/schema/product/test/route/UI implementation is included. This document makes the required approval concrete; the R1 task stops at this boundary.

Required identity: `(tenant, project, draft ProjectVersion, preparation_id, immutable input/config universe)` plus separately recorded `(preparation_id, candidate_type, candidate_id, decision revision, actor, time, original digest, action, override)`.

Preparation and decisions belong to a shared pre-formal input application owner. Existing candidate tables, document/source authorities, Project/ProjectVersion, Model/Prompt/Policy registries, AuditEvent, Snapshot and context/formal owners remain canonical. M2-D ReviewTask is not reused.

## Proposed canonical flow

1. User submits typed structured inputs to a DRAFT ProjectVersion. Native parsing uses genuine linked DocumentVersions and existing parse tasks/source traces.
2. `PrepareDocumentCandidates(project_id, expected_draft_version, idempotency_key)` authorizes the actor/project and captures the exact draft, document, parse and AI/config universe. It creates a real preparation identity, not an AnalysisSnapshot.
3. Where necessary, the existing governed gateway invokes local/remote HTTP with typed DRAFT_PREPARATION scope and DOCUMENT_CANDIDATE_EXTRACTION purpose. All current model usage, invocation, routing, prompt, provider health, redaction and data-boundary checks apply.
4. Candidates remain immutable and UNVALIDATED. A completed immutable preparation manifest references exact candidates, SourceTraces, request groups and versioned configuration. Preparation never creates formal objects or starts a workflow.
5. CandidatePreview returns bounded source excerpts, proposed values, confidence, extraction method, origin and exact preparation references. GET/reload never invokes LLM again.
6. `ResolveDocumentCandidates` records ACCEPT/REJECT/EDIT under trusted actor identity, draft version, preparation digest, decision CAS and idempotency. EDIT records an override; it does not mutate the candidate. No speculative MERGE action is added.
7. ConfirmProjectIntake locks/revalidates current DRAFT and document/config universe, requires decisions for all material document-derived candidates, then creates the real immutable Snapshot and formalizes only the authorized inputs. It performs no new document semantic extraction.

## Proposed 0019 minimum persistence scope

### Candidate preparation owner

Add `candidate_preparations` with:

| Fields | Purpose |
| --- | --- |
| preparation_id, tenant_id, project_id, project_version_id | Real aggregate identity and exact immutable draft binding; Project/PV FKs use RESTRICT |
| preparation_generation, state, record_version | Explicit preparation/CAS revision; distinct from ProjectVersion and context-resolution versions |
| input_universe_digest, config_universe_digest, request_hash | Draft/doc/parse/AI equality and idempotent operation identity |
| prepared_by, requested_at, completed_at, failure_code | Trusted actor, timing and durable outcome, including failed attempts |
| manifest_json, manifest_digest | Typed exact pins/candidate universe; complete manifest is sealed once, never rewritten |

Indexes/constraints: unique `(tenant_id, project_version_id, preparation_generation)`; index `(tenant_id, project_id, project_version_id, state)`; state checks for PREPARING/COMPLETED/FAILED; completion requires a manifest digest. Repeated prepare for an unchanged completed universe returns the existing identity; a changed security/config universe requires a distinct generation, never overwrites the sealed manifest.

The application takes the existing Project row lock and validates expected draft version plus preparation record_version before mutation. Draft edits/document replacement/successor versions cannot transfer old decisions. A preparation's temporary lifecycle state does not allow its completed manifest to change. No new generic task scheduler is required by this proposal; reuse native parse task persistence and existing idempotency receipts.

`manifest_json` contains typed, versioned, secret-free fields:

- Project/PV and structured-input digest; analysis_as_of_date.
- Exact DocumentVersion/ParseRun/SourceTrace references and document membership digest.
- usage_mode/selection_mode, model/deployment/provider-version IDs.
- ModelUsagePolicy, LLMInvocationPolicy, Prompt and governed fact-type version IDs.
- Invocation group, child request IDs, applicable redaction IDs and outcomes.
- Candidate type/ID/content digest, safe original/source reference, prepared_at.

The manifest is not another registry: it references existing registry identities. It is not a Formal Context or AnalysisSnapshot.

### Append-only human candidate decisions

Add `candidate_decisions` with:

| Fields | Purpose |
| --- | --- |
| decision_id, tenant_id, project_id, project_version_id, preparation_id | Owner-scoped identity with preparation/draft linkage |
| candidate_type, candidate_id, candidate_content_digest | Exact original candidate; never accept a changed candidate under old consent |
| decision_revision, previous_decision_id | Append-only decision history; predecessor permits intentional correction with CAS |
| action, confirmed_value_json | ACCEPT/REJECT/EDIT; override required only for EDIT, original candidate remains intact |
| actor_id, resolved_at, resolved_by_type | Server identity from RepositoryContext; USER_CONFIRMATION authority |
| manifest_digest, request_hash | Bind decision to the reviewed universe and exact idempotent payload |

Indexes/constraints: FK to preparation with RESTRICT, unique `(tenant_id, preparation_id, candidate_type, candidate_id, decision_revision)`, index latest-decision lookup on that prefix. Candidate types form a fixed typed allowlist; candidate membership/digest and tenant/project/PV matching are revalidated by the application owner. No polymorphic fake FK or new candidate model is invented. Project/preparation row locking and expected decision revision enforce one winner; append-only rows reject UPDATE/DELETE through the owning adapter (and migration-level protection can be reviewed for these new tables).

Reusing ApiIdempotency receipts preserves same key/same payload replay and same key/different payload conflict. These receipts reference the preparation/decision result; they do not become consent records. Record formal candidate→object mapping later in existing resolution tables, with USER_CONFIRMATION authority and confirmed decision references carried in exact Snapshot/context provenance. Do not insert a pre-authorization row into candidate_resolutions.

### Extend the existing audit authority

Retain **one** `audit_events`. Do not introduce CandidateAuditStore, ReviewRuntime or a second gateway.

A clean typed scope extension should support:

- SNAPSHOT: actual analysis_snapshot_id and workflow_run_id; existing registry pins and exact current authorization.
- DRAFT_PREPARATION: project_id, project_version_id, preparation_id, DOCUMENT_CANDIDATE_EXTRACTION purpose; actual run/Snapshot identities absent.

For R1 gateway events, propose adding scope/project/PV/preparation reference columns and permitting NULL run/Snapshot identities **only under the corresponding draft-scope constraint**. Snapshot events retain non-null real identities. Tenant/project/PV/preparation equality remains application-authorized and reference-checked. Existing EXTERNAL_OPERATION blank-string records must be preserved as the legacy external-operation representation; do not reinterpret them as Snapshot or preparation events or reject them retroactively.

Audit minimum payload is allowlisted tenant/project/PV/actor/purpose/model/deployment/provider/policy/prompt/request/group/redaction/outcome/time. No raw source text, provider response, URL credentials or secret is stored. Invocation-start and terminal outcomes are separate append-only events with stable request identity. Do not put ProjectVersion IDs, zero UUIDs or fabricated Snapshot IDs into the Snapshot column.

The existing external empty-string convention proves that generic pre-snapshot audit is present. An alternative scope-in-provenance adapter over that convention is possible only with an explicit typed absence/legacy compatibility decision. It would still not create the missing preparation and decision identities, so it does not remove the two-owner migration proposal. Review audit-column necessity separately; no audit redesign is inferred to be already approved.

## Ownership and security

Preparation and decision commands require current project access, tenant scope, actor permissions and expected_version. Invocation additionally requires llm:invoke and all existing governance. A caller cannot submit actor_id or a completed manifest as authority. Structured inputs already explicitly submitted by the user do not become candidates for the same fields.

Preparation authorizes DRAFT_PREPARATION only for document candidate extraction and typed pre-confirm triggers. Knowledge query expansion, result explanation and formal-time model use remain SNAPSHOT-scoped. Draft catalog eligibility is not an invocation bypass. MULTI_MODEL children preserve independent candidates and provenance; no majority vote establishes formal input or law.

Only user-authorized document candidates enter BusinessFact/DataItem/DataFlow/Product Context formalization. Rejected IDs are excluded before normalization; structurally valid/high-confidence candidates cannot bypass the gate. Typed structured input remains authoritative; a conflicting document value requires explicit resolution and cannot overwrite it silently.

## Confirmation, temporal safety and error contracts

Confirmation requires the current draft to equal the reviewed preparation's PV, exact document/parse/AI/structured-input/candidate digests to match, and all required decisions to exist. It revalidates current security/revocation without resolving a replacement latest model/prompt/policy. Stable errors:

- Unresolved material candidate: CANDIDATE_CONFIRMATION_REQUIRED.
- Changed draft/document/parse/preference/input universe: CANDIDATE_PREPARATION_STALE.
- Revoked/disallowed/security-blocked pinned configuration: CANDIDATE_PREPARATION_REVALIDATION_FAILED.

The owning confirmation transaction freezes approved preparation/decision IDs/digests, documents/parses, exact preparation model/provider/deployment/prompt/policy/fact-type versions and structured input into real Snapshot provenance and existing pin authorities. It copies checked exact identities; it does not select latest or call extraction. Formal BusinessFact provenance joins candidate→decision→SourceTrace→ParseRun→DocumentVersion and child LLM request/config references. It uses USER_CONFIRMED_DOCUMENT_CANDIDATE or a reviewed equivalent resolution_method, never POLICY as user consent.

Future input creates a successor ProjectVersion, new preparation and new decisions, then S2. Neither late candidates nor active configuration changes mutate S1. Pre-confirm candidate approval is distinct from M2-D formal workflow review.

## Channels after approval

Shared Prepare / Preview / Resolve use cases adapt to Web, External API and SDK contracts. Suggested internal routes are POST candidate-preparation, GET candidate-preview and POST candidate-decisions under the canonical project API. External API exposes equivalent authorized commands, rather than its own resolution rules. Both confirmation paths reject unresolved candidates server-side.

Web Candidate Review supports zh-CN/zh-HK/en-US, bounded document/locator/excerpt/confidence/model-origin display and ACCEPT/REJECT/EDIT. Confirm disabled state is UX; the shared server use case remains authority. No frontend-only checkbox constitutes consent.

## Upgrade, downgrade and historical compatibility

Proposed revision: `0019_stage1_candidate_governance`; down_revision: `0018_phase1h_multijurisdiction_classification_identity`. **No DDL file exists.**

Upgrade would add preparation/decision storage and the reviewed scoped audit extension. It must not mutate 0001–0018, existing candidates/formal resolutions, historical Snapshot/results, ReviewTask/ReviewDecision, runtime/checkpointer or 0018 jurisdiction-aware uniqueness. Existing history is not backfilled with fabricated user consent. Existing Snapshot LLM audit is read under its original identity; legacy external events remain readable.

Downgrade must refuse if preparations, user decisions, draft-scope LLM audit or Snapshot references retain R1 authority. It may drop new empty storage and restore old audit constraints only when data is provably compatible. It must not cascade-delete candidate authorization, fabricate non-null Snapshot IDs, erase provenance or silently remove authority. Re-upgrade on the permitted empty/non-authoritative dataset must restore the same schema.

Required migration evidence after approval: fresh→0019, exact0018→0019, schema equivalence, legacy data preservation, empty safe downgrade/re-upgrade, retained-authority refusal, one Alembic head, unchanged historical migration digests. All are **NOT EXECUTED** now.

## Recovery acceptance plan after approval

Reuse the retained real PostgreSQL/HTTP/DOCX/local-HTTP counterexample. First prove preparation/preview produces no formal objects; premature Confirm returns CANDIDATE_CONFIRMATION_REQUIRED; actor-owned ACCEPT followed by Confirm formalizes. Add REJECT, EDIT, original-candidate immutability, exact SourceTrace/LLM/decision provenance, stale draft/document/AI universe, current revocation, multi-model conflicts, structured precedence, idempotency/CAS, snapshot exact pins and successor immutability cases.

Then verify shared external/Web/SDK ownership and three-locale recovery Browser journeys, additive architecture rules, full M2-A/B/D/E and Phase1K-B regression, backend≥910 with zero failed/error/skipped/deselected, runtime25, frontend≥135 and existing browser≥60 with zero retries. Update ownership evidence through reviewed exact Git blobs; do not widen frozen-owner checkers to self-certify current working files.

Do not begin the four-outcome Full Stage1 Browser matrix before R1 PASS. Do not create a PR before the owner contract and focused real evidence are clear. No legal engine, country branch, Stage2 generation or production-auth redesign belongs in this recovery.
