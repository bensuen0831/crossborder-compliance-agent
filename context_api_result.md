# Phase 1E Context API Result

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

## Actual routes / contracts

實際註冊檔案：`interfaces/api/routes/context_resolution.py`；APIRouter prefix=/api/v1。由 API main 掛載；資料庫 context 由 trusted request RepositoryContext 取得，預設服務依 tenant scoped repository 建立。

| Method / route | 實際輸出或 contract |
|---|---|
| GET /api/v1/projects/{project_id}/business-context | business fact dictionary list |
| GET /api/v1/projects/{project_id}/product-context | ProductContext dictionary list + registry definition links |
| GET /api/v1/projects/{project_id}/scenario-context | ScenarioContext dictionary list |
| GET /api/v1/projects/{project_id}/systems | SystemContext dictionary list |
| GET /api/v1/projects/{project_id}/parties | PartyResolution dictionary list |
| GET /api/v1/projects/{project_id}/data-items | formal item/detail/provenance dictionary list |
| GET /api/v1/projects/{project_id}/data-groups | logical group/member dictionary list |
| GET /api/v1/projects/{project_id}/data-flows | dictionary with nodes / edges / data_item_links |
| GET /api/v1/projects/{project_id}/jurisdiction-context | JurisdictionContext dictionary list |
| GET /api/v1/projects/{project_id}/context-resolution | dataclass ContextResolutionResult via asdict; absent result = 404 |
| GET /api/v1/projects/{project_id}/context-conflicts | list[ContextConflictDTO] response_model |
| POST /api/v1/projects/{project_id}/context-resolution/run | ContextResolutionRunRequestDTO → ContextResolutionRunResponseDTO |
| POST /api/v1/context-conflicts/{conflict_id}/resolve | ContextConflictResolveRequestDTO → ContextConflictDTO |

Run request 包含 selected/detected product scope、selected/detected scenarios、system/device/party/jurisdiction specs、candidate item-product/flow bindings、DataGroupSpecDTO list 及 optional workflow_run_id。Run response 為 context_resolution_run_id、project_id、version、statistics、review_task_ids、confidence。

Resolve request 包含 resolution dictionary、resolved_by、expected_record_version>=1；回應含 conflict IDs/type、objects/reason、traces/confidence、resolution/review status、record_version。Run ValueError/LookupError 映射 422；resolve optimistic error=409、lookup error=404。

## Actual PASS assertions

`test_phase1e_required_api_paths_are_registered` 驗證 13 routes；unauthorized run=401、trusted run=200 且 typed statistics；mock-backed conflict resolve=200、stale version=409。Repository PostgreSQL test 另驗證 tenant isolation、persisted outputs 與 real concurrency。這不是 13 個 API 各自完整 PostgreSQL HTTP end-to-end tests。

## Source-of-truth boundary

HTTP 返回 dictionary / Pydantic DTO / dataclass projection，沒有 ORM object；讀取現有 authoritative context / inventory / flow tables，不建 API-owned result store。

## Actual limits

前十個 GET 沒有指定 response_model；ContextResolutionSummaryDTO 雖存在但該 GET 实际使用 asdict。DeviceContext 沒有獨立要求外的 /devices route；system/party/jurisdiction nested inputs 使用 dict[str,Any]，非完整 strict nested DTO。不能把設計 contract 宣稱為全部已部署 response_model。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
