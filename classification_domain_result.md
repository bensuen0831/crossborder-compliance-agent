# Phase 1H formal classification domain

Versioned schemes specify one or more jurisdictions and explicit category/level membership. Draft codes resolve to existing canonical members or create members under the same scheme; immutable code/rank changes require new member codes. The membership list is frozen per published version; no global cross-country level is implied.

Classification validates hit tenant/project/snapshot/item/context identity and scheme target membership. Matching categories are combined; maximum rule priority selects levels. Equal-priority conflicting levels return REVIEW_REQUIRED without fabricating a result. Every formal result requires a target, matched RuleHit references, verified evidence, fact references and reasons. It records jurisdiction, scheme/version, record/context versions, snapshot, evidence packs, confidence and review state; generated_by is SAFE_RULE_ENGINE_V1.

No data item produces the typed policy default NOT_APPLICABLE (configurable to INSUFFICIENT_INPUT). Missing facts, rule matches, evidence or required evidence types produces INSUFFICIENT_INPUT. Neither path creates a fake classification row. Fact quality review remains REVIEW_REQUIRED. The application does not convert ordinary narrative text into formal legal conclusions.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
