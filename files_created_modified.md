# Phase 1E Files Created / Modified

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

## Actual Phase 1E implementation files

以下由 `git diff --name-status 51429bc147a843f67ef43e88f7ae61094f6144f1..6d05588a02752dc5479658f63bc4b6ab8c29331e` 取得，A=added、M=modified。這是之前完成的 implementation diff，本次不改這些檔案。

| Status | Actual file |
|---|---|
| M | `ARCHITECTURE_RULES.md` |
| M | `alembic/env.py` |
| A | `alembic/versions/0005_phase1e_context_resolution.py` |
| M | `scripts/architecture_rule_check.py` |
| M | `scripts/phase1b_schema_check.py` |
| M | `scripts/phase1c_schema_check.py` |
| M | `scripts/phase1d_schema_check.py` |
| A | `scripts/phase1e_schema_check.py` |
| M | `smoke/postgres_schema_evidence.py` |
| M | `smoke/run_gate.sh` |
| A | `src/crossborder_compliance/application/context_ports.py` |
| A | `src/crossborder_compliance/application/context_services.py` |
| A | `src/crossborder_compliance/domain/context_resolution.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/context_models.py` |
| A | `src/crossborder_compliance/infrastructure/persistence/context_repositories.py` |
| A | `src/crossborder_compliance/interfaces/api/context_schemas.py` |
| M | `src/crossborder_compliance/interfaces/api/main.py` |
| A | `src/crossborder_compliance/interfaces/api/routes/context_resolution.py` |
| A | `tests/test_phase1e_api.py` |
| A | `tests/test_phase1e_context_unit.py` |
| A | `tests/test_phase1e_postgres.py` |

## Phase 1E.1 documentation / evidence closure files

- `Phase1E_context_resolution_design.md`
- `business_fact_resolution_result.md`
- `product_context_result.md`
- `scenario_system_party_context_result.md`
- `data_inventory_result.md`
- `data_item_dedup_group_result.md`
- `data_flow_resolution_result.md`
- `jurisdiction_context_result.md`
- `context_conflict_review_result.md`
- `context_api_result.md`
- `snapshot_versioning_result.md`
- `migration_result.md`
- `test_result.md`
- `architecture_rule_check.md`
- `files_created_modified.md`
- `ARCHITECTURE_RULES.md`：追加交付證據索引，規則 94–103 內容不變；此檔案在既有 pull_request path filter 內，可使文件推送匹配完整 CI workflow。
- `evidence/phase1e/baseline_manifest.json`：baseline identity、來源歸屬與 gate numbers。
- `evidence/phase1e/baseline-local/`：相同 code SHA 的前輪 local gate 證據，清楚區分 remote run。

本次 new PR head 在文件 commit 後由 Git 產生；完整 head / documentation-only diff confirmation 記錄在 checkout 外的 closure receipt，避免在 commit 內容內自引用 SHA。Final remote CI 若可取得，另外保存 run manifest / logs / artifact identity；未通過前不生成 Phase1F_entry_decision.md。

## Source-of-truth boundary / actual PASS assertions

原 implementation file inventory 與 Git diff 一致。Baseline technical assertions 82 pytest / 22 schema / 59 architecture 已有結果；本次 commit 僅允許 root deliverable Markdown 及 evidence/phase1e 內 evidence files。Source/test/migration/workflow hash 必須與 previous tested code 一致，確認未新增 business 功能。文件 evidence 不成為另一套 domain authority。

## Known exclusions 與回歸邊界

本次僅更新 documentation / evidence；不修改 Domain、Application、API、migration、tests 或 workflow 實作。RAG / Knowledge Retrieval、Formal Classification、Regulation Applicability、Risk、Country Compliance、Compliance Path、Required Regulatory Document Decision、Production Agent 均不在本 Phase 執行範圍。

Phase 1A–1D baseline 回歸保持 PASS；新文件 head 的回歸狀態以新 CI 為準。靜態規則與測試通過不代表未測路徑、完整地理驗證、法律責任判斷或後續 Compliance 已實作。
