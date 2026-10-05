# Phase 1K-A actual created/modified files

Phase: **Track B — Phase 1K-A foundation**, not full Phase 1K production integration.
Base: `f563e5067308e7eab6d3f89321b8b30da7c39044`; tag `v3.6-phase1g-pass`.
Tested implementation source SHA: `256b74df044870487d668764ffc0aa704806224e`; Run **37019990110**, Number **110**, Attempt **1**, **SUCCESS**.
Runner merge SHA: `64be7b05cf38aa8a8446dda95e0ed8402ee471aa`. Artifact **11231744443**, digest `sha256:e5390bf776f66cf50dc207c550dedad1f9f37cb6a3439c0fa54755c26f140c34`.
Full remote gate log: `ci_complete.log`, 74540 bytes, SHA-256 `131e01c87043cc4b3f4769c4fbcaff278815e5207309bfd2b12dd5178b8ab09f`.

Actual full PostgreSQL/runtime pytest: **276 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**. Local JUnit identifies **76 Track B tests** (64 non-PostgreSQL + 12 PostgreSQL) and all **200 frozen baseline tests**. The remote total is verified through official measured Check annotations; no remote JUnit ZIP download is claimed. The frozen test hashes plus full no-deselect gate preserve the same test set remotely.
Alembic remains **0007_phase1g**; **no migration**. Existing schema gates B/C/D/E/F/G: **16/16 / 20/20 / 15/15 / 22/22 / 29/29 / 58/58 PASS**. Frozen architecture checks **108/108**, additional Track B boundaries **20/20** (executed by full pytest), runtime/checkpoint ownership **25/25 PASS**. Phase 1A–1G regressions **PASS**.

Source of Truth: existing PostgreSQL Phase 1C model/provider/deployment/capability/health metadata, generic governed metadata versions, Prompt versions and AnalysisSnapshot registry pins. Registries remain projections; no duplicate authoritative store, publish mechanism, knowledge, parser, retrieval or workflow was introduced.

Known exclusions: full Phase 1K/1L compliance workflow, legal rules, formal classification/applicability/risk/path decisions, production agents, every provider SDK, multimodal binary ingestion, automatic health monitoring, production secret-vault/resource-source/audit/detection wiring, reversible mapping storage and next-phase development. Production callers must inject trusted scoped resource loading, approved detection when required, protected secret resolution and an available event audit sink; absent/failing mandatory dependencies block invocation. Tests inject deterministic adapters; PostgreSQL/Redis/pgvector remain real. No paid provider is required for CI.

Evidence: [implementation identity](evidence/phase1k-a/implementation-ci/verified_identity.json), [measured full gate](evidence/phase1k-a/implementation-ci/empirical_summary.json), [local full log](evidence/phase1k-a/local-final/ci_complete.log), [local JUnit](evidence/phase1k-a/local-final/pytest_full.xml), [Track B boundary results](evidence/phase1k-a/local-final/phase1k_a_boundary_check.json), [frozen hashes](evidence/phase1k-a/frozen_baseline_manifest.json).
The unchanged Phase 1G CI workflow/summary script is reused: its historical `phase: 1G` label identifies the gate script, while its pytest total includes the new Track B suite. These documents explicitly distinguish frozen Phase 1G 200-test baseline from the new 276-test foundation result. The later documentation-only publication head has its own final CI, recorded in the final PR description/receipt, never attributed to this earlier implementation SHA.

Complete actual baseline-relative implementation + delivery closure diff (including this ledger and delivery_manifest.json):

