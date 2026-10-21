# G1 Formal Reviewer Package

準備日期：2026-10-21T04:10:03.812889+00:00。PR [#29](https://github.com/bensuen0831/crossborder-compliance-agent/pull/29)，Product Head `39c3581ca455df4e3ce9760ed2deab8905a5f588`，Main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`。本材料屬 AI 審查協調與工程建議，不是正式 Reviewer Approval，也不代表風險接受或合併授權。G0 Evidence `1193eb35096806fc0f885c0181de98b87d61980a` 與先前技術驗收 `bd30290c577e8ac16cbb88a20a0535553fb6bd00` 均為獨立證據身份。

結論：**AWAITING_FORMAL_REVIEW**。PR 維持 Draft；程式、測試、Migration、Main 與 Release Tag 均未更改。

## 固定來源與實際 Diff

[固定比較](https://github.com/bensuen0831/crossborder-compliance-agent/compare/060cbb5a20a9f8f70fa88dbefb8b5feb404c460d...39c3581ca455df4e3ce9760ed2deab8905a5f588)：285 檔，Git 實測 +61097 / -307；production 74、frontend 44、tests 34、CI/tools 25、alembic 5、docs/evidence/config 103。這是路徑分類；alembic 5 檔包括環境接線與四個 revision，並非五個 migration。

完整 285 檔的 base/head blob、SHA256、行數及分類見 [pr_diff_inventory.json](../../../evidence/stage1-gap-kb01/g1/pr_diff_inventory.json)。所有檔案的 GitHub 路徑與 product blob 完全一致。18 個 evidence JSON 的 API 行數為零且沒有 rendered patch，但本地 Git 有內容；不得據此略過審查。API 省略原因未證實。

可重現的完整 diff：

```bash
git diff --binary 060cbb5a20a9f8f70fa88dbefb8b5feb404c460d 39c3581ca455df4e3ce9760ed2deab8905a5f588
git diff --name-status 060cbb5a20a9f8f70fa88dbefb8b5feb404c460d 39c3581ca455df4e3ce9760ed2deab8905a5f588
git show 39c3581ca455df4e3ce9760ed2deab8905a5f588:scripts/kb01/Containerfile
```

第一條輸出 SHA256 `ae0f16383711fe24f9cc1cd17e05fc29450b5a0a4684eb402ef34ecff1b056f5`，3611946 bytes。需從具備這兩個物件的 clone 執行，不以 PR 頁面顏色取代來源核對。

## 依 Owner 分配審查

| 範圍 | 變更與重點 | 獨立參考 |
|---|---|---|
| Metadata / Jurisdiction | taxonomy CRUD、alias、版本、標籤；merge 不重綁歷史 scope；list N+1 尚待處置 | [G0 架構](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_architecture_review.md)、[Finding 處置](G1_medium_findings_disposition.md) |
| Knowledge / Document | 保留單一 source/document/version/structure/citation owner；刪除依賴、hold、retention、CAS | [G0 知識治理](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_knowledge_governance_review.md) |
| Upload / Batch / Parser | 六格式、大檔 multipart、RAR4/RAR5/ZIP、原件精確版本、隔離轉換、manifest 可選 | [G0 Upload](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_upload_archive_review.md) |
| DB / Temporal | 0021–0024；複合 tenant FK、immutable receipt、拒絕破壞性 downgrade | [G0 Migration](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_database_migration_review.md) |
| UI / Stats | 三語系管理、階層、篩選、動態 SQL 統計；列表效率與 counts 正確性分開評估 | [G0 Frontend](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_frontend_crud_review.md) |
| Security | RepositoryContext、operation grants、tenant/resource boundary、scanner fail-closed、parser sandbox | [G0 Security](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_security_review.md) |
| F0 readiness | 來源核驗、專家任命與 Gold Standard typed record；不能生成真實 F1 批准 | [G0 Traceability](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_requirement_traceability.md) |

## Schema 與遷移

| Revision | Parent | 影響及 downgrade 邊界 |
|---|---|---|
| 0021_kb01_taxonomy_operations | 0020 | taxonomy operations/tenant labels、operation receipts、hold；不得丟失治理審計 |
| 0022_kb01_binary_transport | 0021 | multipart/attachments/batch/items；保留原件、租戶 FK 與 immutable receipts |
| 0023_kb01_evidence_source_reference | 0022 | source_ref lossless Text 擴展、32768-byte guard；>500 字元回退拒絕；md5 僅 non-unique 查找索引 |
| 0024_kb01_import_manifest_records | 0023 | batch 內 immutable manifest proposal/records/mapping；拒絕證據丟失回退 |

單一 head 為 `0024_kb01_import_manifest_records`。G0 已在真實 PostgreSQL 重跑 fresh、exact predecessor、schema equivalence、舊 rows 保存、安全 downgrade/re-upgrade、unsafe refusal；完整測試 ID 與 matrix 見 [migration_review.json](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/evidence/stage1-gap-kb01/g0/migration_review.json)。G1 重算 0001–0020 與 main 的 byte identity，以及 0021–0024 source hashes；另在隔離效能 DB fresh upgrade 0024。G1 未重跑完整 migration matrix，亦不宣稱 production backup/restore 驗收。0002 歷史 bootstrap 會 import runtime metadata，精確前序測試使用 committed Git blobs 重建；此限制保留。

## 測試與 Exact-head 證據

| Scope | 結果與限制 |
|---|---|
| 既有完整 PostgreSQL | 每次 1315 PASS，共四次完整執行；各次 failed/errors/skipped/deselected = 0 |
| 既有補充 contract subset | 676 PASS / 7 skipped / 632 deselected，獨立披露，非完整 suite |
| 既有完整 Browser | 88/88、retries 0；77 retained + 11 KB；12 outcome × locale 保留 |
| Architecture / Runtime / Frontend | 456/456、25/25、180 PASS；typecheck/lint/build/i18n PASS |
| G0 獨立重跑 | KB PostgreSQL/security/migration 303、adversarial 12、historical 24；architecture 456、runtime 25、frontend 180 |
| G1 新核查 | 12/12 workflows SUCCESS、22/22 actual checkout/log digest 與 source `39c3581ca455df4e3ce9760ed2deab8905a5f588` 一致；731 source hashes、27 G0 review hashes 重算；24 次 taxonomy 讀取與本地 SBOM |

G1 沒有重新 dispatch 或重跑 1315/88；未變更產品，引用的是同一 source 的既有完整技術驗收。先前 131 technical evidence hashes、27 artifact ZIP / 191 retained members 的完整性鏈見 [G0 integrity](https://github.com/bensuen0831/crossborder-compliance-agent/blob/1193eb35096806fc0f885c0181de98b87d61980a/docs/stage1-gap-kb01/g0/G0_evidence_integrity_review.md)。早期失敗、setup recovery、capacity/race diagnostics 均保留；沒有把局部復現當成遠端歷史失敗根因。

本次逐 job 的 run ID、attempt、checkout SHA、log SHA256、URL 見 [ci_identity.json](../../../evidence/stage1-gap-kb01/g1/ci_identity.json)。12 個 technical mandatory workflows 的 PASS 不等於 GitHub branch-protection Required Checks 設定已核實。

## 尚待正式判斷

閱讀 [Medium 處置方案](G1_medium_findings_disposition.md)、[MASTER 比對](G1_master_requirement_reconciliation.md)、[政策核查](G1_repository_policy_check.md)、[批准矩陣](G1_reviewer_approval_matrix.md)。兩項 Finding 仍 OPEN，工程建議 pre-merge fix，但無已批准 FIX/ACCEPT/DEFER/BLOCK 決策，也沒有執行產品修復。

F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Knowledge / Production UAT / Paid Internet LLM = NOT EXECUTED。F0 技術機制不能代替來源、獨立專家答案與正式批准。Main merge NOT AUTHORIZED；Tag unchanged；Stage 2 NOT STARTED。
