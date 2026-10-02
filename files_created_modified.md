# Phase 1G actual files created / modified

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

## Actual implementation / preserved preflight changes

The following is the actual main→implementation tested-head diff. Historical preflight evidence is explicitly in `evidence/phase1g-start-gate/`; it is not relabelled as Phase 1G implementation evidence.

| Change | Actual path |
|---|---|
| M | `.github/workflows/phase1a-runtime-smoke.yml` |
| M | `ARCHITECTURE_RULES.md` |
| A | `alembic/versions/0007_phase1g_retrieval_evidence.py` |
| A | `evidence/phase1g-start-gate/evidence_sha256.json` |
| A | `evidence/phase1g-start-gate/main_ancestry.json` |
| A | `evidence/phase1g-start-gate/main_final.json` |
| A | `evidence/phase1g-start-gate/main_gate_manifest.json` |
| A | `evidence/phase1g-start-gate/main_local/alembic_upgrade.log` |
| A | `evidence/phase1g-start-gate/main_local/architecture_rule_check.json` |
| A | `evidence/phase1g-start-gate/main_local/architecture_rule_check.md` |
| A | `evidence/phase1g-start-gate/main_local/architecture_rule_check_stdout.json` |
| A | `evidence/phase1g-start-gate/main_local/ci_complete.log` |
| A | `evidence/phase1g-start-gate/main_local/ci_run_evidence.json` |
| A | `evidence/phase1g-start-gate/main_local/ci_run_evidence.md` |
| A | `evidence/phase1g-start-gate/main_local/database_schema_result.md` |
| A | `evidence/phase1g-start-gate/main_local/evidence_file_manifest.json` |
| A | `evidence/phase1g-start-gate/main_local/phase1b_schema_check.json` |
| A | `evidence/phase1g-start-gate/main_local/phase1c_database_schema_result.md` |
| A | `evidence/phase1g-start-gate/main_local/phase1c_schema_check.json` |
| A | `evidence/phase1g-start-gate/main_local/phase1c_security_result.md` |
| A | `evidence/phase1g-start-gate/main_local/phase1d_database_schema_result.md` |
| A | `evidence/phase1g-start-gate/main_local/phase1d_schema_check.json` |
| A | `evidence/phase1g-start-gate/main_local/phase1e_database_schema_result.md` |
| A | `evidence/phase1g-start-gate/main_local/phase1e_schema_check.json` |
| A | `evidence/phase1g-start-gate/main_local/phase1f_empirical_summary.json` |
| A | `evidence/phase1g-start-gate/main_local/phase1f_schema_check.json` |
| A | `evidence/phase1g-start-gate/main_local/post_alembic_schema.json` |
| A | `evidence/phase1g-start-gate/main_local/post_runtime_schema.json` |
| A | `evidence/phase1g-start-gate/main_local/postgres_schema_evidence.md` |
| A | `evidence/phase1g-start-gate/main_local/postgres_schema_state.json` |
| A | `evidence/phase1g-start-gate/main_local/preflight.json` |
| A | `evidence/phase1g-start-gate/main_local/process1.log` |
| A | `evidence/phase1g-start-gate/main_local/process2.log` |
| A | `evidence/phase1g-start-gate/main_local/process3_resume_retry.log` |
| A | `evidence/phase1g-start-gate/main_local/pytest_full.log` |
| A | `evidence/phase1g-start-gate/main_local/pytest_full.xml` |
| A | `evidence/phase1g-start-gate/main_local/pytest_full_summary.json` |
| A | `evidence/phase1g-start-gate/main_local/runtime_assertions.json` |
| A | `evidence/phase1g-start-gate/main_local/runtime_event_evidence.md` |
| A | `evidence/phase1g-start-gate/main_local/runtime_smoke_result.md` |
| A | `evidence/phase1g-start-gate/main_local/runtime_verify.json` |
| A | `evidence/phase1g-start-gate/main_local/runtime_versions.md` |
| A | `evidence/phase1g-start-gate/main_local/source_of_truth_check.md` |
| A | `evidence/phase1g-start-gate/main_local/test_result.md` |
| A | `evidence/phase1g-start-gate/main_remote/annotations.json` |
| A | `evidence/phase1g-start-gate/main_remote/artifacts.json` |
| A | `evidence/phase1g-start-gate/main_remote/empirical_summary.json` |
| A | `evidence/phase1g-start-gate/main_remote/jobs.json` |
| A | `evidence/phase1g-start-gate/main_remote/run.json` |
| A | `evidence/phase1g-start-gate/mark_ready_result.json` |
| A | `evidence/phase1g-start-gate/merge_result.json` |
| A | `evidence/phase1g-start-gate/pr9_checks.json` |
| A | `evidence/phase1g-start-gate/pr9_merged.json` |
| A | `evidence/phase1g-start-gate/pr9_ready.json` |
| A | `evidence/phase1g-start-gate/pr9_review_result.json` |
| A | `evidence/phase1g-start-gate/pr9_run.json` |
| A | `evidence/phase1g-start-gate/release_branch_result.json` |
| A | `phase1g_preflight_status.md` |
| M | `scripts/architecture_rule_check.py` |
| M | `scripts/phase1b_schema_check.py` |
| M | `scripts/phase1c_schema_check.py` |
| M | `scripts/phase1d_schema_check.py` |
| M | `scripts/phase1e_schema_check.py` |
| M | `scripts/phase1f_schema_check.py` |
| A | `scripts/phase1g_empirical_summary.py` |
| A | `scripts/phase1g_schema_check.py` |
| M | `scripts/verify_full_pytest.py` |
| M | `smoke/postgres_schema_evidence.py` |
| M | `smoke/run_gate.sh` |
| A | `src/crossborder_compliance/application/external_evidence_services.py` |
| A | `src/crossborder_compliance/application/knowledge_runtime_services.py` |
| M | `src/crossborder_compliance/application/metadata_services.py` |
| A | `src/crossborder_compliance/application/retrieval_algorithms.py` |
| A | `src/crossborder_compliance/application/retrieval_ports.py` |
| A | `src/crossborder_compliance/application/retrieval_services.py` |
| A | `src/crossborder_compliance/domain/retrieval.py` |
| M | `src/crossborder_compliance/infrastructure/knowledge_download.py` |
| A | `src/crossborder_compliance/infrastructure/knowledge_publication_worker.py` |
| M | `src/crossborder_compliance/infrastructure/persistence/knowledge_repositories.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/knowledge_runtime_repository.py` |
| M | `src/crossborder_compliance/infrastructure/persistence/metadata_models.py` |
| M | `src/crossborder_compliance/infrastructure/persistence/metadata_repositories.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/retrieval_models.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/retrieval_navigation.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/retrieval_repositories.py` |
| A | `src/crossborder_compliance/infrastructure/retrieval_external.py` |
| A | `src/crossborder_compliance/infrastructure/retrieval_search.py` |
| A | `src/crossborder_compliance/infrastructure/retrieval_test_adapters.py` |
| M | `src/crossborder_compliance/interfaces/api/main.py` |
| A | `src/crossborder_compliance/interfaces/api/retrieval_schemas.py` |
| A | `src/crossborder_compliance/interfaces/api/routes/retrieval.py` |
| A | `tests/phase1g_fixtures.py` |
| A | `tests/test_phase1g_algorithms.py` |
| A | `tests/test_phase1g_api_postgres.py` |
| A | `tests/test_phase1g_external_postgres.py` |
| A | `tests/test_phase1g_isolation_postgres.py` |
| A | `tests/test_phase1g_navigation_postgres.py` |
| A | `tests/test_phase1g_persistence_postgres.py` |
| A | `tests/test_phase1g_publication_postgres.py` |
| A | `tests/test_phase1g_search_postgres.py` |

