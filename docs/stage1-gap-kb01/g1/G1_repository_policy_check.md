# G1 Repository Policy Check

準備日期：2026-10-21T04:10:03.812889+00:00。PR [#29](https://github.com/bensuen0831/crossborder-compliance-agent/pull/29)，Product Head `39c3581ca455df4e3ce9760ed2deab8905a5f588`，Main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`。本材料屬 AI 審查協調與工程建議，不是正式 Reviewer Approval，也不代表風險接受或合併授權。G0 Evidence `1193eb35096806fc0f885c0181de98b87d61980a` 與先前技術驗收 `bd30290c577e8ac16cbb88a20a0535553fb6bd00` 均為獨立證據身份。

**REPOSITORY_POLICY_VERIFICATION_PENDING**。觀測時間 `2026-10-21T11:56:32.100278+08:00`，詳見 [repository_policy_snapshot.json](../../../evidence/stage1-gap-kb01/g1/repository_policy_snapshot.json)。

| 檢查 | 實際讀取結果 | 可下的結論 |
|---|---|---|
| PR29 | OPEN、Draft、未 merged、mergeable=true | 技術上可合併不是批准 |
| Reviews / review comments / pending requests | 空；reviewDecision null，reviewThreads 無項目 | 無正式批准、無待辦 request |
| Main branch endpoint | protected=false；可讀 protection summary 無 checks | 僅 endpoint 觀測 |
| Legacy branch protection endpoint | HTTP403 Resource not accessible by integration | 完整設定無法核實，不能解釋為無規則 |
| Applicable rules / rulesets incl. parents | 可讀結果均 [] | 不填補 403 的可見性缺口 |
| GraphQL branchProtectionRule | null | 不作全域無保護結論 |
| CODEOWNERS | main/product 的 .github/CODEOWNERS、CODEOWNERS、docs/CODEOWNERS 均無檔 | 不能據此認定不需要正式 review |
| Merge method flags | merge commit=true；squash=true；rebase=true；auto-merge=false | 能力旗標，不是本任務合併授權 |
| Required Approvals / Required Status Checks | UNKNOWN / Pending authoritative verification | 不填 0，不把 12 technical workflows 當 server-enforced setting |

即使 repo 回傳部分 admin/maintain/push 能力，也不能繞過 endpoint 403、branch protection 或使用者授權邊界。本輪不變更 policy、不用 admin bypass、不提交 review、不安排 reviewers、不轉 Ready。

由 Authorized Maintainer 核實完整 policy：main 適用的 legacy protection、org/repo rulesets、required approval count、CODEOWNER requirements、stale approval dismissal、last-push approval、required status contexts/apps、merge queue／方法、例外與獨立性規則。提供具時間、repo/ref、rules applicability 的受控 export 或截圖／紀錄；不要求在 evidence 存 token。確認後與最新 head 的 review/CI 逐項核對。

審查角色可兼任須有正式任命、能力、獨立性且 policy 允許；不預設四人或四個 GitHub approval。PR 作者 `bensuen0831` 的身份不能用來冒充獨立 Reviewer。若產品 head 更新，重新檢查 approval validity 與完整 CI；merge authorization 須另行明示。
