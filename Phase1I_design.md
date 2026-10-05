# Phase 1I design / reuse and source-of-truth decision

Verified base: `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7`, tag `v3.6-phase1h-pass`; start gate PASS. Track `phase1i-applicability-country-scenario` exclusively owns0009; no other worktree is changed.

## Canonical regulation map — decision before implementation

Phase1F `knowledge_documents` identifies a regulation document; `knowledge_document_versions` is its reviewed/effective immutable version. REGULATION knowledge type is represented by canonical knowledge structure node types and governed collection/source metadata. `knowledge_structure_nodes.regulatory_structure_node_id` extends canonical Phase1B `regulatory_structure_nodes`; ingestion writes `regulation_version_ref = knowledge_version_id`. These nodes retain jurisdiction, official source and article/section path; citations retain their locator and canonical evidence. `legal_basis_items` references those canonical nodes and retains official source/locator. Existing `legal_basis_rule_hit_links` and `legal_basis_evidence_links` provide M:N provenance.

There is no missing normalized regulation identity blocking this phase. Decision: REUSE these identities, versions, structures and links; do not create Regulation, RegulationVersion, Article, Section or LegalBasis tables or alternative authoritative documents. The applicability result references this chain, never copies a regulation corpus into another store.

## Substantial component decisions

| Component | Decision | Reason / authoritative owner |
|---|---|---|
| Jurisdiction / Scenario / Skill | REUSE | Canonical jurisdictions and metadata_definitions + existing registries |
| CountryComplianceProfile | EXTEND | Typed payload kind COUNTRY_PROFILE in existing MetadataDefinition/Version, own-tenant jurisdiction/capability/binding refs |
| ScenarioAdjustmentProfile | EXTEND | Typed payload kind SCENARIO_ADJUSTMENT in existing versioned metadata; references existing SCENARIO |
| Country capabilities | EXTEND | Typed payload kind COUNTRY_CAPABILITY; discovery, availability and controlled boundary, no new country classifier/obligations |
| Applicability configuration | EXTEND | Typed payload kind APPLICABILITY_CONFIG; existing Phase1H RuleHit decisions and canonical legal references |
| Metadata governance/publish | EXTEND | Existing lifecycle/review/publish/outbox, add validation and immutable H+ profile guards; no duplicate publish service |
| Snapshot config pins | REUSE | Existing AnalysisSnapshotRegistryPin with explicit I configuration initialization, marker freezes even empty sets |
| Formal applicability result | CUSTOM_BUILD | No existing authoritative applicability table; minimal new regulation_applicability_results with canonical FKs, full immutable provenance and retry identity |
| Rule/classification | REUSE | Consume already-authorized Phase1H result/RuleHit and existing explicit pins; never rerun unpinned rules or classify independently |
| Evidence/sufficiency | REUSE | Phase1G scoped_saved_response revalidates Phase1F permissions/filters; retain fallback for deficient evidence |
| Generic skills and Country facade | CUSTOM_BUILD | Pure typed operations and application ports; no ORM/provider/country branches; facade delegates classification/evidence through authorized adapters |
| Dependencies | REUSE | Existing Pydantic/SQLAlchemy/Alembic/FastAPI; no dependency addition |

## Resolution semantics and scope

The fixed semantic pipeline remains Requirement/Scenario → Context → Data/Flow → Jurisdiction → Scope → Evidence → Sufficiency → Classification → Applicability → (future) Obligation/Path/Risk/Recommendation/Final Path. Scenario profiles merge configuration deterministically, never produce another graph or reorder this chain. Required/disabled skill conflicts, contradictory requirement/check/risk-priority/evidence-profile bindings produce typed review conflicts; required skills cannot be silently disabled. Conditional skills activate only through explicit typed input requirements.

Capability discovery is profile-based. Classification delegates to Phase1H; other capability contracts provide CONFIGURED, NOT_APPLICABLE, CAPABILITY_NOT_CONFIGURED or REVIEW_REQUIRED with rule/evidence/profile provenance; they never create obligations or legal mechanism-specific Python skills. Adding a test jurisdiction must use metadata/profile bindings only.

Applicability configuration references canonical knowledge version, jurisdiction, legal bases/nodes, required rule definitions and a typed decision mapping from persisted Phase1H matching hits. Classification and hit identities, pinned config, effective dates and authorized scope are checked before resolution. Missing evidence, partial/insufficient/conflicted Phase1G sufficiency and review/conflicts fail conservatively with preserved fallback. Scenario-only decisions require validated formal scenario/jurisdiction/facts and independently sufficient evidence; no fake classification.

## Persistence and migration

Country/scenario/capability/applicability versions remain existing metadata rows. New0009 contains only the missing applicability result table plus profile/result/pin immutability guards and required indexes/constraints. Migrations0001–0008 are unchanged. Fresh PostgreSQL and archived exact baseline0008→0009 must yield equivalent schemas, and empty downgrade must round-trip; authoritative I metadata/results/pins prevent destructive downgrade.

## Security and interfaces

Requests contain references only. Trusted RepositoryContext supplies identity/tenant/permission; operation and project scopes are required. Existing Phase1E project/snapshot/context versions provide actual subject, jurisdiction/scenario/product/data flow references. Existing Phase1G scopes enforce org/project/product/resource/sensitivity/knowledge/evidence authorization. Classification reads and saved evidence reads revalidate permissions. Profile references are same tenant and kind, ACTIVE/effective/durably published on new pins; replay uses exact previously published version refs without refreshing.

No Phase1J obligations/risk/path, Phase1L workflow, UI, raw provider or document generation is implemented. PASS and Phase1J entry issuance are withheld until full local and exact final remote gates pass and all delivery documents are complete.

## Explicit scenario-only adapter gap decision

Phase1H's application classifier stops when there is no data inventory. Its existing pure SafeRuleEngine already accepts `data_item_id=None`, and the canonical RuleHit table supports SCENARIO. EXTEND only the authorized adapter: an explicit scenario RuleHit operation consumes validated Phase1E business facts and scenario/jurisdiction references, already pinned Phase1H rule versions, and the same authorized Phase1G PROJECT evidence pack. It delegates to the existing H engine and persists canonical SCENARIO RuleHits without manufacturing a ClassificationResult. Scenario applicability requires independent sufficient evidence and `requires_classification=False`; data-specific capability operations remain NOT_APPLICABLE or insufficient input. No second rule engine, country classifier or rule source of truth is introduced.

## Multilingual metadata reuse / gap decision

`I18N_METADATA_BACKEND_GAP`: no reusable generic typed label/fallback resolver or API locale presenter existed. RESOLVED by one optional `localized_display` / `localized_code_labels` payload convention inside the existing MetadataVersion authority, including the existing canonical `JURISDICTION_CONFIG` overlay. No translation table, locale registry, duplicate jurisdiction/configuration identity or new migration is needed. All I typed configuration payloads support the same contract; SCENARIO and SKILL generic payloads reuse it. Locales are zh-CN, zh-HK and en-US. Governance validates typed labels at draft and publish; profile versions retain labels with their version. Runtime metadata APIs expose labels and deterministic presentation. Fallback is requested locale → governed fallback locale → canonical display name/code. No runtime machine translation is invoked.

A separate applicability presentation endpoint resolves labels from the result's exact pinned configuration version and returns the untouched formal result beside presentation metadata. Formal status/reason codes and official source/evidence/citation language never change with locale. UI switching, frontend resources and document translation remain outside Phase1I.
