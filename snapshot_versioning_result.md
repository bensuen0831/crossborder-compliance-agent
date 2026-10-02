# Phase 1E Snapshot / Versioning Result

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

ContextResolutionRun 帶 project context version、product_context_version、data_inventory_version、data_flow_version 與 statistics/confidence。新 run 版本遞增，context/resolution rows 帶 version。pin_snapshot_context 保存 AnalysisSnapshotContextPin 指向 run UUID 及上述四個版本，unique tenant/snapshot/project；同 snapshot 重新 pin 不同 run raises ValueError。

DocumentVersion / ParseRun pin 與 metadata version pin 重用 Phase 1D / 1C Infrastructure，Phase 1E 增加 context pins，不把 LangGraph checkpoint 當 AnalysisSnapshot。Runtime resume 從既有 checkpoint / snapshot identity 恢復，沒有動態 registry/context refresh 调用。

## Actual PASS assertions

PostgreSQL：run1.version=1；run2.version=2；既有 snapshot pin run1 不可改指 run2；database pin version=1 且 run ID 保留。Product conflict expected_record_version=1 的首次 update 成功、同版本重試 raises OptimisticConcurrencyError；API stale update=409。Phase 1A 25 runtime assertions 包含 checkpoint process restart、snapshot identity 保存、duplicate retry 无新增 events/reviews。

## Source-of-truth boundary

analysis_snapshots + existing metadata/parse pins + analysis_snapshot_context_pins 定義分析輸入 identity；domain tables 為資料 authority。context run summary 不建立獨立 final inventory。LangGraph checkpoint internals 仍由 PostgresSaver.setup 管理。

## Actual limits

pin immutability test 不等於完整 historical materialization。data_item_resolution_details 為 one-to-one、groups/product links 非完整 run-specific history；project GETs 會列出 project rows，ContextResolutionResult 目前按最新 version 重新組合。沒有提供已測的 snapshot-version-specific inventory reader；故不宣稱 update 後所有舊 inventory link/value 均可由新 query 完整重建。

Review resolve 可在同 context version 更新 resolution；record_version concurrency 與 analysis version 是不同概念。未為整個 orchestrator 提供 single transaction rollback，也未測 context run 競爭创建的全部 interleavings。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
