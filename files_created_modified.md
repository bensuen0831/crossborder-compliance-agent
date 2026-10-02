# Phase 1F Files Created / Modified

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation**.

Tested SHA: `1784f10409012918aae709e2a5dc492edbe272e2`. Run ID: `36968764193`. Attempt: `1`.
Final evidence Source of Truth: [phase1f_final_remote.json](evidence/phase1f_final_remote.json).
Artifact ID: `11210258936`. Artifact digest: `sha256:5fe9dcefcdd266127b5fa081bfb5f31c53dc5c33d57bbff5385d11c1ca5d07bc`.

| Empirical assertion | Actual result |
|---|---|
| Full PostgreSQL/runtime pytest | **137 passed / 0 skipped / 0 deselected** |
| Alembic head | **0006_phase1f** |
| Phase 1F schema | **29/29 PASS** |
| Architecture executable checks | **77/77 PASS** |
| Phase 1A runtime/checkpoint/restart/resume/retry | **25/25 PASS** |
| Phase 1B / 1C / 1D / 1E schema regression | **16/16; 20/20; 15/15; 22/22 PASS** |
| Phase 1A–1E full regression | **PASS** |

Above values are independently verified through GitHub Checks measured evidence for the identified CI run; they do not reuse Phase 1E totals. The local full gate at `5acbcd1813cb80a2bd3d0f92d04dc68f5d4fc3db` is separate corroborating evidence. The linked remote manifest pins the immutable pre-issuance baseline. Later governance commits contain documentation/evidence only and retain the tested implementation.

Known exclusions: Phase 1G retrieval/ranking/reranking/RAG/answer generation, classification, regulation applicability, country rules, risk and compliance paths are excluded. Ingestion currently supports approved canonical structure JSON upload or controlled HTTPS JSON sources; automatic legal PDF/DOCX import, external site crawling, actual model-provider execution and affected-project impact calculation are excluded. Storage/embedding tests use explicit adapters; PostgreSQL and Redis are real. Whitespace token counting is a deterministic foundation measure, not provider tokenizer equivalence. Local PostgreSQL 17.11/Redis 8.0.2 are separately identified from CI PostgreSQL 16/Redis 7.

Authoritative boundary: PostgreSQL canonical knowledge tables; Phase 1C source definitions/collections/bindings and model metadata are reused; Phase 1B RegulatoryStructureNode/EvidenceReference/Citation and durable admin review are reused. Object storage retains original artifacts. Registry, FTS and pgvector are derived projections/indexes. Formal Phase 1E context is the only context input.

Actual Phase 1F files relative to integrated main, including delivery evidence. Generated caches/egg-info, local service data and credentials are excluded. Phase 1E business implementation is unchanged.

