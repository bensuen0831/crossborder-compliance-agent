# Phase 1G migration result

Phase: **1G — Scope-first Hybrid Retrieval / RAG foundation + Publish-driven Runtime Synchronization**.

Implementation tested PR head SHA: `beeaa0a692e97a8554e3247f6a53bf5dc23f9f0f`. Runner merge SHA: `887029e59b3bea94925be7fb0a0ddf530e59de75`.
GitHub Actions Run ID: **36989359103**, Run Number: **100**, Attempt: **1**, conclusion **SUCCESS**.
Artifact ID: **11218543793**; digest `sha256:a6c70f27ef45e3cec242b5ef6927b4faf1ca9021c6b0dde4e1d379b77442cee3`.
Remote full gate log SHA-256: `d44a8b7d3797ae03dc9d042cb9b3ce5f3fefc28082fa9298217da3ebbb7a511f`; `ci_complete.log` is retained inside that GitHub artifact.

Measured full pytest: **200 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**. Alembic head: **0007_phase1g**.
Schema assertions: Phase 1B **16/16**, 1C **20/20**, 1D **15/15**, 1E **22/22**, 1F **29/29**, 1G **58/58 PASS**.
Executable architecture checks: **108/108 PASS**; Phase 1A runtime assertions: **25/25 PASS**. Phase 1A–1F regressions: **PASS**.

Evidence: [verified remote identity](evidence/phase1g/implementation-ci/verified_identity.json), [measured remote summary](evidence/phase1g/implementation-ci/empirical_summary.json), [local complete gate log](evidence/phase1g/local-final/ci_complete.log).
This implementation CI is distinct from the subsequent documentation-only closure head. The formal closure CI and issuance identities are recorded in [Phase1H_entry_decision.md](Phase1H_entry_decision.md) only after that head passes complete CI; this document does not authorize Phase 1H coding.

## Actual migration

Alembic head = **0007_phase1g**, down revision **0006_phase1f**. Frozen DDL adds 19 tenant-audited derived/governance tables:

`retrieval_policies`, `retrieval_runs`, `evidence_packs`, `evidence_pack_items`, `knowledge_sufficiency_policies`, `knowledge_sufficiency_results`, `trusted_source_policies`, `external_evidence_candidates`, `external_evidence_validation_results`, `runtime_verified_external_evidence`, `wiki_pages`, `wiki_versions`, `wiki_source_bindings`, `wiki_citations`, `wiki_reviews`, `wiki_publish_records`, `knowledge_graph_nodes`, `knowledge_graph_edges`, `knowledge_runtime_publications`.

Canonical Phase 1F tables, existing EvidenceReference/Citation, Phase 1C registry sync/outbox/model metadata and durable Admin review are reused. No parallel Knowledge store, article/section authority, publish system, sync event store or compliance result is added.

FKs protect source/index/policy/snapshot/evidence/citation/review chains. Partial indexes enforce one active policy/wiki version. Unique keys enforce run idempotency, per-run pack, sufficiency, external snapshot/source/trust identity and publication event. CHECKs enforce exactly one evidence chain, derived/nonlegal flags, external-not-ACTIVE, Wiki/Graph review and READY index/registry/cache barrier.

PASS: real PostgreSQL migration from empty schema; `phase1g_schema_check.py` **58/58**; earlier B–F schema assertions remain intact with 0007 accepted as the current descendant head. Migrations 0001–0006 were not edited. Local development databases from earlier runs were preserved; every full gate used a separate fresh database. Downgrade drops only the new tables in reverse FK order and is operational tooling, not performed on user data.

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.


---

# Phase 1H migration extension (Track A)

Only `0008_phase1h` is new; frozen 0001–0007 are byte-identical to verified baseline. Additive columns extend canonical rule_versions/governance, rule_hits and classification_results (project/snapshot/full provenance); constraints/indexes enforce dates, active validation, scoped formal results and retry uniqueness. PostgreSQL functions/triggers preserve governed rule/test/scheme and formal result/hit immutability.

Frozen 0002 uses live Base.metadata: on a fresh database some new ORM columns already exist. 0008 inspects matching type/nullability/FKs and adds only absent columns. Tests archive the exact verified baseline, migrate a separate empty database using that archived code to real 0007, verify its old schema, then use current code to 0008. Another empty database migrates current code directly to head. Canonical domain columns/types/vector dimensions, PKs/FKs/checks/indexes/triggers/function definitions are compared and equal. Both paths then downgrade to 0007 and re-upgrade with equivalent schemas.

Defined downgrade refuses to remove any Phase 1H contract/scheme/formal authoritative data until archive/export; the rejection preserves data and revision. Empty downgrade removes Phase 1H additions only. Test DBs have unique generated names and are cleaned after the measured test.

Phase 1B–1G regression now uses shared `migration_lineage.revision_at_or_after` over ScriptDirectory's actual graph. Exact known revisions and valid descendants pass; aliases/prefixes/unknown strings/earlier/sibling revisions and parallel heads fail. Existing schema assertions remain intact. Fourteen helper tests include real repository ancestry and temporary divergent/merged graphs. No historical migration is edited and no arbitrary future revision string is accepted.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.


# Phase1I — migration0009

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

Exclusive owner: Phase1I. Head: 0009_phase1i, down_revision0008_phase1h. Migrations0001–0008 are byte-identical to the verified baseline. Explicit frozen DDL creates only regulation_applicability_results, canonical foreign keys, subject/status constraints, retry uniqueness and tenant/snapshot indexes. It adds configuration-definition/version, result and I-pin immutability triggers; unrelated metadata behavior is preserved.

Dual-path test archives EXACT700951ebb9ebdf33e399158fd3fb53bb4a6c87e7 and verifies its real Alembic head0008. Separate disposable empty PostgreSQL databases run fresh→head and archived0008→0009. Resulting entire public domain schemas compare equal: columns/nullability/defaults/PK/FK/checks/unique indexes, pgvector catalog types, exact index definitions, trigger definitions and I function definitions. Both databases test empty0009→0008→0009 round trips. Retained authoritative I configuration/results/pins refuse downgrade with archive/export instruction; the starting head and retained data remain unchanged.

Historical Phase1H downgrade test now records the actual starting head and asserts transactional refusal retains it. It preserves all original retained-rule assertions; no legacy migration or Phase1H business logic changed. Phase1B–H schema gates continue using the existing tested Alembic revision-graph lineage helper, rejecting unrelated/unknown revisions.

Evidence: tests/test_phase1i_migrations.py and phase1i_migration_dual_path.json in final local/CI evidence. Full suite additionally runs the historical0007→head path.

Phase1I final measured dual-path migration gate: **PASS** at code SHA131d101cdd02999aa478c1a730f492c1729caf30. All five boolean checks (fresh, verified0008 upgrade, schema equivalence, empty downgrade roundtrip, retained-data refusal) are true in [phase1i_migration_dual_path.json](evidence/phase1i/local/phase1i_migration_dual_path.json).
