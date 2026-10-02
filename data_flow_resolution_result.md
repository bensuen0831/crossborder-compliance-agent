# Phase 1E Formal Data Flow Resolution Result

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

DataFlowResolutionService 由 candidate node/edge 解析 structured `data_flow_nodes` / `data_flow_edges`，以 detail tables 保存 system/party/jurisdiction、role、direction、protocol/frequency、confidence、source traces、validation/version。SYSTEM node 必須找到已知 SystemContext；已知 party/location candidate 必須解析成功。

Flow edge 必須有正式 source/target、方向及至少一個 resolved item binding，並建立 `data_item_flow_links` / detail。Conflict 路徑包括 SYSTEM_CONTEXT_CONFLICT、PARTY_CONTEXT_CONFLICT、LOCATION_CONTEXT_CONFLICT、SOURCE_DESTINATION_CONFLICT、FLOW_DIRECTION_CONFLICT、DATA_ITEM_FLOW_CONFLICT；保留 candidate resolution CONFLICT。

## Actual PASS assertions

PostgreSQL：formal node count >= 2、edge count >= 1；nodes 均有 system ID、匹配 party ID 與 jurisdiction context；links 非空且含 field item。UNKNOWN direction candidate 產生 FLOW_DIRECTION_CONFLICT。每個留存 DATA_FLOW_NODE / DATA_FLOW_EDGE candidate 均有 resolution record。Repository invalid self-edge raises ValueError，edge count 不變，沒有留下無效正式 edge。

## Source-of-truth boundary

正式 flow authority 是 Phase 1B 原有 nodes / edges / item links；Phase 1E details 與 candidate resolutions 補充 provenance。Narrative label 不能替代 DataItemFlowLink；不建 parallel resolved_data_flows store。

## Actual limits

Item-flow bindings 由 request 显式传入 candidate IDs；缺少 resolved item 则 conflict，不从自由文本 customer data 自动推断。Self-edge test 證實個別 repository operation 的拒絕／無殘留，不代表整個 resolution orchestrator 是單一原子 transaction。各 conflict branch 有實作，單一 generic fixture 不獨立覆蓋每種 branch 的全部組合。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
