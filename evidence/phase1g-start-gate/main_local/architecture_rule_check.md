# Phase 1F Architecture Rule Check

**Decision: PASS — 77/77 checks passed.**

| # | Architecture rule check | Result | Evidence |
|---:|---|---|---|
| 1 | `domain_has_no_langgraph_import` | **PASS** | `"clean"` |
| 2 | `domain_has_no_sqlalchemy_import` | **PASS** | `"clean"` |
| 3 | `application_has_no_sqlalchemy_import` | **PASS** | `"clean"` |
| 4 | `langgraph_runtime_isolated_to_adapter` | **PASS** | `["src/crossborder_compliance/workflows/langgraph_adapter.py"]` |
| 5 | `no_eval_exec` | **PASS** | `"clean"` |
| 6 | `human_review_node_not_agent` | **PASS** | `"clean"` |
| 7 | `classification_results_is_only_formal_classification_source` | **PASS** | `"classification_results present; data_classifications absent"` |
| 8 | `workflow_stage_view_not_persisted` | **PASS** | `"no WorkflowStageView persistence model/table"` |
| 9 | `regulatory_structure_node_is_canonical_persistence` | **PASS** | `"RegulatoryStructureNodeEntity present"` |
| 10 | `stage1_explicit_cross_border_results` | **PASS** | `"Stage1ComplianceResultDTO.cross_border_results"` |
| 11 | `legal_basis_rulehit_many_to_many_contract` | **PASS** | `"LegalBasisItemDTO.rule_hit_ids[]"` |
| 12 | `legal_basis_rulehit_many_to_many_persistence` | **PASS** | `"association table legal_basis_rule_hit_links"` |
| 13 | `domain_migration_does_not_own_checkpointer_schema` | **PASS** | `"no checkpoint internal DDL in Domain Alembic"` |
| 14 | `api_workflow_idempotency_separated` | **PASS** | `"separate tables present"` |
| 15 | `workflow_state_has_no_runtime_services_or_secrets` | **PASS** | `{"forbidden": ["db_session", "repository", "client", "secret", "api_key", "provider", "document_bytes", "knowledge_chunks"]}` |
| 16 | `durable_postgres_checkpointer_setup_present` | **PASS** | `"PostgresSaver + official setup() path"` |
| 17 | `thread_id_backend_bound_to_workflow_run_id` | **PASS** | `"workflow_run_id used as LangGraph thread_id"` |
| 18 | `conversation_thread_not_langgraph_thread_id` | **PASS** | `"ConversationThreadEntity has no standalone LangGraph thread_id field"` |
| 19 | `interrupt_pre_side_effect_event_idempotent` | **PASS** | `"deterministic event + idempotent review key"` |
| 20 | `raw_langgraph_event_not_external_contract` | **PASS** | `"canonical event boundary present"` |
| 21 | `api_routes_do_not_return_or_import_orm_models` | **PASS** | `"API layer uses Pydantic/Application DTOs only"` |
| 22 | `domain_repositories_are_automatically_tenant_scoped` | **PASS** | `["PostgresProjectRepository", "PostgresPartyRepository", "PostgresDocumentRepository", "PostgresDataInventoryRepository", "PostgresJurisdictionRepository", "PostgresClassificationRepository", "PostgresEvidenceRepository", "PostgresLegalBasisRepository", "PostgresAnalysisSnapshotRepository", "PostgresWorkflowRunRepository", "PostgresReviewRepository", "PostgresAnalysisStageRepository", "PostgresConversationRepository"]` |
| 23 | `no_second_classification_repository` | **PASS** | `"one ClassificationRepository adapter; no parallel DataClassificationRepository"` |
| 24 | `no_country_product_regulation_fixed_business_logic` | **PASS** | `"no fixed country/product/regulatory-document business skills"` |
| 25 | `frontend_has_no_business_metadata_enum` | **PASS** | `"no hard-coded frontend business option lists"` |
| 26 | `agent_skill_has_no_model_name_or_base_url` | **PASS** | `"no provider/model/base-url binding in agent/skill/workflow code"` |
| 27 | `prompt_business_content_not_embedded_in_agent` | **PASS** | `"no embedded business prompt in agent/skill code"` |
| 28 | `registry_not_source_of_truth` | **PASS** | `"ProjectionRegistry explicitly identifies itself as non-authoritative projection"` |
| 29 | `admin_draft_not_runtime_visible` | **PASS** | `"runtime loaders filter ACTIVE lifecycle versions only"` |
| 30 | `model_secret_not_persisted_in_metadata` | **PASS** | `"model metadata stores secret_ref only; no credential-value columns"` |
| 31 | `snapshot_not_dynamic_registry_lookup_on_resume` | **PASS** | `"resume adapter does not consult registry; snapshot pins are immutable"` |
| 32 | `registry_publish_uses_transactional_outbox` | **PASS** | `"publish and RegistrySyncEvent are written inside the same DB transaction"` |
| 33 | `no_country_specific_registry_branch` | **PASS** | `"registry resolution is metadata/binding driven"` |
| 34 | `graph_state_has_no_document_binary` | **PASS** | `"LangGraph state contains references only; no document binary fields"` |
| 35 | `canonical_document_not_llm_narrative` | **PASS** | `"canonical parser output is structured and parser-driven, not LLM narrative"` |
| 36 | `candidate_vision_has_no_legal_result` | **PASS** | `"CandidateDiagramResult contains candidate nodes/edges only"` |
| 37 | `extracted_result_has_source_trace` | **PASS** | `"candidate facts/items/flows carry SourceTraceRef and persistence rejects empty provenance"` |
| 38 | `spreadsheet_preserves_row_column_provenance` | **PASS** | `"XLSX adapter preserves row/column/header/formula/merged-cell metadata"` |
| 39 | `formal_counts_not_llm` | **PASS** | `"DocumentAnalysisSummary is programmatically aggregated from persistence"` |
| 40 | `parse_run_is_versioned` | **PASS** | `"Phase 1B parse-run identity + Phase 1D one-to-one detail extension has explicit version and unique tenant/document/version constraint"` |
| 41 | `snapshot_can_pin_parse_run` | **PASS** | `"AnalysisSnapshot has immutable parse-run pin persistence"` |
| 42 | `parser_provider_is_adapter_only` | **PASS** | `"provider SDKs isolated to infrastructure/document_parsers.py"` |
| 43 | `phase1d_has_no_country_product_regulation_logic` | **PASS** | `"Document Intelligence foundation contains no fixed country/product/regulation decisions"` |
| 44 | `candidate_not_formal_compliance_input` | **PASS** | `"Candidate → Resolution → Formal object boundary is persisted; candidates are retained"` |
| 45 | `product_context_is_registry_driven` | **PASS** | `"Product Context resolves ACTIVE metadata definitions and persists registry bindings"` |
| 46 | `no_product_search_all_scope` | **PASS** | `"No selection uses document-detected scope or unresolved generic scope; never all products"` |
| 47 | `product_conflict_is_explicit` | **PASS** | `"Explicit selection vs detected scope conflict is persisted as PRODUCT_CONTEXT_CONFLICT"` |
| 48 | `business_fact_conflict_is_explicit` | **PASS** | `"Conflicting normalized values for one registry fact type create explicit reviewable conflict"` |
| 49 | `possible_duplicate_requires_review_conflict` | **PASS** | `"Semantic POSSIBLE_SAME remains candidate-only and enters ContextConflict/review"` |
| 50 | `unresolved_party_requires_review_conflict` | **PASS** | `"Unresolved PartyCandidate persists PartyResolution plus explicit reviewable conflict"` |
| 51 | `data_item_source_trace_required` | **PASS** | `"Formal data_items retain all candidate and SourceTrace links"` |
| 52 | `formal_counts_are_separate` | **PASS** | `"Raw occurrence, normalized DataItem and DataGroup counts are separate programmatic aggregates"` |
| 53 | `no_parallel_data_item_source_of_truth` | **PASS** | `"Phase 1B data_items remains authoritative; Phase 1E adds detail/link tables only"` |
| 54 | `no_parallel_data_flow_source_of_truth` | **PASS** | `"Phase 1B data_flow_nodes/data_flow_edges/data_item_flow_links remain authoritative"` |
| 55 | `data_flow_is_structured` | **PASS** | `"Formal flow uses structured Node/Edge/DataItemFlowLink plus versioned detail"` |
| 56 | `jurisdiction_not_regulation_decision` | **PASS** | `"Jurisdiction Context carries location context only; no regulation/cross-border legal decision"` |
| 57 | `semantic_resolution_candidate_only` | **PASS** | `"Semantic similarity can create candidate/review evidence but does not directly merge formal DataItems"` |
| 58 | `context_snapshot_versioned` | **PASS** | `"AnalysisSnapshot pins immutable versioned Context/DataInventory/DataFlow versions"` |
| 59 | `no_country_product_rule_logic` | **PASS** | `"No country/product-code/regulation decision routing, risk, or compliance-path logic"` |
| 60 | `knowledge_platform_not_vector_db` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 61 | `scope_resolver_has_no_retrieval` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 62 | `hard_filter_precedes_similarity` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 63 | `unrelated_product_knowledge_excluded` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 64 | `unresolved_product_scope_fail_safe` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 65 | `knowledge_chunk_has_provenance` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 66 | `vector_index_is_derived` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 67 | `fts_index_is_derived` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 68 | `registry_not_knowledge_source` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 69 | `translation_review_boundary` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 70 | `knowledge_quality_before_active` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 71 | `snapshot_pins_knowledge_version` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 72 | `phase1f_uses_phase1e_context` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 73 | `no_country_specific_knowledge_branch` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 74 | `no_regulation_business_decision` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 75 | `controlled_downloader_boundary` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 76 | `knowledge_ingestion_no_graph_checkpoints` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
| 77 | `no_parallel_knowledge_source` | **PASS** | `"Phase 1F canonical/domain/service/migration boundary; tests/test_phase1f_* empirical coverage"` |
