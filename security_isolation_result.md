# Phase 1H isolation and immutable provenance

Trusted RepositoryContext supplies tenant/actor/scopes; request bodies cannot supply these identities. Non-system access requires `classification:execute` or `classification:read` plus `project:<uuid>:classify`. Admin versions use existing metadata admin policy. Inaccessible project/snapshot/item/scheme/result/evidence identifiers fail without cross-tenant enumeration.

A snapshot must belong to the project; context and item versions must match its Phase 1E pins. Rules and scheme are tenant-scoped and snapshot-pinned. Document/source trace evidence belongs to the same project/item. The Phase 1G adapter consumes only completed own-actor exact-DATA_ITEM retrieval records and calls existing scoped_saved_response revalidation before using saved citations; generic or another-subject packs cannot masquerade as item evidence.

Persisted classifications retain their immutable historical content, but result reads revalidate current document/Phase 1G evidence access. Revoked or no-longer-authorized evidence denies the read; retries cannot return a result whose saved evidence is absent from the currently allowed set. This is exercised against real PostgreSQL, including evidence revocation, tenant/project/snapshot/data-item/operation isolation and missing-evidence/no-data outcomes.

Database triggers block modifications/deletion of formal results and RuleHits and updates of approved scheme/rule contents. Tests do not replace these invariants with mocks. No LLM call, unrestricted search, filesystem or network is reachable from pure rule evaluation.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
