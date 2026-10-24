# RC1 合成測試角色

沒有預設密碼，透過僅限 loopback 的 synthetic login/session cookie。兩個 safety flags `M0_LOCAL_UAT=1` / `KB01_LOCAL_UAT=1` 由 RC1 launcher 設定；缺任何一個即拒絕啟動。角色按鈕另限 `VITE_M0_DEMO=true` / `VITE_KB01_UAT=true`，不是生產 login。

| UI / persona | 範圍 | 不可做 |
|---|---|---|
| A / AUTHOR | Tenant A，建立、編輯、上傳、送審、分類與管理 | 新 KB governance approve/publish |
| B | 另一個 synthetic tenant 的 Author | 讀取／變更 Tenant A 的真實 IDs |
| REVIEWER | 與 A 同 tenant，不同 actor；核准分類／文件 | Author write、Publisher publish |
| PUBLISHER | 與 A 同 tenant，不同 actor；publish | Author write、Reviewer approve |
| RESTRICTED | 同 tenant、空 operation scopes | 所有受保護 KB 操作 |
| PROJECT | 保留的既有 Project UAT persona | 不作 KB 管理員 |

UI 上 A 按鈕仍沿用既有名稱（UAT user A）；按 Reviewer/Publisher/Restricted 切換會清除舊 QueryCache。伺服器從 private persona manifest 建 RepositoryContext，不信任 client tenant/actor/grant payload。Cookie 一小時失效，重啟需重新登入，但業務資料保留。

這些是隔離工程測試身份，不是正式 PR Reviewer、法律專家或 Production IAM。Synthetic demo 的 canonical review/publish 不代表正式 Reviewer Approval。

版本：`KB01-Technical-UAT-RC1`。只限 `LOCAL / ISOLATED TECHNICAL TESTING ONLY`。使用既有 React 前端、UAT Host、PostgreSQL、Redis、versioned S3 與 canonical Workers；不是 Production Auth，也不提供公開網址。

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Acceptance / Production UAT / Paid Internet LLM = NOT EXECUTED；Reviewer Approval = Pending；MASTER reconciliation = INPUT_REQUIRED；PR29 Draft；Main merge 未授權；Release Tag 不變；Stage2 NOT STARTED。
