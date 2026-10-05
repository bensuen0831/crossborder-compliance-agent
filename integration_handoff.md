# Phase1I — integration handoff /22 fields

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

| # | Field | Delivery |
|---:|---|---|
|1|Task|Phase1I Applicability + Country Capability + Scenario Adjustment + Generic Skills + multilingual metadata|
|2|Branch|phase1i-applicability-country-scenario|
|3|Verified base|700951ebb9ebdf33e399158fd3fb53bb4a6c87e7 / v3.6-phase1h-pass|
|4|Final SHA|Final exact branch HEAD is reported with its successful CI in the final delivery report; code SHA 131d101cdd02999aa478c1a730f492c1729caf30 is frozen and recorded in local evidence. Documentation/entry commits remain separately attributable.|
|5|PR|DRAFT #18 → main; no merge|
|6|Files|evidence/phase1i/files_changed.json and files_created_modified.md|
|7|Migration|Exclusive0009_phase1i; frozen0001–0008 unchanged; explicit immutable result/config/pin extensions|
|8|APIs|Explicit compliance-pins; country configuration/capability; scenario RuleHit; applicability execute/read/presentation; existing admin lifecycle and runtime metadata locale queries|
|9|Config|COUNTRY_PROFILE, SCENARIO_ADJUSTMENT, COUNTRY_CAPABILITY, APPLICABILITY_CONFIG, RULE_PACK in canonical metadata; optional generic locale payloads|
|10|Dependencies|No added packages; existing Pydantic/SQLAlchemy/Alembic/FastAPI/PostgreSQL/Redis|
|11|Architecture|Rules1–139 frozen;140–151 appended;135 executable checks|
|12|Tests|Domain/locale, actual PG/API, all statuses/security/no-data/flow/history/zero-code/resource publication and fresh/exact0008 dual-path migration plus full regressions|
|13|Local gate|Final observed measurements are linked from test_result.md and evidence/phase1i/local; zero skips/deselections required|
|14|Remote gate|Exact final-head SUCCESS required; verified run/jobs/artifact API evidence; no assumed remote log digest|
|15|Consumed contracts|E context/items/flows/pins; F canonical source/scope/versions; G evidence/sufficiency/fallback; H formal classifications/RuleHits/pins; C metadata/registries/outbox/admin|
|16|Provided contracts|Typed profile/merge/capability facade/boundaries, formal RegulationApplicabilityResult, pinned config APIs and generic display presenter|
|17|Risks/limits|Availability boundaries do not implement legal obligations; reviewed configuration is required; existing evidence-owner and H read permissions remain required; missing/ambiguous/expired/unpublished references fail conservatively|
|18|Merge order|Integrator reviews shared admin/registry/main/gate changes alongside integration/stage1-alpha and phase1l-a-workflow-skeleton; apply only one0009 and do not silently renumber or rewrite the frozen lineage|
|19|Post-merge checks|Verify exact merged head, migration graph, fresh/exact0008 equivalence, full smoke/schema/architecture/pytest and all shared interfaces. No merge or post-merge success is claimed here.|
|20|Demo|Run scoped retrieval/H classification, explicit I pins then applicability; second configured jurisdiction/filing availability uses same facade; metadata locale queries change display only. Tests are executable examples.|
|21|Entry decision|Phase1J_entry_decision.md is issued only after final-code local and delivery-head remote gates PASS; it does not authorize starting J in this task.|
|22|Decision|Closure PASS only after the cited local/remote gates; stop after I and retain DRAFT PR.|

API integration: trusted RepositoryContext must authorize tenant plus operation/project scopes. Pin I configuration explicitly before use. Supply only project/snapshot/subject/jurisdiction/config/retrieval and existing H result/hit references. Scenario-only callers must obtain explicit scenario RuleHits from formal facts plus scoped PROJECT evidence and use a reviewed config that does not require classification. Consumers must preserve review/conflict/fallback and never reinterpret CONFIGURED availability as a legal obligation.

Presentation integration: request zh-CN/zh-HK/en-US on runtime metadata APIs, or the separate applicability presentation endpoint. Consume resolved presentation and fallback provenance; use unchanged machine codes for behavior. Do not replace original source/evidence/citation text with labels. Backend gap I18N_METADATA_BACKEND_GAP is resolved within the existing version store; UI resources remain outside this delivery.
