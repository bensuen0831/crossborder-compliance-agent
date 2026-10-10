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

- workflow_run_id: `fd3c57c0-1b8c-4bee-bb92-60fa7e9f2a5f`
- thread_id: `fd3c57c0-1b8c-4bee-bb92-60fa7e9f2a5f`
- tenant_id: `429703c5-c2ac-48c3-9a01-fe1fce057720`
- analysis_snapshot_id: `e9290b90-169d-49cc-9d17-e4b936c63963`

## Checkpoint Evidence

- tables: `['checkpoint_blobs', 'checkpoint_migrations', 'checkpoint_writes', 'checkpoints']`
- rows for thread: `5`
- process-1 rows before exit: `3`

## Resume Retry

- safe: `True`
- events unchanged: `True`
- review count unchanged: `True`
