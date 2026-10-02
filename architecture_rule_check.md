# Phase 1F Architecture Rule Check

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation**.

Tested SHA: `7391b9728e788b70e11885fe23d64980dcc3db37`. Run ID: `36973990791`. Attempt: `1`.
Final evidence Source of Truth: [phase1f_final_remote.json](evidence/phase1f_final_remote.json).
Artifact ID: `11212349170`. Artifact digest: `sha256:b31ac0fe52e103fa291e2c5f1356bee52a47ffd0fa0fc3b4f9774534cf43b47d`.

| Empirical assertion | Actual result |
|---|---|
| Full PostgreSQL/runtime pytest | **142 passed / 0 skipped / 0 deselected** |
| Alembic head | **0006_phase1f** |
| Phase 1F schema | **29/29 PASS** |
| Architecture executable checks | **77/77 PASS** |
| Phase 1A runtime/checkpoint/restart/resume/retry | **25/25 PASS** |
| Phase 1B / 1C / 1D / 1E schema regression | **16/16; 20/20; 15/15; 22/22 PASS** |
| Phase 1A–1E full regression | **PASS** |

Above values are independently verified through GitHub Checks measured evidence for the identified CI run; they do not reuse Phase 1E totals. The local full gate at `4e7d0d9759c42b2da91a23dea47f2cdea0243449` is separate corroborating evidence. The linked remote manifest pins the immutable pre-issuance baseline. Later governance commits contain documentation/evidence only and retain the tested implementation.

Known exclusions: Phase 1G retrieval/ranking/reranking/RAG/answer generation, classification, regulation applicability, country rules, risk and compliance paths are excluded. Ingestion currently supports approved canonical structure JSON upload or controlled HTTPS JSON sources; automatic legal PDF/DOCX import, external site crawling, actual model-provider execution and affected-project impact calculation are excluded. Storage/embedding tests use explicit adapters; PostgreSQL and Redis are real. Whitespace token counting is a deterministic foundation measure, not provider tokenizer equivalence. Local PostgreSQL 17.11/Redis 8.0.2 are separately identified from CI PostgreSQL 16/Redis 7.

Authoritative boundary: PostgreSQL canonical knowledge tables; Phase 1C source definitions/collections/bindings and model metadata are reused; Phase 1B RegulatoryStructureNode/EvidenceReference/Citation and durable admin review are reused. Object storage retains original artifacts. Registry, FTS and pgvector are derived projections/indexes. Formal Phase 1E context is the only context input.

**77/77 PASS**. Existing 59 checks remain; 18 Phase 1F boundaries are added. Rules 104–114 are recorded after Rule 103. Static checks inspect domain/application/model/migration/API/runtime source; PostgreSQL tests separately demonstrate behavior.

