# Phase 1H safe rule evaluation

SafeRuleEngine requires tenant-consistent snapshot-pinned published versions with durable approval/publication. New evaluation uses ACTIVE versions; historical evaluation accepts only previously published pinned versions. Effective intervals and jurisdiction/industry/scenario/product/data-category scopes filter eligible rules. Priority descending and version ID resolve ordering deterministically. Same-priority overlapping differing actions for one scheme are rejected conservatively rather than guessed from conditions.

Hits retain rule/version, tenant/project/item/snapshot/context version, match, actions, severity, priority, legal basis, evidence requirements/IDs/packs, matched source-fact references, evaluation timestamp, reason and validation/review status. Every referenced present formal fact needs source references. Nonmatched hits contain no triggered action, severity or matched references.

Review semantics: `facts.review_required OR (matched AND required evidence missing)`. A nonmatched rule with absent evidence does not require review solely for that absence. Matched missing evidence cannot produce a formal classification; the typed outcome is INSUFFICIENT_INPUT. Regression cases explicitly cover both branches and inherited fact review.

`test_phase1h_rules.py`: 17 executed cases for scope/dates/order/conflicts, review semantics, multiple hits, pinned history, evidence, confidence and typed no-data policy.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
