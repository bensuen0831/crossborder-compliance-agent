# Phase 1H typed AST

`parse_ast` fully validates every branch before returning immutable `TypedNode`/`ValidatedAST` values, a stable schema tuple and referenced field names. Operator compatibility is checked statically; collection element scope is closed. Evaluation accepts only the exact validated AST and a fact dict, reconstructs/revalidates the bounded closed representation, then validates all fact values before evaluating.

A missing non-exists field raises `MissingRuleFact`; the service returns INSUFFICIENT_INPUT. `exists` explicitly handles absence/null. Nullable comparisons propagate Unknown using three-valued and/or/not; Unknown cannot match. Empty any/all return false, avoiding vacuous positive legal decisions. Comparisons are performed only on exact validated primitives; malicious Python objects cannot inject comparison or timezone behavior.

Parser and runtime limits are enforced independently. `test_phase1h_ast.py` provides 35 executed cases; runtime/lineage tests are separate, not substituted for typed AST tests.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