| # | Executable assertion | Result |
|---|---|---|
| 1 | `domain_has_no_langgraph_import` | PASS |
| 2 | `domain_has_no_sqlalchemy_import` | PASS |
| 3 | `application_has_no_sqlalchemy_import` | PASS |
| 4 | `langgraph_runtime_isolated_to_adapter` | PASS |
| 5 | `no_eval_exec` | PASS |
| 6 | `human_review_node_not_agent` | PASS |
| 7 | `classification_results_is_only_formal_classification_source` | PASS |
| 8 | `workflow_stage_view_not_persisted` | PASS |
| 9 | `regulatory_structure_node_is_canonical_persistence` | PASS |
| 10 | `stage1_explicit_cross_border_results` | PASS |
| 11 | `legal_basis_rulehit_many_to_many_contract` | PASS |
| 12 | `legal_basis_rulehit_many_to_many_persistence` | PASS |
| 13 | `domain_migration_does_not_own_checkpointer_schema` | PASS |
| 14 | `api_workflow_idempotency_separated` | PASS |
| 15 | `workflow_state_has_no_runtime_services_or_secrets` | PASS |
| 16 | `durable_postgres_checkpointer_setup_present` | PASS |
| 17 | `thread_id_backend_bound_to_workflow_run_id` | PASS |
| 18 | `conversation_thread_not_langgraph_thread_id` | PASS |
| 19 | `interrupt_pre_side_effect_event_idempotent` | PASS |
| 20 | `raw_langgraph_event_not_external_contract` | PASS |
| 21 | `api_routes_do_not_return_or_import_orm_models` | PASS |
| 22 | `domain_repositories_are_automatically_tenant_scoped` | PASS |
| 23 | `no_second_classification_repository` | PASS |
| 24 | `no_country_product_regulation_fixed_business_logic` | PASS |
| 25 | `frontend_has_no_business_metadata_enum` | PASS |
| 26 | `agent_skill_has_no_model_name_or_base_url` | PASS |
| 27 | `prompt_business_content_not_embedded_in_agent` | PASS |
| 28 | `registry_not_source_of_truth` | PASS |
| 29 | `admin_draft_not_runtime_visible` | PASS |
| 30 | `model_secret_not_persisted_in_metadata` | PASS |
| 31 | `snapshot_not_dynamic_registry_lookup_on_resume` | PASS |
| 32 | `registry_publish_uses_transactional_outbox` | PASS |
| 33 | `no_country_specific_registry_branch` | PASS |
| 34 | `graph_state_has_no_document_binary` | PASS |
| 35 | `canonical_document_not_llm_narrative` | PASS |
| 36 | `candidate_vision_has_no_legal_result` | PASS |
| 37 | `extracted_result_has_source_trace` | PASS |
| 38 | `spreadsheet_preserves_row_column_provenance` | PASS |
| 39 | `formal_counts_not_llm` | PASS |
| 40 | `parse_run_is_versioned` | PASS |
| 41 | `snapshot_can_pin_parse_run` | PASS |
| 42 | `parser_provider_is_adapter_only` | PASS |
| 43 | `phase1d_has_no_country_product_regulation_logic` | PASS |
| 44 | `candidate_not_formal_compliance_input` | PASS |
| 45 | `product_context_is_registry_driven` | PASS |
| 46 | `no_product_search_all_scope` | PASS |
| 47 | `product_conflict_is_explicit` | PASS |
| 48 | `business_fact_conflict_is_explicit` | PASS |
| 49 | `possible_duplicate_requires_review_conflict` | PASS |
| 50 | `unresolved_party_requires_review_conflict` | PASS |
| 51 | `data_item_source_trace_required` | PASS |
| 52 | `formal_counts_are_separate` | PASS |
| 53 | `no_parallel_data_item_source_of_truth` | PASS |
| 54 | `no_parallel_data_flow_source_of_truth` | PASS |
| 55 | `data_flow_is_structured` | PASS |
| 56 | `jurisdiction_not_regulation_decision` | PASS |
| 57 | `semantic_resolution_candidate_only` | PASS |
| 58 | `context_snapshot_versioned` | PASS |
| 59 | `no_country_product_rule_logic` | PASS |
| 60 | `knowledge_platform_not_vector_db` | PASS |
| 61 | `scope_resolver_has_no_retrieval` | PASS |
| 62 | `hard_filter_precedes_similarity` | PASS |
| 63 | `unrelated_product_knowledge_excluded` | PASS |
| 64 | `unresolved_product_scope_fail_safe` | PASS |
| 65 | `knowledge_chunk_has_provenance` | PASS |
| 66 | `vector_index_is_derived` | PASS |
| 67 | `fts_index_is_derived` | PASS |
| 68 | `registry_not_knowledge_source` | PASS |
| 69 | `translation_review_boundary` | PASS |
| 70 | `knowledge_quality_before_active` | PASS |
| 71 | `snapshot_pins_knowledge_version` | PASS |
| 72 | `phase1f_uses_phase1e_context` | PASS |
| 73 | `no_country_specific_knowledge_branch` | PASS |
| 74 | `no_regulation_business_decision` | PASS |
| 75 | `controlled_downloader_boundary` | PASS |
| 76 | `knowledge_ingestion_no_graph_checkpoints` | PASS |
| 77 | `no_parallel_knowledge_source` | PASS |

No retrieval/ranking in ScopeResolver; hard filters and minimal product context precede future similarity; canonical PostgreSQL knowledge remains authoritative; chunks retain provenance; quality/review precede ACTIVE; original/translation separation; snapshot pins; Phase 1E-only context; no country/product/regulation business branch; controlled downloading; no graph-checkpoint ingestion; no parallel knowledge store.