```text
A	Phase1K_A_llm_gateway_foundation_design.md
A	architecture_boundary_check.md
A	data_redaction_result.md
A	evidence/phase1k-a/delivery_manifest.json
A	evidence/phase1k-a/early_checkpoint_process_check.json
A	evidence/phase1k-a/early_checkpoint_remote_receipt.json
A	evidence/phase1k-a/frozen_baseline_manifest.json
A	evidence/phase1k-a/implementation-ci/annotations.json
A	evidence/phase1k-a/implementation-ci/artifacts.json
A	evidence/phase1k-a/implementation-ci/empirical_summary.json
A	evidence/phase1k-a/implementation-ci/jobs.json
A	evidence/phase1k-a/implementation-ci/run.json
A	evidence/phase1k-a/implementation-ci/verified_identity.json
A	evidence/phase1k-a/local-final/alembic_upgrade.log
A	evidence/phase1k-a/local-final/architecture_rule_check.json
A	evidence/phase1k-a/local-final/architecture_rule_check.md
A	evidence/phase1k-a/local-final/architecture_rule_check_stdout.json
A	evidence/phase1k-a/local-final/ci_complete.log
A	evidence/phase1k-a/local-final/ci_run_evidence.json
A	evidence/phase1k-a/local-final/ci_run_evidence.md
A	evidence/phase1k-a/local-final/database_schema_result.md
A	evidence/phase1k-a/local-final/evidence_file_manifest.json
A	evidence/phase1k-a/local-final/phase1b_schema_check.json
A	evidence/phase1k-a/local-final/phase1c_database_schema_result.md
A	evidence/phase1k-a/local-final/phase1c_schema_check.json
A	evidence/phase1k-a/local-final/phase1c_security_result.md
A	evidence/phase1k-a/local-final/phase1d_database_schema_result.md
A	evidence/phase1k-a/local-final/phase1d_schema_check.json
A	evidence/phase1k-a/local-final/phase1e_database_schema_result.md
A	evidence/phase1k-a/local-final/phase1e_schema_check.json
A	evidence/phase1k-a/local-final/phase1f_schema_check.json
A	evidence/phase1k-a/local-final/phase1g_empirical_summary.json
A	evidence/phase1k-a/local-final/phase1g_schema_check.json
A	evidence/phase1k-a/local-final/phase1k_a_boundary_check.json
A	evidence/phase1k-a/local-final/post_alembic_schema.json
A	evidence/phase1k-a/local-final/post_runtime_schema.json
A	evidence/phase1k-a/local-final/postgres_schema_evidence.md
A	evidence/phase1k-a/local-final/postgres_schema_state.json
A	evidence/phase1k-a/local-final/preflight.json
A	evidence/phase1k-a/local-final/process1.log
A	evidence/phase1k-a/local-final/process2.log
A	evidence/phase1k-a/local-final/process3_resume_retry.log
A	evidence/phase1k-a/local-final/pytest_full.log
A	evidence/phase1k-a/local-final/pytest_full.xml
A	evidence/phase1k-a/local-final/pytest_full_summary.json
A	evidence/phase1k-a/local-final/runtime_assertions.json
A	evidence/phase1k-a/local-final/runtime_event_evidence.md
A	evidence/phase1k-a/local-final/runtime_smoke_result.md
A	evidence/phase1k-a/local-final/runtime_verify.json
A	evidence/phase1k-a/local-final/runtime_versions.md
A	evidence/phase1k-a/local-final/source_of_truth_check.md
A	evidence/phase1k-a/local-final/test_result.md
A	evidence/phase1k-a/prior-phase1g-docs/files_created_modified.md
A	evidence/phase1k-a/prior-phase1g-docs/test_result.md
M	files_created_modified.md
A	integration_handoff.md
A	llm_service_contract_result.md
A	model_router_result.md
A	model_usage_policy_result.md
A	phase1k_a_parallel_checkpoint.json
A	phase1k_a_parallel_checkpoint.md
A	phase1k_a_start_gate.md
A	provider_adapter_result.md
M	pyproject.toml
A	scripts/phase1k_a_boundary_check.py
A	security_boundary_result.md
A	src/crossborder_compliance/application/llm_gateway_policy.py
A	src/crossborder_compliance/application/llm_gateway_ports.py
A	src/crossborder_compliance/application/llm_gateway_redaction.py
A	src/crossborder_compliance/application/llm_gateway_services.py
A	src/crossborder_compliance/domain/llm_gateway.py
A	src/crossborder_compliance/infrastructure/llm_gateway_configuration.py
A	src/crossborder_compliance/infrastructure/llm_gateway_http.py
M	test_result.md
A	tests/phase1k_a_fixtures.py
A	tests/test_phase1k_a_architecture.py
A	tests/test_phase1k_a_configuration_postgres.py
A	tests/test_phase1k_a_gateway.py
A	tests/test_phase1k_a_http_redaction.py
```

Shared files: pyproject.toml (existing httpx promoted to runtime; jsonschema added), and explicitly requested test_result.md / files_created_modified.md. Prior Phase 1G generic documents are retained in evidence/phase1k-a/prior-phase1g-docs. All other Track B files are additive. No API route/ORM table/migration/other-track code changed. Existing 148 frozen implementation files and all 0001–0007 migrations pass hash checks.
