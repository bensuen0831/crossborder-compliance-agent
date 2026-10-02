# Phase 1E Product Context Result

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

ProductContextResolutionService 驗證 ACTIVE metadata 的 PRODUCT_DOMAIN / PRODUCT_CATEGORY / PRODUCT_FAMILY / PRODUCT / PRODUCT_TAG UUID，保存 explicit selection 與 supplied document-detected ProductContextCandidate，建立 ProductContext、definition links 與 ProductScopeResolution。

selected 與 detected 均存在且 UUID sets 不同時保存 `PRODUCT_CONTEXT_CONFLICT`、selected_product_scope、detected_product_context、conflicting object IDs、reason、confidence 與 review flag；effective_product_scope 為空。无冲突时采用 selected 或 detected；兩者皆空為 GENERIC_UNRESOLVED。沒有 search-all fallback。

共用 conflict resolve route 以 registry validation 與 optimistic concurrency 更新 ProductScopeResolution.effective_product_scope，保存 resolver/時間與 resolution evidence。DataItem Product binding 維持個別 `data_item_product_links`，不將 project scope 自動複製至所有 item。

## Actual PASS assertions

- Unit：explicit A vs detected B → PRODUCT_CONTEXT_CONFLICT、REVIEW_REQUIRED、empty effective scope；保留兩個 product candidates。
- Unit：未選產品但 supplied detected A → effective scope 僅 A，排除 unrelated B。
- PostgreSQL：product candidate count = 2；field item product_refs 只含 A，unit item 只含 B；human resolution 將 scope_result 更新為 A，review_required=False；stale expected_record_version 拒絕。
- Schema：Product candidate/context definition registry FK、selected/detected/effective/conflict 欄位存在。

## Source-of-truth boundary

Product definitions 由 Phase 1C metadata registry authority 管理；context binding/resolution 是 project-specific scope；item binding SoT 為既有 `data_item_product_links` 加 link detail。此處不執行 Knowledge Scope retrieval。

## Actual limits

detected scope 由 run request 提供；没有从已上传文件自动解析产品 UUID 的 detector。Product service 可接受 source_trace_ids，但 run orchestrator 未傳入；item-product binding 明確傳入空 trace tuple。Document-evidence completeness 未由現有測試證實。Conflict detection 是 UUID set inequality，未实现产品层级兼容性 policy。ProductScopeResolution 更新已測；ProductContext effective scope 的同步更新未實作，不宣稱兩者均自動刷新。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
