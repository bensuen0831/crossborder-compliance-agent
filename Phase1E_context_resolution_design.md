# Phase 1E Context Resolution Design

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

`domain/context_resolution.py` 定義不可變 Context / Resolution dataclasses、ResolutionAction、ContextValidationStatus、DedupDecision、LocationPrecision。`application/context_ports.py` 定義 repository / SemanticResolutionPort / CandidateSimilarityPort；`application/context_services.py` 提供 normalization、scope、scenario、system/device、party、dedup、grouping、flow、jurisdiction 與 validation application services。Provider SDK、Vector DB 與 LLM 調用不在服務內。

實際 `ContextResolutionService.run` 順序：start versioned run → business fact normalization/conflict → product scope → scenario → request-supplied system/device/party context → formal item normalization → pairwise dedup evidence → requested grouping → item-product bindings → jurisdiction → structured flow → conflict/review aggregation → finish run。Jurisdiction 先於 flow，用於 node location binding。Candidate / Resolution / validation status 持久化；review-required 物件不能據此被宣告為已確認的 Compliance input。

## Actual PASS assertions

`tests/test_phase1e_postgres.py::test_phase1e_context_resolution_formal_inventory_flow_review_versioning_and_isolation` 在同一 generic project 使用 DOCX / XLSX / PPTX / PDF，驗證所有 Phase 1D fact/item/node/edge candidate 均有版本 1 resolution；candidate 留存、typed result 非空、Product A/B item isolation、structured flow links、conflicts/reviews、version 1 → 2、immutable pin、tenant isolation、invalid self-edge 拒絕與 stale conflict update 拒絕。

其他 7 個 Phase 1E 測試涵蓋 semantic candidate-only、explicit product conflict、no search-all fallback、API authentication/contract、API conflict concurrency、13 routes 與 noncanonical coordinate rejection。Phase 1E 合計 8 個測試函式；完整累積 suite 為 82，不是 82 個 Phase 1E-only tests。

## Source-of-truth boundary

Formal inventory：`data_items` / `data_item_groups`；formal flow：`data_flow_nodes` / `data_flow_edges` / `data_item_flow_links`；formal party：`project_parties` / `legal_entities`。Product/Scenario/Type bindings 指向 ACTIVE metadata definitions。Jurisdiction context 指向 `jurisdictions`。Detail、resolution、source-link 與 run summary 為 extension/provenance，不建立 parallel authoritative result store。

## Actual limits

detected product/scenario UUIDs 及 systems/devices/parties/jurisdictions 由 request supplied context 傳入，未建置自動 document-to-registry semantic detector。Normalization 現以 project normalized name grouping；未測同名但不同 system/product 的完整 separation policy。Review creation 需要 workflow_run_id；精確座標僅驗證 canonical precision 標記與 jurisdiction existence。這些實作邊界會在分項報告明列，不宣稱額外功能。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