## Why existing foundation files changed

- Phase 1F Publish repository: adds atomic publication outbox/PENDING state only; review/lifecycle semantics remain intact.
- Phase 1C RegistrySyncService/repository: additive versioned consumer hook and publication routing so general metadata sync cannot acknowledge publication without materialization. Existing registry/outbox remain unique.
- Existing controlled downloader: adds final canonical URL to its audit, preserving its security rules.
- Metadata model import: registers additive Phase 1G derived tables.
- FastAPI main: registers routes and starts/stops the automatic background publication worker.
- Existing schema/mandatory gate scripts: accept descendant 0007 without removing B–F assertions; add Phase 1G coverage and measured CI evidence.

Migrations 0001–0006 and Phase 1A–1F tests are unchanged. New test helpers simulate the live automatic publication worker using explicit test embedding adapters.

## Documentation-only closure

This delivery changes only the 17 result documents and `evidence/phase1g/` copies/manifests. The implementation tested head remains separately recorded above. Git diff confirmation and the subsequent closure tested head/run/artifact are recorded in the final entry decision after full CI. No Phase 1H code, new branch or main merge is part of this work.

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.


---

# Phase 1H implementation inventory

Verified base `f563e5067308e7eab6d3f89321b8b30da7c39044`; implementation `1de60800efa7dc2e9f7092842e0044899eb74690`.

