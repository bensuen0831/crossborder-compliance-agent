# 本輪 owning-contract 與驗收條件核對

基準：產品733a748、V3.7 Master（repository 同名完整文件）、ARCHITECTURE_RULES、既有 F0/F1 definition。KB01-MASTER V2.0 原始全文與正式變更簽核仍未在 repository 找到；本文件**不聲稱**完成其全文一致性比對或正式批准。相應 Gate 維持 INPUT_REQUIRED / NOT_VERIFIED。

| 要求位置／原文摘要 | 適用與實作 | 本輪證據／差異 |
|---|---|---|
| V3.7 §0.4 Structured Input 優先、RAG/RULE/EVIDENCE-FIRST | 不修改 LLM Gateway、legal owners 或 rules；新 Host 只組裝 canonical routers | scoped auth / zero-provider fail closed；未有真實法規／模型，正式業務鏈未驗證 |
| V3.7 §0.3 Snapshot/temporal，Architecture19/82 | 沿用 R1 preparation→user decisions→Confirm；不 seed Snapshot 或 default runtime contexts | 結構與既有 owner 保留，完整 real case 尚未執行 |
| Architecture25/26/68/76 Single authority / channel | `business_host.py` 直接組裝 workflow_app router + main lifespan；S3/FileObjectStorage / SecretStore 為既有 adapter | 不匯入 tests/fixture Host，不做 dependency override，不建立新 store/runtime/schema |
| Architecture45 jurisdiction-scoped classification | `Stage1Workspace.tsx` 原先 find 僅顯示一筆；改為顯示同 subject 全部 jurisdiction 結果 | 新 frontend regression 保留兩法域、分類／level、原 JSON 及 zero writes；法律算法未改 |
| Architecture61/62 原文引用與來源追溯 | 沿用 KnowledgeVersion / structure / SourceTrace 與 ResultWorkspace | 真實來源未提供；不能由 UI 存在推論引用準確性 PASS |
| Architecture83 / Phase1K-B Secret boundary | 私密600帳號／加密SecretStore；API/provider credential 保持write-only | 未配置任何 API Secret；ChatGPT 訂閱不可替代；無即時模型或 token measurement |
| KB01 security / human review | 上傳政策經既有 Metadata review/publish，真實 scanner 與 isolated workers | native130H1C及舊掃描不被接受；worker / project upload held。沒有正式安全豁免 |
| F0/F1五類條件、獨立 actor/date/approval | 新 F1 panel 只匯入 L2 draft，調 canonical F0 read/transition/readiness | 未提供 appointment、source verification、Gold；不提交專家批准 |
| V3.7對外五階段、強制可視化 | 原有 WorkStepper/ResultWorkspace/Risk/Path/RequiredDocuments 重用 | 本輪不重設 stage aggregation 或以非關鍵色碼擴張 scope；使用者完整語義驗收仍須真實案例 |
| 部署／身份／啟停 | 僅 loopback 的隔離本機入口；offline account provisioning、current server grants、same-origin session | 非 production SSO、不公開服務。重啟保留資料不等於異機還原／長期Registry acceptance |
| Stage2 boundary | 不改 generation_available，不增生成／合同流程 | Stage2 NOT_STARTED；main/tag/PR29 Draft 狀態不變 |

本輪新增 finite ownership overlay v23 僅涵蓋明列入口、UI、測試與 checker 路徑。所有 v1–v22 manifests 保留並由原 seal Git blobs 核實；新增 proof 由已提交 source blobs 產生，不以工作檔 hash 自證。這是使用者本輪任務的有限修改範圍紀錄，不是正式 Reviewer 的 risk acceptance，也不代替缺少的 KB01-MASTER 原文。

安全、法規、模型、Gold、正式法律準確性、Production Acceptance 分開判斷。UI/preflight 固定為 BLOCKED 的欄位是當前不具備測量的保守狀態，不是可以由使用者勾選的通過旗標；後續完整實測後才可接入有版本與來源身份的 readiness evidence。
