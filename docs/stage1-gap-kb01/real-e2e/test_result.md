> 本報告主體為上午893c4a2的歷史實測；最新產品e7efe53、恢復作業、安全重掃及政策頁修復見 [接續執行紀錄](resumption_and_next_gates.md)。下列舊Head結果不可當作新Head完整回歸。

# 真實法規與即時模型 E2E 就緒：本輪實測報告

**用戶尚不能開始所要求的完整 E2E。** 可操作的是本機業務入口與管理介面；真實原檔處理、即時模型、獨立法律答案及正式安全條件尚未齊備。沒有執行第一個完整真實法規／模型案例，也沒有法律準確性 PASS。

產品 branch：`feat/stage1-real-e2e-readiness`；Head：`893c4a2ac3e126607aeaad91ad1dce69c77f958d`；[Draft PR #30](https://github.com/bensuen0831/crossborder-compliance-agent/pull/30) 疊於 PR #29 的產品733a748。PR #29 仍 Draft，Head733a748不變；main060cbb5與正式 release tag 不變。獨立 evidence branch：`evidence/stage1-real-e2e-893c4a2`，其文件提交不是產品 SHA。

## 現在的入口與實際交付

上午實測入口為 `http://127.0.0.1:15174/intake`，後端 `http://127.0.0.1:18011/health/live`；當時重啟後兩者200，PostgreSQL readonly與Redis PASS。2026-10-26 15:56（香港時間）重新檢查時，前後端與PG／Redis均不可用，受管PG／Redis容器已停止；當前不能沿用上午200作服務運行證明。它們不是外部可存取網址；沒有公開 Cloud URL。用戶須先 checkout `feat/stage1-real-e2e-readiness`（核對 Head893c4a2），再在自己的隔離主機按 [README](README.md) 啟動；不要在 RC1 安裝步驟切回缺少新啟動器的舊分支。使用自己離線設定的帳號／密碼登入，不能用其他電腦開啟 Cloud 的 loopback。

- 新 Host 使用正式應用的 canonical routers / lifespan、RepositoryContext、PG、S3、Document storage及加密 Secret Store。沒有 fixture imports、預種法律設定／結果、system身份或 dependency override。
- 伺服器擁有 tenant、actor與角色權限；新增本機密碼登入、session撤銷、同源／Host檢查、rate limit及安全錯誤回應。實測普通業務身份不能存取模型後台，客戶端 header 不能注入權限。
- 前端可建立空白項目、重載與重登、進入模型設定、法規檔案選擇、技術 upload-policy 管理、F0 真實驗收草稿及明確版本讀取／治理介面。上傳政策缺失會明確拒絕，沒有假成功。
- 原檔處理接線使用既有 genuine scanner與隔離 parser/worker；目前工具有未處置 High/Critical，worker不啟動、業務上傳不放行。沒有 clean scanner 或 permissive policy替代。
- 同一 DataItem 的多 jurisdiction分類改為全部顯示，修正原 UI 只顯示首筆的問題；不改法律計算、結果DTO或資料庫。
- 第一例的 [非敏感需求與待填manifest](case-01/input_manifest.json)、未批准的安全上傳政策payload與 [用戶測試清單](case-01/review_checklist.md) 已提供。尚無真實法域、法規或法律預期，不預設出境結論。

## 本輪新執行：精確產品 Head893c4a2

| Gate | 實測 | 限制 |
|---|---|---|
| 重點 PostgreSQL／來源／F0回歸 | **78 PASS**，0 failed/errors/skipped/deselected | 四個明列檔案，**不是全 repository backend suite**；含13個新入口／身份測試 |
| 既有九組架構 authority | **456/456 PASS** | checks未刪減；新增有限v23 proof由 committed Git blobs產生，保留v1–v22 |
| 完整 frontend unit suite | **181 PASS**，0 failed/pending | 包含新增雙法域分類／原JSON不變／零寫入測試 |
| typecheck / lint / build / i18n | **PASS** | zh-CN、zh-HK、en-US；原有大bundle警告保留，未放寬門檻 |
| Chromium入口／身份／空白draft／重登／管理介面 | **3/3 locale PASS**，Retries0 | 0意外JS/console/5xx；未配置上傳政策的503是明確負面驗證；**不是完整法律業務旅程** |
| 同機stop/start及draft讀回 | **PASS**，前後canonical JSON hash相同 | 不是異機還原或正式部署接受 |
| Migration identity | 0001–0024 byte-identical、single head0024 | 沒有schema變更；未重跑fresh/upgrade/downgrade矩陣 |

沒有在本機重跑／繼承為本Head PASS：全Backend1336、Runtime25、既有Browser89及六格式／容量native回歸。2026-10-26重新讀取GitHub：12組remote CI中11 SUCCESS、1 CANCELLED，22/22實際job checkout均匹配893c4a2。Phase1KB run40263233199的mandatory-backend明確超過90分鐘上限；該job的完整pytest已1352 PASS，但後續檢查未全部完成，不能宣稱12/12 PASS。見 `remote_ci_references.json` / `remote_ci_snapshot.json`，沒有借用舊Head結果。既有733a748的完整結果與22checkout/12CI只在 `historical_evidence.json` 作歷史參考。本輪產品沒有修改法律owner、Runtime或native依賴；完成適用的重點回歸，不宣稱全量Release Closure。

初期環境／來源／測試driver失敗已保留於 `diagnostic_history.json`：停用的舊PG5432已改用既有受管PG17；測試中修改診斷檔造成的4個ownership拒絕，在封存後完整重跑78；直接刪Cookie導致尚在執行的parties請求401，改走實際UI登出取消查詢；CJK兩字按鈕的展示空格改以完整翻譯文字容許空白匹配。沒有對parties401增加豁免、沒有降低斷言或增加瀏覽器重試。尊重每帳號每分鐘5次登入的節流等待不是assertion retry。

## 安全及供應鏈

沿用工具 image config：`sha256:35765d74c83509652f2a7c5112fb983ec2398e1709a05f144177a12a16321e19`；OCI manifest：`sha256:07be6daf20dbe2feb33424afa26466421783d95504487e7ffd8548cb3064b61c`；284-package SPDX2.3 SBOM與原始scan/OCI hashes見 `native-security.json`。本輪重新核對其身份與來源，**未重建映像或重新掃描**，不把舊scan描述為新報告。API／前端是host process，不在工具映像SBOM的完整審查範圍。

歷史459報告134 High／1 Critical；現保留733工具報告130 High／1 Critical，共131筆套件findings、45個unique CVE、此本機scan一個image config，不能稱為131個獨立漏洞。本輪未修復／消除任何finding，也未新增掃描結果。

Critical `CVE-2026-6653`，libxml2 `2.12.7+dfsg+really2.9.14-2.1+deb13u3`。2026-10-26重新取得Debian官方tracker，trixie仍vulnerable、forky/sid另列fixed；沒有證據可把unstable ABI直接混入現有受支援工具鏈。原報告沒有列出修復版。需要Dependency Maintainer選定vendor-supported backport／base遷移，實測parser/scanner相容性、六格式／引用／安全／容量，固定重建與fresh scan，再由正式Reviewer處置適用版本的剩餘問題。sandbox和「工具映像」身分不等於風險接受。

本機technical preflight採保守零High/Critical且24h內報告，仍不代表正式Security Approval。若未來採正式批准的限期例外，還需可核實scope／版本／期限的適配，不得手改scan或自行勾選批准。正式安全審查仍PENDING。

## 外部材料、責任方與下一個動作

1. **API／額度負責人**：設定既有已授權Provider、model/deployment、伺服器API Secret、額度及資料邊界。用戶本輪已授權最小即時調用，但ChatGPT登入／訂閱不能作後端API憑證；沒有抽取Cookie、沒有呼叫獨立chat冒充工作流。接入後先量測一次非cache的業務候選抽取，串接request/preparation/project/snapshot/run，脫敏保存用量與耗時。
2. **授權上傳者及法域專家**：提供真正原檔、官方來源、版本／適用日、修訂與廢止關係，安全解除後由介面匯入、核實、review/publish/index；既有分類／規則／binding／path政策亦需對該scope有效。上傳文字不會自動成為已批准法律規則。接著驗證原文引用及RAG Evidence。
3. **Dependency Maintainer與實際Security Reviewer**：處理上述Critical／High與所需原檔處理安全條件。沒有自行接受豁免；既有合成測試許可沒有擴張為真實資料批准。
4. **項目負責人及獨立專家**：正式任命及授權法域、來源／有效性verification、預先批准的Gold／理由、identity/date/version/approval及評估標準。沿用F1五類條件，不以模型答案／模板／合成專家替代。材料到齊後執行實際完整比對與差異處置，目前NOT_EXECUTED。

新租戶readonly inventory目前為0 Provider、0 Deployment、0 KnowledgeVersion、0 Snapshot及0 F0紀錄；沒有把舊RC1另一租戶的ACTIVE數量誤認為已核實真實法規。原KB01-MASTER V2.0全文及正式變更簽核仍未可核實，本輪也嘗試讀取歷史上傳但不可授權／解析；完整全文比對維持INPUT_REQUIRED。V3.7與本輪資料契約／引用／Snapshot／結果解讀差異核對見 [contract_reconciliation](contract_reconciliation.md)。

長期Registry保存與獨立主機還原屬既有運維驗收依賴，不是新增的F1法律條件，也不能被同機restart取代。用戶實際操作及Production UAT沒有被自動化PASS代替。

材料、已批准治理配置及安全修復就緒後，單一案例的設定、串接與驗證暫估**8–16工程小時**；不含供應商／base修補、重新建立法律配置、正式專家審核及外部等待。上述外部等待目前沒有可承諾日期；維持原本1日首例／2–3日法律比對為條件式目標，不虛報已完成。

```ini
BUSINESS_UI_E2E = BLOCKED
BUSINESS_ENTRY = OPERABLE_LOOPBACK_ONLY
REAL_REGULATORY_DATA = BLOCKED
LIVE_MODEL_WORKFLOW = BLOCKED
LEGAL_GOLD_AND_CRITERIA = BLOCKED
LEGAL_ACCURACY_EXECUTION = NOT_EXECUTED
USER_E2E_TEST_READINESS = BLOCKED
FORMAL_SECURITY_ACCEPTANCE = PENDING_BLOCKED_REVIEW_REQUIRED
KB01_F1 = BLOCKED_EXTERNAL_EVIDENCE_PENDING
PRODUCTION_BUSINESS_UAT = NOT_EXECUTED
STAGE2 = NOT_STARTED
```

證據索引：`evidence/stage1-gap-kb01/real-e2e/readiness_validation.json`、`source_identity.json`、`backend_validation.json`、`frontend_validation.json`、`architecture_validation.json`、`browser_entry_validation.json`、`restart_validation.json`、`native-security.json`、`f1_dependency_checklist.json`、`diagnostic_history.json`及`evidence_digests.json`。產品已推送；上次證據留在獨立worktree而未形成commit，本次在正確證據分支封存。沒有main merge、tag、release、Review Request或正式批准。

PR描述更新曾遇到舊版gh CLI的Projects Classic GraphQL棄用錯誤，改用原生REST PATCH成功；沒有繞過權限或repository policy。
