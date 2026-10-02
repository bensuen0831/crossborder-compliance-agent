# Phase 1E Test Result

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

## Actual empirical assertions

**Full PostgreSQL/runtime pytest：82 passed / 0 skipped / 0 deselected。**

Baseline Run 36950913643 / Attempt 1 的 identity 由用戶提供；相同 source SHA 的前輪 local full gate log 為 `evidence/phase1e/baseline-local/pytest_full.log`（1 個 Starlette HTTP_422_UNPROCESSABLE_ENTITY deprecation warning，非 failure）。Local log 不冒充 remote Actions artifact。

| Gate | Baseline result |
|---|---|
| Fresh PostgreSQL Alembic | PASS，0005_phase1e |
| Phase 1E Schema | 22/22 PASS |
| Architecture | 59/59 PASS |
| Phase 1A runtime / checkpoint / restart / resume / retry | 25/25 assertions PASS |
| Phase 1B persistence / tenant / source of truth | PASS |
| Phase 1C registry / metadata / admin / pinning | PASS |
| Phase 1D parser / provenance / async parse | PASS；schema 15/15 PASS |

## Phase 1E test files / functions

- `test_phase1e_api.py::test_context_resolution_run_requires_trusted_context_and_returns_typed_result`
- `test_phase1e_api.py::test_context_conflict_api_uses_optimistic_concurrency`
- `test_phase1e_api.py::test_phase1e_required_api_paths_are_registered`
- `test_phase1e_context_unit.py::test_semantic_similarity_is_candidate_only_and_does_not_formal_merge`
- `test_phase1e_context_unit.py::test_product_selection_conflict_is_explicit_and_effective_scope_stays_empty`
- `test_phase1e_context_unit.py::test_no_selected_product_uses_document_detected_scope_not_all_registry`
- `test_phase1e_postgres.py::test_phase1e_context_resolution_formal_inventory_flow_review_versioning_and_isolation`
- `test_phase1e_postgres.py::test_phase1e_noncanonical_coordinates_are_rejected`

PostgreSQL fixture 涵蓋四種 generic documents、candidate resolutions、normalization/dedup/group、multi-product item bindings、Product/fact/duplicate/party/flow/location conflicts、review reuse、typed result、context versions、snapshot immutable pin、tenant isolation、invalid self-edge 無殘留、conflict optimistic concurrency 與 provenance。Unit/API fixtures 採 mock ports/repositories，不誤標為 PostgreSQL integration。

## Source-of-truth 與 known coverage limits

Assertions 驗證原有 authoritative data_items/flow/party tables 與新增 resolution/details，沒有另建 test-only formal authority。整合測試共用一個較大 fixture，未單獨覆蓋全部 conflict branches、未知 fact type review、workflow_run_id 缺省 review、完整 canonical geocoding、同名跨產品 separation、historical inventory reader 或全 run 原子 rollback。Final closure head 的結果待新完整 CI，不能以本 baseline 當新 CI。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
