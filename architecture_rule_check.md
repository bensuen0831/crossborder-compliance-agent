# Phase 1G architecture rule check

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

## Rules and executable results

Existing Rules 1–114 are retained. Phase 1G adds **115–132**, plus **133** for normal publication automatically reaching runtime assets without human Sync/Reindex. Phase 1A–1F executable checks remain 77/77, with 31 new Phase 1G/addendum checks for a measured **108/108 PASS**.

The checker inspects actual imports/AST call order, SQL materialized filtering, contract/model constraints, source/policy pins, external validation, fallback and review/READY/outbox integration. Mandatory PostgreSQL tests complement static checks with behavior rather than substituting marker text for runtime verification.

| # | Check | Result |
|---:|---|---|
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
| 78 | `retrieval_consumes_phase1f_scope` | PASS |
| 79 | `retrieval_hard_filters_before_similarity` | PASS |
| 80 | `retrieval_indexes_are_derived` | PASS |
| 81 | `hybrid_merge_deterministic_score_provenance` | PASS |
| 82 | `reranker_allowed_candidates_only` | PASS |
| 83 | `rerank_scope_revalidation` | PASS |
| 84 | `evidence_pack_complete_provenance` | PASS |
| 85 | `rag_context_not_legal_source` | PASS |
| 86 | `sufficiency_is_policy_driven` | PASS |
| 87 | `generic_knowledge_not_jurisdiction_sufficient` | PASS |
| 88 | `external_preserves_formal_scope` | PASS |
| 89 | `unverified_discovery_not_evidence` | PASS |
| 90 | `official_external_validation` | PASS |
| 91 | `runtime_external_not_active` | PASS |
| 92 | `external_snapshot_reproducible` | PASS |
| 93 | `fallback_guidance_nonempty` | PASS |
| 94 | `fallback_not_compliance_path` | PASS |
| 95 | `retrieval_policy_snapshot_pinned` | PASS |
| 96 | `no_country_product_regulation_retrieval_branch` | PASS |
| 97 | `retrieval_services_no_provider_sql_graph_sdk` | PASS |
| 98 | `wiki_reuses_durable_review` | PASS |
| 99 | `wiki_not_official_legal_evidence` | PASS |
| 100 | `graph_reviewed_derived_provenance` | PASS |
| 101 | `runtime_client_cannot_supply_scope` | PASS |
| 102 | `normal_publish_automatic_runtime_sync` | PASS |
| 103 | `publication_reuses_registry_outbox_service` | PASS |
| 104 | `runtime_ready_before_new_retrieval` | PASS |
| 105 | `publication_snapshot_stability` | PASS |
| 106 | `publication_duplicate_retry_safe` | PASS |
| 107 | `publication_failed_build_not_ready` | PASS |
| 108 | `runtime_materialization_no_agent_graph` | PASS |

## Boundaries / exclusions / regression status

Phase 1E formal Context remains the only context input. Phase 1F PostgreSQL Source/Document/Version/Structure/Chunk/Binding/EvidenceReference/Citation tables remain canonical Knowledge Source of Truth. Retrieval stores, runtime materialization state, indexes, Wiki/Graph and RAGContextPack are derived. Runtime external evidence remains VERIFIED, separate from ACTIVE canonical knowledge.

Excluded: production model/provider execution, LLM answers, formal classification, regulation applicability, country-specific compliance routing, risk, Candidate/Final Compliance Path, required regulatory-document decisions and production legal agents. External parsing currently accepts attributed canonical JSON through the existing controlled MIME boundary; HTML/PDF web crawling and unrestricted discovery are outside this foundation. Embedding/rerank tests use explicit deterministic adapters behind ports. Original source text is preserved; no reviewed translation becomes original official text.

Phase 1A–1F regressions pass under the current 0007 migration. Earlier migration files 0001–0006 are unchanged. The historical Phase 1F main baseline remains `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; its 142-test baseline is historical and is not substituted for this Phase 1G 200-test result.


---

# Phase 1H architecture addendum

Original Rules 1–133 remain unchanged. Rules 134–139 add closed typed AST and pure rule evaluation, canonical provenance, reference-only classification, immutable governed publication, actual graph-based migration compatibility and Track A scope boundaries. Existing 108 executable architecture checks are preserved; 10 Phase 1H checks bring the measured total to 118/118. Static checks are supported by actual unit/PostgreSQL/API/migration tests rather than presented as proof of all runtime behavior.

No duplicate Registry/Knowledge/Workflow or rule/classification store is introduced. Pure domain/application modules remain infrastructure-free. No applicability/risk/path/LLM/frontend implementation is included.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.


# Phase1I — architecture preservation

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

Rules1–139 are preserved as an exact prefix of the verified baseline. Append-only Rules140–151 cover canonical applicability, shared metadata governance/outbox, deterministic scenario configuration, generic capabilities, scoped formal inputs, active/READY new pins versus exact historical replay, conservative evidence/conflict handling, no-data scenario delegation, immutable canonical provenance, phase/migration boundaries and locale-neutral presentation.

The executable checker retains all118 preceding checks and adds17 I checks (135 total). Domain/application purity, no eval/exec or country translation branches, one legal/knowledge/registry authority and no workflow/frontend/provider changes are verified alongside runtime tests. Static checks complement the PostgreSQL/API tests and do not establish legal correctness on their own.

Final complete measured table/JSON is retained under evidence/phase1i/local. Frozen migration and architecture-prefix hashes are recorded in the local manifest.