| Status | File |
|---|---|
| A | `Phase1G_entry_decision.md` |
| M | `.github/workflows/phase1a-runtime-smoke.yml` |
| A | `.gitignore` |
| M | `ARCHITECTURE_RULES.md` |
| M | `Phase1F_entry_decision.md` |
| A | `Phase1F_knowledge_scope_design.md` |
| A | `alembic/versions/0006_phase1f_knowledge_scope.py` |
| M | `architecture_rule_check.md` |
| A | `evidence/phase1f-main-start-gate/evidence_sha256.json` |
| A | `evidence/phase1f-main-start-gate/local-regression/architecture_rule_check.json` |
| A | `evidence/phase1f-main-start-gate/local-regression/ci_complete.log` |
| A | `evidence/phase1f-main-start-gate/local-regression/phase1b_schema_check.json` |
| A | `evidence/phase1f-main-start-gate/local-regression/phase1c_schema_check.json` |
| A | `evidence/phase1f-main-start-gate/local-regression/phase1d_schema_check.json` |
| A | `evidence/phase1f-main-start-gate/local-regression/phase1e_schema_check.json` |
| A | `evidence/phase1f-main-start-gate/local-regression/pytest_full.log` |
| A | `evidence/phase1f-main-start-gate/local-regression/runtime_verify.json` |
| A | `evidence/phase1f-main-start-gate/main_start_gate_manifest.json` |
| A | `evidence/phase1f/local_final_gate/architecture_rule_check.json` |
| A | `evidence/phase1f/local_final_gate/ci_complete.log` |
| A | `evidence/phase1f/local_final_gate/ci_run_evidence.json` |
| A | `evidence/phase1f/local_final_gate/evidence_file_manifest.json` |
| A | `evidence/phase1f/local_final_gate/migration_roundtrip_result.json` |
| A | `evidence/phase1f/local_final_gate/phase1f_empirical_summary.json` |
| A | `evidence/phase1f/local_final_gate/phase1f_schema_check.json` |
| A | `evidence/phase1f/local_final_gate/pytest_full.xml` |
| A | `evidence/phase1f/local_final_gate/pytest_full_summary.json` |
| A | `evidence/phase1f/local_final_gate/runtime_verify.json` |
| A | `evidence/phase1f/run_36968097285/annotations.json` |
| A | `evidence/phase1f/run_36968097285/artifacts.json` |
| A | `evidence/phase1f/run_36968097285/empirical_summary.json` |
| A | `evidence/phase1f/run_36968097285/jobs.json` |
| A | `evidence/phase1f/run_36968097285/run.json` |
| A | `evidence/phase1f_final_remote.json` |
| A | `evidence_citation_result.md` |
| M | `files_created_modified.md` |
| A | `index_foundation_result.md` |
| A | `knowledge_api_result.md` |
| A | `knowledge_chunk_binding_result.md` |
| A | `knowledge_domain_result.md` |
| A | `knowledge_ingestion_result.md` |
| A | `knowledge_quality_governance_result.md` |
| A | `knowledge_scope_resolver_result.md` |
| M | `migration_result.md` |
| M | `phase1f_preflight_status.md` |
| A | `product_scope_isolation_result.md` |
| A | `regulatory_structure_result.md` |
| M | `scripts/architecture_rule_check.py` |
| A | `scripts/knowledge_ingestion_worker.py` |
| M | `scripts/phase1b_schema_check.py` |
| M | `scripts/phase1c_schema_check.py` |
| M | `scripts/phase1d_schema_check.py` |
| M | `scripts/phase1e_schema_check.py` |
| A | `scripts/phase1f_empirical_summary.py` |
| A | `scripts/phase1f_schema_check.py` |
| A | `scripts/verify_full_pytest.py` |
| M | `smoke/ci_run_evidence.py` |
| M | `smoke/postgres_schema_evidence.py` |
| M | `smoke/run_gate.sh` |
| A | `src/crossborder_compliance/application/knowledge_ports.py` |
| A | `src/crossborder_compliance/application/knowledge_services.py` |
| A | `src/crossborder_compliance/domain/knowledge.py` |
| A | `src/crossborder_compliance/infrastructure/knowledge_download.py` |
| A | `src/crossborder_compliance/infrastructure/knowledge_worker.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/knowledge_models.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/knowledge_repositories.py` |
| M | `src/crossborder_compliance/infrastructure/persistence/metadata_models.py` |
| M | `src/crossborder_compliance/infrastructure/persistence/metadata_repositories.py` |
| A | `src/crossborder_compliance/interfaces/api/knowledge_schemas.py` |
| M | `src/crossborder_compliance/interfaces/api/main.py` |
| A | `src/crossborder_compliance/interfaces/api/routes/knowledge.py` |
| M | `test_result.md` |
| A | `tests/test_phase1f_download_chunking.py` |
| A | `tests/test_phase1f_postgres.py` |
| A | `translation_provenance_result.md` |
| A | `evidence/phase1f/run_36968764193/annotations.json` |
| A | `evidence/phase1f/run_36968764193/artifacts.json` |
| A | `evidence/phase1f/run_36968764193/empirical_summary.json` |
| A | `evidence/phase1f/run_36968764193/jobs.json` |
| A | `evidence/phase1f/run_36968764193/run.json` |

PASS assertions: source/migration/tests/gates/routes are traceable to actual Git diff; existing source tables and gates reused. files_created_modified.md lists itself as a delivery update. Final governance file is generated only after successful final empirical CI.
