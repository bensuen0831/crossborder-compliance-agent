# Phase 1H — Track A design

The backend evaluates closed, statically typed JSON rules against authorized Phase 1E formal facts and produces provenance-bearing RuleHit records. Formal classification combines matching hits within a published jurisdiction-specific scheme version. It never infers formal facts from raw text or model narratives.

## Boundaries and existing authority

`rule_ast.py` parses JSON → immutable typed AST → static field/operator/type checks → bounded typed values → pure evaluation. `rules.py` owns the versioned runtime contract and deterministic hits. `classification.py` owns typed scheme membership, actions, results and insufficient/review outcomes. `ClassificationService` orchestrates its repository protocol; infrastructure performs authorization, snapshot preparation, existing-evidence revalidation and canonical persistence.

The existing Phase 1C rule definitions/versions/test cases, classification schemes/versions and RegistrySyncEvent/RegistrySyncService remain authoritative. The existing Phase 1B RuleHit, classification result/member tables receive additive provenance; no parallel store is introduced. Existing Phase 1E project/context/data-item versions and snapshot pins select facts. Existing Phase 1F/G evidence and citation authorization supply evidence references. Legacy configuration-only rule versions remain readable but cannot run as V1 contracts.

## Version initialization and replay

An authorized caller explicitly pins an ACTIVE, date-effective scheme and eligible ACTIVE published V1 rules to the existing analysis snapshot registry-pin table. Execution requires these pins; even an empty rule set remains empty after later publication. Pinned approved/published superseded, expired or archived versions remain available for historical replay. A new scheme version requires a new snapshot; results are immutable and unique per tenant/project/snapshot/item/scheme version.

A rule includes version, field schema, conditions, classification actions, jurisdiction/industry/scenario/product/data-category scope, severity, priority, legal basis references, evidence requirements and effective dates. Classification confidence inherits formal fact quality, not legal probability. Unknown/missing input cannot manufacture a positive decision.

## Ownership and exclusions

Track A owns backend rules/classification, 0008 and necessary shared persistence/admin/API registration extensions. Shared review surfaces are listed in the handoff. Migration-lineage changes only improve schema test infrastructure and retain the frozen business assertions. Phase 1I applicability, Phase 1J risk/path, Phase 1K LLM and frontend/admin UI are excluded.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
