# Phase 1E Jurisdiction Context Result

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

JurisdictionResolutionService 保存 JurisdictionContext 與 JurisdictionResolution，context_type 字串可表示 SOURCE / DESTINATION / PROCESSING / STORAGE / TRANSIT context。Registry ID 存在則 ACCEPTED；缺失則 REVIEW_REQUIRED，保存 LOCATION_CONTEXT_CONFLICT / JURISDICTION_AMBIGUOUS。

LocationPrecision 定義 EXACT_CANONICAL / REGION / COUNTRY / UNKNOWN；每筆含 jurisdiction_id、source、confidence、optional latitude/longitude、trace、version。country/region code 由 canonical jurisdictions reference 取得，context DTO 不另存 country code authority。

非 EXACT_CANONICAL 若提供座標則 ValueError；EXACT_CANONICAL 必須有存在的 jurisdiction ID。精確地理來源驗證的實際限制如下。

## Actual PASS assertions

PostgreSQL：PROCESSING EXACT_CANONICAL context 保存 fixture latitude=1.0 / longitude=2.0；STORAGE UNKNOWN context 的座標皆 None，review_required；typed result jurisdiction contexts = 2。`test_phase1e_noncanonical_coordinates_are_rejected` 對 DOCUMENT_DERIVED / UNKNOWN 搭配座標 raises ValueError。

## Source-of-truth boundary

Jurisdiction identity SoT 為既有 `jurisdictions`；`jurisdiction_contexts` 保存 project location context，resolution 保存理由/evidence。Jurisdiction Context != Regulation Applicability；不計算 cross-border legal status。

## Actual limits

source/destination/transit 是 context_type 可接受字串，並未對三者逐一做 empirical fixture。服務未查 canonical geocoded coordinate record，也未驗證 request 坐標與 registry canonical 坐標相等；因此不能宣稱已阻止任意 caller 把自由文本座標標成 EXACT_CANONICAL。Parser/LLM 未在本 Phase 產生正式精確座標。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
