# Phase 1A.1 Mandatory PostgreSQL-backed LangGraph Runtime Smoke

## Gate Decision

**PASS**

## Mandatory Assertions

| Mandatory assertion | Result |
|---|---|
| `postgres_checkpoint_row_gt_zero` | **PASS** |
| `workflow_run_exists` | **PASS** |
| `analysis_snapshot_exists` | **PASS** |
| `analysis_snapshot_and_checkpoint_are_separate_sources` | **PASS** |
| `workflow_run_id_equals_thread_id` | **PASS** |
| `review_task_count_eq_one` | **PASS** |
| `review_required_event_count_eq_one` | **PASS** |
| `workflow_resumed_event_count_eq_one` | **PASS** |
| `workflow_completed_event_count_eq_one` | **PASS** |
| `formal_completion_audit_count_eq_one` | **PASS** |
| `final_workflow_status_completed` | **PASS** |
| `tenant_id_preserved_after_restart` | **PASS** |
| `analysis_snapshot_id_preserved_after_restart` | **PASS** |
| `graph_runtime_checkpointer_state_schema_versions_retained` | **PASS** |
| `audit_provenance_retained` | **PASS** |
| `canonical_events_only` | **PASS** |
| `no_raw_langgraph_payload_keys_persisted` | **PASS** |
| `external_workflow_event_contract_has_no_raw_langgraph_fields` | **PASS** |
| `api_layer_has_no_raw_langgraph_import` | **PASS** |
| `domain_metadata_does_not_own_checkpoint_tables` | **PASS** |
| `process1_checkpoint_existed_before_process_exit` | **PASS** |
| `process2_loaded_checkpoint_context_before_resume` | **PASS** |
| `resume_retry_safe` | **PASS** |
| `resume_retry_event_counts_unchanged` | **PASS** |
| `resume_retry_review_count_unchanged` | **PASS** |

## Workflow Identity

- workflow_run_id: `8e6c8bda-b955-41d1-abee-9b3474ae6553`
- thread_id: `8e6c8bda-b955-41d1-abee-9b3474ae6553`
- tenant_id: `3827eb31-c9b7-45d6-b7a8-1d590985d833`
- analysis_snapshot_id: `8480467c-ef1f-4cf9-9cf7-24373b8742f3`

## Checkpoint Evidence

- tables: `['checkpoint_blobs', 'checkpoint_migrations', 'checkpoint_writes', 'checkpoints']`
- rows for thread: `5`
- process-1 rows before exit: `3`

## Resume Retry

- safe: `True`
- events unchanged: `True`
- review count unchanged: `True`
