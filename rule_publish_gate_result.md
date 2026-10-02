# Phase 1H governed rule publication

Existing admin draft/update/submit/review/publish operations are reused. A V1 runtime contract is parsed at draft/update; persisted test cases are stored in the existing `rule_test_cases` table. Each test asserts expected match, actions, severity and evidence requirement. Submit, approve and publish revalidate the AST, references, tests and conservative overlap conflicts. At least one test is required. Jurisdictions, legal bases, scheme versions and membership must exist in the same tenant; actions must belong to the approved/active scheme version.

Submission records its actor; approval requires an independent actor; publication requires durable approval and passing validation. The existing publish transaction updates the definition/version and inserts its existing publish/outbox records atomically. Tenant-row locking serializes competing approval/publication conflict checks; definition locks serialize version creation. Failed tests roll back publication and emit no outbox event.

PostgreSQL guards preserve non-draft rule payload/test content, including attempts to move a test from a frozen parent. Version changes create a new version. Config-only Phase 1C rows retain historical admin behavior but have no executable V1 permission.

Real database tests cover independent review, expected-test failure rollback, own-tenant references, conflicts, immutable tests/payload and retained historical versions; API tests cover version creation, validate/test and detail routes through existing authorization.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
