# Phase 1E Architecture Rule Check

## Phase 與 evidence identity

- Phase：Phase 1E；本次文件整理：Phase 1E.1 Delivery & Evidence Closure。
- Previous tested code / source branch SHA：`6d05588a02752dc5479658f63bc4b6ab8c29331e`。
- Baseline GitHub Actions Run ID：`36950913643`；Attempt：`1`。
- Baseline PR runner merge SHA：`fac2806d819694b4fb8210179ec90348f73791ca`。
- Base Phase 1D SHA：`51429bc147a843f67ef43e88f7ae61094f6144f1`。
- Alembic head：`0005_phase1e`。
- Full PostgreSQL/runtime pytest：**82 passed / 0 skipped / 0 deselected**。
- Phase 1E PostgreSQL Schema Gate：**22/22 PASS**。
- Executable Architecture Rules：**59/59 PASS**。
- Phase 1A、1B、1C、1D regression：**PASS / PASS / PASS / PASS**。

Run identity 與 CI baseline 由本輪提供的 verified empirical baseline 引用；本環境尚未下載該 Actions run 的原始 artifact。`evidence/phase1e/baseline-local/` 為前輪在相同 source SHA 獨立執行完整 PostgreSQL/runtime gate 的證據，結果一致，但不是 Run 36950913643 的 artifact。Artifact ID / digest 不得以本地檔案雜湊冒充。

本文件的 PASS 僅指下列實際程式／測試 assertions 與既有 baseline。新的 documentation commit 尚須完整 CI，才能完成最終 Delivery Closure；舊 run 不涵蓋新 PR head。最終 head、run、artifact 與完整 log 應存入 `evidence/phase1e/final_ci_manifest.json`，目前不簽發 Phase 1F entry decision。

## Actual executable rule result

**59/59 PASS**，來自 `scripts/architecture_rule_check.py`；`ARCHITECTURE_RULES.md` Phase 1E addendum 為 rules 94–103。59 是累積 executable checks 數，不是 addendum 新規則數。

| # | Check | Baseline |
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

## Source-of-truth boundary

Checks 保障無平行 data item/flow authority、review subsystem、classification source；Domain/Application 不依賴 SQLAlchemy/LangGraph/provider SDK；candidate/trace/version/schema boundary 使用現有模型與 extension。Product/Jurisdiction contexts 不能當作 regulation decision。

## Known executable-check limits

多數規則使用 source regex/token 檢查，PASS 不等於所有行為的 formal proof。no_product_search_all_scope 驗證 resolver 的 selected/detected/fallback，而非自動文件產品偵測；context_snapshot_versioned 驗證欄位與 immutable pin，而非全 historical reader。Behavioral tests 補充驗證，其已測／未測範圍詳各 result 文件。新文件 head 必須重新執行此腳本。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
