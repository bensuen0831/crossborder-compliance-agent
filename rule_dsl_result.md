# Phase 1H closed rule DSL

DSL version 1 uses only `and`, `or`, `not`, `eq`, `ne`, `in`, `contains`, `gt`, `gte`, `lt`, `lte`, `exists`, `date_before`, `date_after`, `any`, `all`. Logical nodes contain `op,args`; predicates `op,field,value`; exists `op,field`; quantifiers `op,field,where`. Quantifier predicates reference only `$item`.

```json
{"op":"and","args":[{"op":"gte","field":"record_count","value":100},{"op":"eq","field":"sensitive","value":true}]}
```

Fields have flat public names and declared `string`, `boolean`, `integer`, `decimal`, `date`, `datetime`, `code`, `list` or `set` types, with explicit nullable support. Code values use an allowlist. Decimal literals use strings or integers, date values ISO dates, datetime values aware fixed-offset ISO datetimes. Facts are exact built-in typed values; strings are normalized to declared dates/Decimal in the persistence adapter. Boolean is never treated as integer; floats do not silently become Decimal.

Unknown operators/fields/keys, duplicate JSON keys, invalid arity/type, nested collection schemas, attribute paths and oversized inputs fail before evaluation. Bounds: JSON 65,536 characters, 1–100 fields, AST depth 20/nodes 200, 1–50 logical operands, collection 1,000 items, string 4,096 characters, signed-64-bit integers and finite Decimal magnitude ≤1e30. No eval, exec, dynamic import, reflection, command, file/network or model capability exists in the evaluator.

Evidence: `test_phase1h_ast.py` covers every operator, numeric/date/code/collection/null handling, hostile expressions, oversized input, forged AST/comparison objects and executable timezone hooks.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
