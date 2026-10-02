# Phase 1E Formal Data Inventory Result

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

## Actual implementation scope

DataItemNormalizationService 由 Phase 1D CandidateDataItem 讀取 normalized/raw name，按 normalized name 分組，要求 union SourceTrace 非空，再建立 authoritative `data_items` 與 one-to-one `data_item_resolution_details`。Detail 包含 display_name、value_type、format、unit、frequency/quantity metadata、system/device refs、confidence、validation/review 與 version。

每個 candidate 透過 `data_item_candidate_links` 映射 formal item；`data_item_source_trace_links` 連回既有 `source_trace_refs`。每次 formalization 產生 candidate resolution ACCEPTED 或 MERGED；不將 CandidateDataItem 作為 formal source，也不刪除 occurrences。

Item-product links 明確绑定每個 item；system/device ID arrays 有儲存欄位。正式流與 item 使用 DataItemFlowLink 的 UUID 關聯。

## Actual PASS assertions

generic field 在 DOCX / XLSX / PPTX 至少出現三次；單一 canonical_name=field formal item 保留至少三個 raw_candidate_ids 與 source_trace_ids。所有 DATA_ITEM candidates 的 resolution count 等於留存 candidate count。Item A 只綁 Product A、另一 item 只綁 B；other tenant 無法讀取 item inventory。Schema gate 驗證 one-to-one detail PK、candidate link、source trace FK 與無 parallel item tables。

## Source-of-truth boundary

Formal item SoT：`data_items`。Detail 與 link tables 是補充欄位與 provenance；不建立 formal_data_items / resolved_data_items / final_data_items。GET data-items 返回 plain dictionary projection，不是 ORM object。

## Actual limits

Normalization 的 system_ids/device_ids 初始為空，沒有自動把 request systems 綁至 item；format 預設 None。Product links 存在但 GET data-items projection 未直接返回 product/party link arrays。現有 grouping key 僅 normalized name，沒有產品/系統完整 composite identity；本輪證實不同 item 的 Product isolation，不證實同名跨產品 item 必然分離。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
