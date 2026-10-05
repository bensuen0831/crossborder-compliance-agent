# Phase1J persistence decision

Decision: **migration required for future implementation; reserve `0010_phase1j` exclusively to Phase1J**. J-A creates no migration, model, repository or schema change. Parent is `0009_phase1i`; migrations0001–0009 remain byte-identical. Reverify exclusive ownership and single-head lineage at implementation Start Gate; stop on a competing0010 rather than renumber silently.

## Proven gap and storage freeze

Baseline contains formal I applicability storage and canonical H/E/G results. `domain/contracts.py` declares J DTOs but no tables persist their authoritative results. Existing CompliancePathStepEntity/PathStepResponsiblePartyEntity represent project steps/parties and lack snapshot, upstream identity, legal/risk/config provenance and immutable decision semantics. AnalysisStageResult/Stage1 projections and LangGraph checkpoint are also not authoritative J storage. Extending those to silently become decision truth would conflate distinct frozen responsibilities.

Reserve five stage result-envelope tables: `compliance_obligation_results`, `candidate_compliance_path_results`, `risk_assessment_results`, `compliance_recommendation_results`, `final_compliance_path_results`. Each stores its typed v2 stage collection as one immutable payload; item UUIDs are envelope-scoped addresses, not separately mutable authorities. This is the sole new J result authority. No separate generic decision store, risk catalog, requirement registry, evidence store or alternate path-step truth. Reuse canonical party IDs and existing project steps when already present; prospective actions stay typed in the final payload and do not imply execution.

Each table uses existing Base/TenantAuditMixin/session infrastructure and owns result UUID, tenant/project/snapshot/project-version refs, subject discriminator/UUID, context version, as-of date, policy version refs, immutable input/pin digests, authorized owner, request identity, typed contract/engine version, summary status and canonical result payload. Obligation rows reference I applicability IDs; later rows reference prior stage envelope IDs. Cross-stage edges and evidence/policy dependencies require tenant/snapshot/subject/jurisdiction validation in the same transaction. Use scoped composite constraints/typed link rows where a stage has many upstream envelopes or policy versions; link rows are referential integrity only, not another result authority. A single-column global FK alone is insufficient tenant isolation.

Decision item IDs are deterministic from stage identity/policy entry/input digest (or allocated once in the idempotent transaction); never selected by locale or list order. Persisted envelope ID remains the canonical workflow reference. Canonical JSON payload serialization retains numeric decimal encoding, sorted unordered ref sets and ordered action/priority arrays, with schema validation and content digest. Audit timestamps are excluded from the decision digest.

## Governance / pins / lifecycle

- Reuse MetadataDefinition/MetadataVersion for the four J policy kinds. Policy entry UUIDs are stable within governed definitions; IDs referenced across versions cannot be recycled for different semantics. No missing requirement/mechanism UUID is fabricated to satisfy v1 DTOs.
- Reuse existing admin review/publish/outbox/RegistrySync transaction and independent reviewer, typed validators, effective dates and publication proof. Extend hooks rather than create a governance service/store.
- Reuse AnalysisSnapshotRegistryPin with J policy namespaces and an explicit initialization marker, dependency closure and digest. J initialization may append a dedicated immutable pin set once; it cannot rewrite E/H/I pins or snapshot columns. Empty policy coverage is explicitly pinned and unresolved rather than latest-version discovery later. Policy or context changes require a new snapshot.
- New tables, edges, policy pins and authoritative payloads reject UPDATE/DELETE after persistence. Authorize all reads/replay using fresh RepositoryContext and canonical project/upstream ownership; derived caches remain non-authoritative.
- Atomic stage save: validate authorized typed inputs and transitive pins; insert result/edges together. Unique scope/stage/subject/required-jurisdiction-set/policy-digest/upstream-digest identity permits one authoritative result for the same decision input. Exact retry returns it. Same idempotency key with different payload/fingerprint rejects; concurrent differing output for the same inputs is CONFLICTED, never last-writer-wins. No mutable approval in engine payload; reference existing reviewed decisions separately.

Implementation extends existing CountryComplianceRepositoryPort/PostgresCountryComplianceRepository prepare/save/read ownership and existing scoped persistence/session infrastructure. Focused helper modules may split implementation size, but must not create a parallel repository framework, metadata registry or duplicate authority. Pure engines receive no repository/context objects.

## Migration acceptance / downgrade

Future0010 uses explicit frozen DDL, never live Base.metadata. Verify A: fresh PostgreSQL→head; B: exact archived round2/0009 schema→0010; compare domain catalog columns/types/FKs/checks/indexes/functions/triggers and policy/pin behavior. Use the existing graph-lineage helper for earlier schema gates; preserve their assertions, never append future strings to acceptance lists.

Downgrade is transactional: empty J result/link/pin/policy state permits removal of only J additions; any authoritative J result, reviewed/published J policy or J snapshot pin refuses with an archive/export-required error and leaves revision/schema/data unchanged. Draft-only J configuration must be explicitly removed through its existing lifecycle before downgrade, never silently deleted by migration. Shared metadata/rules/knowledge/E–I rows and unrelated delete behavior must remain intact. Downgrade cannot silently rewrite earlier migrations.

No migration is needed merely to deliver this design freeze. Reservation is a design ownership record, not evidence that0010 exists or was tested.
