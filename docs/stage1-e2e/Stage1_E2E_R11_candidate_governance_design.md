# Stage1-E2E-R1.1 approved owning recovery

Formal base: `df3a10923734495d728981f4f319b66afadf8c71`, annotated `v3.7-m2e-pass`. This continues the frozen D0/R1 counterexample and design; it does not reopen the approved migration decision. `0019_stage1_candidate_governance` follows frozen0018 and is owned solely by Stage1 Input Governance, Document Candidate Governance and LLM Pre-confirm Preparation.

## Authority and persistence

Six relational identities record CandidatePreparation, exact DocumentVersion/ParseRun pins, exact registry pins, existing candidate membership/digest/origin, an immutable CandidateDecisionSet and individual ACCEPT/REJECT/EDIT decisions. Candidate payload authority stays in the existing four candidate tables. Existing BusinessFactResolution/CandidateResolution remain candidate-to-formal mappings. JSON holds bounded edited values and safe metadata, not parallel identity or registry stores.

A preparation requires the current DRAFT ProjectVersion and expected version. The project row lock and canonical idempotency receipt serialize mutations. An exact completed universe is reused without another provider call. Failed preparation/audit is retained; a new idempotency key may retry without erasing failed history. Preparation pins and membership seal on completion. Decision sets seal in their submission transaction; new decisions create a new set rather than editing old authorization.

Database constraints require same tenant/preparation membership for decisions, genuine draft ownership, exact parse-to-document relationships, and actual matching pre-confirm LLM completion audit for each model-derived candidate. Triggers prevent changes to prepared candidate values/source links, sealed authorities and pre-confirm audit. No existing migration byte is changed. Safe empty downgrade/re-upgrade is supported; any governance data or dependent draft audit causes `STAGE1_CANDIDATE_GOVERNANCE_DOWNGRADE_REFUSED` before schema loss.

## Gateway and provenance

Typed SnapshotInvocationScope and DraftPreparationInvocationScope are distinct. Draft scope contains real preparation/project/version identities, permits only DOCUMENT_CANDIDATE_EXTRACTION with approved document triggers, and rejects query expansion/explanation. The same Gateway, router, model registry, policies, provider adapter, secret and redaction boundaries are reused. No fake Snapshot/WorkflowRun exists.

The shared preparation owner authorizes only its exact published purpose-bound document extraction prompt after current project/LLM authorization. This supports External API credentials without caller-provided prompt permission or identity. The Gateway still checks prompt permission, ModelUsagePolicy, LLMInvocationPolicy, provider health and data boundary; other purposes and Snapshot invocation are unchanged.

Each model candidate retains its actual child request and invocation-group identity. Preview returns bounded source excerpt/locator, exact document/parse references, confidence, AI origin and safe provenance. It never exposes provider keys, hidden prompts or unrestricted responses. Audit uses the existing canonical AuditEventEntity with a genuine DRAFT_PREPARATION scope and null workflow/snapshot references. Historical audit remains LEGACY; workflow audit remains valid.

## User authorization and confirmation

Web, External API and SDK call the same prepare/preview/resolve/confirm application owner. Actor/time are server-owned. ACCEPT/EDIT authorize only the exact prepared proposal or bounded override. REJECT is excluded. The original proposal and SourceTrace stay immutable. MULTI_MODEL proposals remain distinct; no legal vote is introduced. Structured user fields retain precedence and native deterministic candidates retain their existing governed owner.

Confirm explicitly names a DecisionSet when LLM candidates require consent. Missing or incomplete decisions fail before Snapshot creation. Draft, document/parse and candidate digests must match. Current model/provider/policy/prompt/fact-type security is revalidated; revoked configuration fails without substituting latest. Valid exact preparation pins transfer to canonical Snapshot pins. Context normalization reads only the accepted/edited authorized universe and records USER_CONFIRMATION, not POLICY, as its acceptance authority.

Confirm contains no document candidate generation and makes no document LLM request. The real HTTP counterexample tests stop the provider before confirmation and still require success. Exact prepared fact-type versions are retained after a legitimate future publication. Historical Snapshots need no retroactive0019 decisions; changed input creates a successor draft/preparation/decision/Snapshot and leaves its predecessor unchanged.

## Acceptance and boundaries

Focused tests precede full PostgreSQL backend, 24 additive architecture checks, durable runtime, frontend quality and original browser regression. Five focused browser cases add genuine DOCX, three-locale ACCEPT and REJECT/EDIT coverage. `Stage1 R1 Candidate Governance Recovery` CI records exact checkout identity and retains all existing mandatory regression workflows.

This is not Full Stage1 outcome-matrix closure. No Direct/Conditional/Localization/Review × locale business matrix starts here. No legal result owner, M2-D review authority, Master Specification, Stage2, model registry or workflow runtime is replaced. Paid Internet LLM remains NOT EXECUTED; mandatory extraction uses actual local HTTP providers.
