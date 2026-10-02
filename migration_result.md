# Phase 1E PostgreSQL Migration Result

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

## Actual migration / PASS assertions

Alembic chain：0001_phase1a → 0002_phase1b → 0003_phase1c → 0004_phase1d → **0005_phase1e**。`alembic/versions/0005_phase1e_context_resolution.py` revision=0005_phase1e，down_revision=0004_phase1d；`alembic/env.py` import context metadata。

Baseline fresh PostgreSQL upgrade PASS；Phase 1E schema checks **22/22 PASS**。Checks 驗證 head、required tables、registry FKs、candidate/formal boundary、one-to-one item detail PK、source trace FK、separate count fields、structured flow/link details、jurisdiction context fields、snapshot pin versions、既有 review 重用及原有 authoritative tables 存在。詳細 assertions：`scripts/phase1e_schema_check.py` 與 `evidence/phase1e/baseline-local/phase1e_schema_check.json`。

## Actual Phase 1E ORM tables

- `business_facts`
- `business_fact_resolutions`
- `candidate_resolutions`
- `context_conflicts`
- `product_context_candidates`
- `product_contexts`
- `product_context_definition_links`
- `product_scope_resolutions`
- `scenario_contexts`
- `scenario_resolutions`
- `system_contexts`
- `device_contexts`
- `system_relations`
- `party_candidates`
- `party_resolutions`
- `data_item_resolution_details`
- `data_item_candidate_links`
- `data_item_source_trace_links`
- `data_item_deduplication_results`
- `data_item_product_link_details`
- `jurisdiction_contexts`
- `jurisdiction_resolutions`
- `data_flow_node_details`
- `data_flow_edge_details`
- `data_item_flow_link_details`
- `context_resolution_runs`
- `analysis_snapshot_context_pins`

## Source-of-truth boundary

重用 data_items、data_item_groups、data_flow_nodes、data_flow_edges、data_item_flow_links、data_item_product_links、project_parties、party_role_assignments。Migration 只新增 context / resolution / detail / provenance extensions；不存在 formal_data_items / resolved_data_items / final_data_items 或第二套 review tables。Checkpoint schema 不由 Domain Alembic 持有。

## Actual limits

schema gate count 是 22 個 assertions，不是 table count。migration 有 destructive downgrade 定義，但本輪沒執行 downgrade／資料回復測試；不把 downgrade 當已驗證 operational rollback。精確座標欄位存在只證明 schema，不證明外部 canonical geocoding 已實作。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
