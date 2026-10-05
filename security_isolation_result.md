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


# Phase1I — security and isolation

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

Trusted RepositoryContext supplies tenant/actor/scopes. Applicability execute/read and project:{id}:comply scopes are required; current H result and G saved evidence authorization remain in force. Read does not require execute permission, but retains the existing classification/evidence read permissions and owner visibility. Wrong tenant/project/snapshot/jurisdiction/subject/config/retrieval/H-result references fail closed. Result writes reject identities differing from the original request.

Clients cannot post tenant, facts, scope, narrative or formal applicability decisions: requests forbid extra fields. References are resolved through canonical stores; classification context/item identity, flow-linked validated inventory, saved retrieval subject, pinned config/rule/knowledge versions and evidence visibility are revalidated. Historical profile/configuration replay cannot widen the original knowledge universe. Changed scenario binding digests or required resource versions are rejected.

PostgreSQL protects profile identity/version/published payload/provenance, I pins and results. Independent I review is mandatory even for a system actor; failed validation produces no publish outbox event. Existing unrelated metadata deletion behavior is preserved. Current evidence/source revocation blocks saved positive result reads rather than leaking stale evidence.

Tests: real PostgreSQL/API cross-tenant/project/actor/operation denial, reference spoofing, wrong classification, source revocation, immutable updates, review failure, result identity and locale-neutral machine-code validation. Existing Phase1B–H security regressions are included in the mandatory full suite.


## Final actor-scoped metadata visibility

Frozen delivery implementation SHA: `b2312e9ec48bd05e3398c23f79dcfcf1faf69b9f` (supersedes the earlier131d101 implementation after final review). Registry source filtering applies versioned permission_scopes before list projection, locale presentation, health counts and version summaries. Canonical profile selection uses the same actor boundary; an unauthorized profile cannot leak through a locale query or contaminate eligible-profile resolution. The runtime API invalidates per-resource cached projections before reading so another actor's earlier projection cannot expose labels. Actual PostgreSQL/API tests switch authorized/unauthorized actors and all three locales, proving restricted names/configuration and summary counts stay hidden. The earlier passing local/CI evidence remains historical, not the final gate.
