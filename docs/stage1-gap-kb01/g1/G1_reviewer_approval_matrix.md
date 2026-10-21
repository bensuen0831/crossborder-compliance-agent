# G1 Reviewer Approval Matrix

準備日期：2026-10-21T04:10:03.812889+00:00。PR [#29](https://github.com/bensuen0831/crossborder-compliance-agent/pull/29)，Product Head `39c3581ca455df4e3ce9760ed2deab8905a5f588`，Main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`。本材料屬 AI 審查協調與工程建議，不是正式 Reviewer Approval，也不代表風險接受或合併授權。G0 Evidence `1193eb35096806fc0f885c0181de98b87d61980a` 與先前技術驗收 `bd30290c577e8ac16cbb88a20a0535553fb6bd00` 均為獨立證據身份。

使用者確認尚未正式指定 GitHub Reviewer 或授權範圍。以下是建議分工，不是任命；所有 username、approval、authorization scope 均 `PENDING_USER_CONFIRMATION`。

| 建議角色 | 審查職責 | GitHub username | Approval status | Authorization scope |
|---|---|---|---|---|
| Technical / Architecture Reviewer | 架構、Canonical Source of Truth、API、資料庫遷移、歷史相容性 | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION |
| Security Reviewer | RBAC、Tenant Isolation、上傳、RAR/ZIP、Parser、依賴安全 | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION |
| QA / Release Reviewer | 需求覆蓋、完整回歸、Exact-head CI、Evidence Integrity | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION |
| Authorized Maintainer / Merge Approver | Repository Policy、必要審批、正式合併授權 | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION | PENDING_USER_CONFIRMATION |

正式審查應各自記錄：任命／授權來源、獨立性、review ID/URL、審查 commit SHA、時間、決定、Finding 處置、條件及 outstanding comments。現在所有批准 ID、日期、approved_by 與記錄均為 null，沒有用 AI 或 synthetic 測試身分代簽。Live reviews=[]、requested_reviewers=[]、requested_teams=[]；未發出任何 Review Request。

Technical Reviewer 應核對 migration 四個 revision 與 temporal/canonical owners；Security Reviewer 應決定 parser/toolchain最低控制並核查 upload/archive 隔離及 tenant/rbac；QA/Release 應核對完整 MASTER、test IDs、source/evidence hashes與 checkout；Maintainer 應補完整 policy、必要批准有效性與最終授權。不能以 mergeable=true 替代任一責任。

可由同一人兼任多角色，前提是正式確認授權、獨立性與 policy。實際 required approval count 尚未核實，不在此自行設定。收到人員名單也不自動改為 Ready；目前明確要求 PR29 保持 Draft。正式 Review Request 與轉 Ready 需適用授權，merge 更須另行批准。

機器紀錄：[reviewer_status.json](../../../evidence/stage1-gap-kb01/g1/reviewer_status.json)。
