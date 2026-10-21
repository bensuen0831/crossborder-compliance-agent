# G1 MASTER Requirement Reconciliation

準備日期：2026-10-21T04:10:03.812889+00:00。PR [#29](https://github.com/bensuen0831/crossborder-compliance-agent/pull/29)，Product Head `39c3581ca455df4e3ce9760ed2deab8905a5f588`，Main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`。本材料屬 AI 審查協調與工程建議，不是正式 Reviewer Approval，也不代表風險接受或合併授權。G0 Evidence `1193eb35096806fc0f885c0181de98b87d61980a` 與先前技術驗收 `bd30290c577e8ac16cbb88a20a0535553fb6bd00` 均為獨立證據身份。

`MASTER_FULL_TEXT_RECONCILIATION = INPUT_REQUIRED`

`FORMAL_REQUIREMENT_CHANGE_APPROVAL = NOT_VERIFIED`

使用者明確確認：MASTER V2.0 原文由本項目 ChatGPT 對話編寫，整合先前 MASTER/R4/R5/R6/R7；目前沒有可確認包含完整原文的 repo 文件，也未提供獨立變更批准文件、批准人、批准日期與簽核。這項澄清是輸入狀態確認，不是補簽原需求變更或風險處置。

`D0_requirement_traceability.md`、`D0_gap_matrix.md`、`architecture_design.md` 只作輔助追溯。舊文中的 pending/PR不存在等內容屬歷史狀態，不取代當前 GitHub；其標題也不使其成為原文。G0 16 個技術領域 VERIFIED 不代表 MASTER 原文逐字／逐 clause 完整覆蓋。

## 待與原文核對的清單

| 輔助 ID | 要核對的能力 | 現有證據狀態 | 完整原文比對 |
|---|---|---|---|
| G0-REQ-01 | 國家／地區 CRUD、alias、merge、停用 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-02 | 法規類型 CRUD、層次、重分類 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-03 | 文件 CRUD、版本、受保護刪除、bulk archive | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-04 | 國家→類型→文件動態管理 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-05 | 本地單檔／多檔／資料夾上傳 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-06 | 500MB+ 單檔及 RAR4/RAR5/ZIP 1GB+ | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-07 | 恢復／重試／取消／部分失敗／配額 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-08 | 不依賴 Excel 導入；可選 CSV/XLSX Manifest | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-09 | DOC/DOCX/HTML/PDF/TXT/XHTML 解析與 OCR | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-10 | 資料庫持久化與 canonical 知識儲存 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-11 | 搜尋／篩選／排序／分頁／預覽 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-12 | 分類計數、統計與交叉維度 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-13 | 審查／批准／發布／Runtime READY | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-14 | 法條、原文 Citation、歷史精確版本 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-15 | 租戶／權限／審計／上傳及壓縮檔安全 | Existing G0 technical evidence | INPUT_REQUIRED |
| G0-REQ-16 | F0 專家／Gold Standard／驗收準備 | Existing G0 technical evidence | INPUT_REQUIRED |

逐項 owner、test IDs、固定 G0 evidence refs 及輔助文件 SHA256 見 [requirement_reconciliation.json](../../../evidence/stage1-gap-kb01/g1/requirement_reconciliation.json)。原文 clause 與原文 hash 刻意留 null；沒有重建不存在的 MASTER 全文或臆造簽核。16 行是整理清單，不能證明原文不存在其他條款。

## 需核對的量化與邊界

G0 保留單檔 540006868 bytes、RAR4 1080013875、RAR5 1080013864、ZIP 1080014006 的真實容量紀錄與 exact-source browser originals/download hashes；原文到齊後仍需確認每種格式、閾值、並行、恢復與 UI 要求的完整措辭。資料夾／無 Excel import 與 optional manifest 必須分開核對，不把可選 Excel 改成依賴。六格式不代表所有語言／OCR／掃描品質都已取得真實法律驗收。

F0 readiness 只能證明工程流程；F1 缺授權原始資料、來源版本有效性、專家 Gold Standard、正式審核紀錄及案例／標準。沒有 1026 真實文件身份清冊或真實公司 UAT 批准的獨立證據，不能從合成 fixture 推定。Production identity/session/CSRF、正式部署與運維另有未驗收邊界。

完成 Gate 所需材料：可讀完整原文及其版本／hash；正式變更清單、舊／新條款、批准者與授權、批准日期／記錄；之後建立 original clause→change→implementation→test/evidence→gap 的逐項對照，由指定 Reviewer 確認。當前未提供，保留 INPUT_REQUIRED，其他 G1 材料照常完成。

## D0 輔助矩陣 18 行逐項保留

下表額外保留既有 D0 全部 18 行，避免只以 G0 的 16 個領域代替需求追溯。每行仍為 INPUT_REQUIRED；尤其 KB01-14/15 的真實法律與多角色／多法域驗收，不能被工程機制 PASS 覆蓋。

| D0 ID | 輔助原措辭（非 MASTER 原文） | G0 關聯／邊界 |
|---|---|---|
| KB01-01 | Country/territory/supranational/sub-jurisdiction CRUD, aliases, merge, deactivate/reactivate | G0-REQ-01；Technical evidence only; original full text not compared |
| KB01-02 | Dynamic shared category CRUD, hierarchy/order/merge/reclassification | G0-REQ-02；Technical evidence only; original full text not compared |
| KB01-03 | Document CRUD/version/eligible deletion/bulk archive | G0-REQ-03；Technical evidence only; original full text not compared |
| KB01-04 | Local six-format single upload>=500MB | G0-REQ-05, G0-REQ-06；Technical evidence only; original full text not compared |
| KB01-05 | Local multifile upload/common or per-item metadata | G0-REQ-05；Technical evidence only; original full text not compared |
| KB01-06 | Local folder upload/preserved paths | G0-REQ-05；Technical evidence only; original full text not compared |
| KB01-07 | RAR4/RAR5/ZIP, both RAR/ZIP>1GB | G0-REQ-06；Technical evidence only; original full text not compared |
| KB01-08 | OPTIONAL mapped XLSX/CSV; file/folder/archive-only import must work | G0-REQ-08；Technical evidence only; original full text not compared |
| KB01-09 | Six-format/multilingual/RTL/OCR/clause parser | G0-REQ-09；Technical evidence only; original full text not compared |
| KB01-10 | Canonical database persistence/recovery | G0-REQ-10；Technical evidence only; original full text not compared |
| KB01-11 | Technical stages separate from governed review/publish/READY | G0-REQ-13；Technical evidence only; original full text not compared |
| KB01-12 | SQL dynamic counts, distinct documents/versions/files/manifest and cross-tabs | G0-REQ-12；Technical evidence only; original full text not compared |
| KB01-13 | Exact source version/run/object/article/citation provenance | G0-REQ-14；Technical evidence only; original full text not compared |
| KB01-14 | Genuine approved source integration with formal applicability/obligation owners | G0-REQ-16；F1/legal expected outcome and multi-subject coverage remain external/unaccepted |
| KB01-15 | Source/destination/processing/storage jurisdiction comparison | G0-REQ-14, G0-REQ-16；F1/legal expected outcome and multi-subject coverage remain external/unaccepted |
| KB01-16 | Production auth/CSRF, operation RBAC, tenant/resource audit/security/holds | G0-REQ-15；Production identity/session/CSRF/deployment not accepted |
| KB01-17 | Multipart/quotas/leases/restart/partial retries/cleanup/capacity | G0-REQ-07；Technical evidence only; original full text not compared |
| KB01-18 | Old mandatory IDs + new exact-head technical CI, Draft PR/no merge | Exact-head CI/Evidence；Exact-head CI/evidence is separately reverified, not a new full G1 rerun |
