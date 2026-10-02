# Phase 1E Data Item Deduplication / Grouping Result

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

Raw occurrence、normalized DataItem、logical DataGroup 是不同計數。repository.aggregate_statistics 以 SQL func.count 分別計算 project parse-run CandidateDataItem count、authoritative data_items count、data_item_groups count；不由 LLM 估計。

DataItemDeduplicationService.compare 保存 DataItemDeduplicationResult，含 left/right candidate IDs、decision、deterministic score、semantic candidate score、reason、review flag、version。名稱與 value_type/unit 提供 deterministic score；同 normalized name 可得到 SAME_ITEM。高 semantic similarity 僅產生 POSSIBLE_SAME 與 DATA_ITEM_POSSIBLE_DUPLICATE conflict，不執行 formal merge。

DataItemGroupingService 按 requested item IDs 建立既有 data_item_groups / data_item_group_members；logical grouping 與 Classification Category 完全分離。

## Actual PASS assertions

- PostgreSQL：raw_field_count > normalized_data_item_count > 0；data_group_count = 1。這是三種概念，不要求三個數字在所有項目中必然不相等。
- 重複 field candidates >= 3，formal field item 保留全部 provenance；generic group Operational Fields 存在。
- Semantic 0.95 在不同名稱 pair 產生 POSSIBLE_SAME、review flag、persisted conflict，無 formal merge。

## Source-of-truth boundary

Occurrences 在 candidate tables；formal items 在 data_items；groups 在 data_item_groups / members。Dedup results 是 evidence，不是新 authoritative inventory。Counts 從現有 structured persistence 聚合，run statistics_json 只保存當次摘要。

## Actual limits

Raw count 定義是 CandidateDataItem occurrence count，不是 document 所有 parser cells 的總和。後續 runs 的 aggregate counts 查 project tables，未做 snapshot-specific occurrence filtering。Normalize 先做 name grouping，compare 不作合併決策；未實作完整 field-structure/source-relation/product/system composite dedup policy。未在本文虛構 fixture 的確切 raw/normalized 絕對數，因測試僅 assert inequality。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