```text
M	.github/workflows/phase1a-runtime-smoke.yml
M	ARCHITECTURE_RULES.md
A	alembic/versions/0008_phase1h_rule_classification.py
M	scripts/architecture_rule_check.py
M	scripts/phase1b_schema_check.py
M	scripts/phase1c_schema_check.py
M	scripts/phase1d_schema_check.py
M	scripts/phase1e_schema_check.py
M	scripts/phase1f_schema_check.py
M	scripts/phase1g_schema_check.py
A	scripts/phase1h_schema_check.py
M	scripts/verify_full_pytest.py
M	smoke/postgres_schema_evidence.py
M	smoke/run_gate.sh
A	src/crossborder_compliance/application/classification_services.py
A	src/crossborder_compliance/domain/classification.py
A	src/crossborder_compliance/domain/rule_ast.py
A	src/crossborder_compliance/domain/rules.py
A	src/crossborder_compliance/infrastructure/classification_evidence.py
A	src/crossborder_compliance/infrastructure/persistence/classification_governance.py
A	src/crossborder_compliance/infrastructure/persistence/classification_repository.py
M	src/crossborder_compliance/infrastructure/persistence/config_admin_repositories.py
M	src/crossborder_compliance/infrastructure/persistence/metadata_models.py
M	src/crossborder_compliance/infrastructure/persistence/metadata_repositories.py
A	src/crossborder_compliance/infrastructure/persistence/migration_lineage.py
M	src/crossborder_compliance/infrastructure/persistence/models.py
A	src/crossborder_compliance/infrastructure/persistence/rule_admin_repository.py
A	src/crossborder_compliance/infrastructure/persistence/rule_governance.py
M	src/crossborder_compliance/infrastructure/persistence/special_admin_repositories.py
M	src/crossborder_compliance/interfaces/api/main.py
A	src/crossborder_compliance/interfaces/api/routes/classification.py
A	tests/phase1h_fixtures.py
A	tests/test_phase1h_api.py
A	tests/test_phase1h_ast.py
A	tests/test_phase1h_evidence_postgres.py
A	tests/test_phase1h_migration_lineage.py
A	tests/test_phase1h_migrations.py
A	tests/test_phase1h_postgres.py
A	tests/test_phase1h_rules.py
```

Delivery additionally creates the eight Phase 1H design/component documents, `Phase1H_delivery_handoff.md` and `evidence/phase1h/`; appends Phase 1H sections to shared migration/test/architecture/inventory documents. `Phase1I_entry_decision.md` is issued only after verified closure CI.

Shared surfaces explicitly authorized for Track A: models/metadata models, rule/classification admin repositories, rule registry projection, API router registration, schema/architecture/full-test/runtime gates and CI checkout history. Integrators must review overlaps with other tracks; no other working tree is modified. No frontend, Phase1I+ business code or dependencies are added.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
