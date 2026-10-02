# Phase 1E Business Fact Resolution Result

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

Phase 1D `BusinessFactCandidateEntity` 保留原始值、normalized value、fact type 與 SourceTrace。BusinessFactNormalizationService 依 ACTIVE `BUSINESS_FACT_TYPE` metadata code 驗證類型，以 (fact_type, normalized value key) grouping，保留 original_values、source_document_ids、trace IDs、confidence、version。

Candidate → CandidateResolution / BusinessFactResolution → BusinessFact 具可追溯關聯。repository `save_business_fact` 寫入 `business_facts` 與 `business_fact_resolutions`；generic `candidate_resolutions` 記錄 candidate/formal object mapping、action、reason、review flag、resolver type 與 version。Candidate 不因處理而刪除。

同一 fact type 多個 normalized values 產生 domain `BusinessFactConflict`，以 `BUSINESS_FACT_CONFLICT` 存入共用 `context_conflicts`。Fact 標記 CONFLICT / REVIEW_REQUIRED，candidate resolution 同步為 CONFLICT；未知 registry fact type 僅記錄 REVIEW_REQUIRED，不生成 confirmed formal fact。

## Actual PASS assertions

PostgreSQL generic project assertions：business context 非空；所有 conflicting business facts 的 validation_status 為 REVIEW_REQUIRED、conflict_status 為 CONFLICT；conflict list 含 BUSINESS_FACT_CONFLICT；版本 1 BUSINESS_FACT resolution count 等於留存 fact candidate count。Schema gate 驗證 resolution 的 candidate_fact_id / business_fact_id / action 欄位。

## Provenance、review 與 Source of Truth

Formal fact SoT 為 `business_facts`；provenance 使用既有 candidates、SourceTrace refs、source document IDs 與 resolution records。BusinessFactConflict 不另建第二套 conflict authority，沿用 `context_conflicts`。ReviewTask 使用既有 subsystem。

## Actual limits

ResolutionAction 宣告 PENDING / ACCEPTED / REJECTED / MERGED / SPLIT / CONFLICT / REVIEW_REQUIRED，但本輪未測各 action 的完整人工處理操作。BusinessFactResolution action 由 repository 記錄 ACCEPTED / MERGED，conflict 則反映在 generic CandidateResolution、BusinessFact validation/conflict status 與 reviewer_required；不宣稱兩套 resolution action 完全相同。Unknown fact type 分支只有 candidate review flag，未直接建立 ContextConflict；ContextValidationService 只從 persisted conflicts 建立 workflow-bound reviews。不得宣稱所有 review-required candidates 已自動產生 ReviewTask。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
