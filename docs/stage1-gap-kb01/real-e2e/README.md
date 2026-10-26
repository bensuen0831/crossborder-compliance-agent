# Stage 1 真實法規／即時模型驗收入口

本輪交付的是獨立的本機隔離業務組裝，重用 canonical Intake、Candidate Governance、Workflow、Review、Result、Knowledge 與 LLM Gateway；不使用 Stage1 合成 fixture Host、不 seed 法律結果、不覆寫依賴或使用 system 身份。它不是正式生產身份服務，也不是已完成的真實法律 E2E。

目前可測：登入、空白業務項目建立及保留資料重登、業務／審核路由、模型設定、法規檔案選擇、F0 紀錄匯入及版本讀取入口。**完整業務 E2E 尚不可開始**：新租戶沒有已發布上傳政策、真實法規及相應正式 metadata/rules、授權模型 API 憑證或獨立專家 Gold；工具映像安全問題亦未解除。介面會顯示阻塞，不能藉由健康檢查、模板存在或 ChatGPT 訂閱聲稱模型／法律驗收通過。

## 安裝及啟停

支援基礎環境沿用 RC1 的 Linux amd64、Python 3.12、Node >=22.12、Docker、PostgreSQL、Redis、versioned S3 及固定工具來源。先依 [RC1 installation guide](../uat/RC1_installation_guide.md) 準備**專用的既有服務 state**。不需要執行 `rc1.py demo`；不得把其合成租戶或測試角色作真實驗收。現有服務可共享同一隔離資料庫實例，但本入口新建不同 Tenant、S3 bucket、文件目錄及身份檔，不複製既有知識或政策。

在 repository 根目錄、已安裝 `.[dev]` 及 `frontend/npm ci` 的環境中：

```bash
export PYTHONPATH=src:.
python scripts/kb01/business.py init --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1
python scripts/kb01/business.py account --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1 --username business-user --role business
python scripts/kb01/business.py account --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1 --username knowledge-operator --role knowledge-author
python scripts/kb01/business.py account --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1 --username configuration-reviewer --role configuration-reviewer
python scripts/kb01/business.py account --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1 --username configuration-publisher --role configuration-publisher
python scripts/kb01/business.py start --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1
python scripts/kb01/business.py status --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1
```

`account` 以 getpass 輸入至少 16 字元密碼，僅保存 PBKDF2 hash。不要在命令列、報告、PR 或聊天貼密碼。state-dir 0700、私密檔 0600；同名更新保留 actor UUID、撤銷舊 session。設定角色不是正式任命專家，也不產生批准紀錄。正式專家／發布者必須由責任方另行指定；`acceptance-expert`／`acceptance-publisher` 角色只提供技術權限，F0 仍核對獨立批准的 exact appointment，不能取代該任命。

入口：`http://127.0.0.1:15174/intake`；管理：`/admin?admin_resource=knowledge-management`；模型：`/admin?admin_resource=models`；F1：`/admin?admin_resource=regulatory-acceptance`；人工審核：`/reviews`。後端 liveness：`http://127.0.0.1:18011/health/live`。**網址僅在執行主機可用，不能在另一台電腦／手機開啟 Codex Cloud 的 127.0.0.1；沒有公開持續託管網址。** 使用者需在自己的隔離主機執行上述步驟。不得將測試身份服務綁到 0.0.0.0 或公開 tunnel。

```bash
python scripts/kb01/business.py stop --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1
python scripts/kb01/business.py start --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1
```

Stop 只停止這套 launcher 記錄且 start-time 相符的程序，保留 DB、S3、文件、帳號及加密模型 Secret Store。程序重啟後需重新登入；同一 Project 仍在。沒有自動 reset、drop 或 seed。要重做案例請新建 Project，不要清除歷史 Snapshot。服務本身停止／啟動另遵循 RC1 指引，不以同機重啟冒充異機還原。

## 真實法規上傳及發布

1. 授權 operator 登入管理頁，先經既有 Metadata lifecycle 建立 `knowledge-management-policies` 技術政策草稿；[case-01/upload_policy_draft.json](case-01/upload_policy_draft.json) 是未批准的 payload 參考，`scan_required=true`，不允許 draft delete。由實際具權限、符合獨立性要求的人員 review / approve / publish。AI 沒有替人批准。
2. 建立真實國家／地區、法規類型與集合，經既有 canonical taxonomy owner 治理；不沿用合成國家。使用知識管理「上傳」選擇授權 DOC、DOCX、HTML、PDF、TXT、XHTML 或 ZIP/RAR 原檔。上傳 UI 已存在；目前缺 policy 返回明確 503，提交被停用，不是假成功。
3. 原檔 multipart 存入 canonical 隔離儲存，須通過 genuine ClamAV 與隔離 parser/extractor 才能 attach / parse / ingest。現有工具掃描 130 High／1 Critical，未獲正式處置，**本入口不啟動 native worker，也不允許業務附件繞過掃描**。可驗證檔案選擇介面，尚不可完成真實原檔處理。
4. 安全修復後，固定工具來源、映像、parser hashes、掃描 digest 必須一致；新掃描需在 24 小時內且零 High/Critical 才能 technical preflight clear。該結果不是正式 Security Approval。worker 每輪及業務 scanner 重新檢查。不得手改報告或偽造 zero findings。
5. 處理成功後，在來源／知識版本紀錄 official URL、原檔 hash、法域、版本、有效日、修訂／廢止關係及條文 locator；實際授權專家核實來源與有效性，review / publish / index，取得 KnowledgeVersion、structure nodes、Evidence 與引用。僅上傳檔案或提供 URL 不等於法規有效性已確認。

## 真實模型與正式業務路徑

ChatGPT 網頁登入／訂閱不等於 OpenAI API Key，也不能由本聊天代為執行後端 LLM 節點。不要讀取瀏覽器 Cookie 或複用登入 Token。責任方提供既有授權 API Provider、部署／模型、資料邊界及額度上限後，在模型管理寫入伺服器加密 Secret Store；metadata 只存 secret_ref。不得貼出金鑰。

依 Phase1K-B 現有流程治理 Provider、Model、Deployment、health、ModelUsagePolicy、LLMInvocationPolicy、版本化 Prompt、FactType；以實際 reviewer/publisher 發布，沒有自動模擬 fallback。業務用戶只選 eligible AUTO/SINGLE/MULTI_MODEL。確認明確 prompt-purpose 授權、redaction 與資料境界；設定變更不能替換已 pin 的 preparation / Snapshot。

第一例使用 [case-01](case-01/input_manifest.json) 的非敏感需求草稿，由用戶填入實際 source != destination 的 canonical jurisdictions、scenario、product、data item 與 DataFlow；**不預設法律 outcome**。第一輪業務附件僅啟用 bounded TXT <=1MiB 且需安全掃描；法規管理仍沿用六格式 owner。需 DOCX 業務附件擴展時，必須先為業務上傳 owner 接入經安全核實的格式策略與隔離 parser，不以 host XML 或 clean stub 代替。

操作：空白 Project → typed Intake / 真正 DataFlow → 上傳需求 → native parse → prepare candidates → preview → user ACCEPT/REJECT/EDIT → Confirm → exact Snapshot → Start → canonical pipeline → 結果／Review。新 Project 建立後，操作者可離線授權該實際 UUID：

```bash
python scripts/kb01/business.py grant-project --state-dir /absolute/private/stage1-business --services-state /absolute/private/kb01-rc1 --username business-user --project-id <actual-project-uuid>
```

相同方式僅授權指定 workflow-reviewer 的 Project，不給 `system` 或 wildcard。此步不替人作 ReviewDecision；原有 server current-role/CAS/tenant enforcement 保留。

取得完整結果後核對 classification、risk、recommendation、final path、required documents、LegalBasis/Evidence 原文；有多 jurisdiction 的同一 DataItem 會顯示全部分類，避免只看第一個分類。重載／重新登入後從 canonical read 取得相同 Snapshot、pins、result。缺資料時按既有 review / successor 流程補充，不修改舊 S1、不自動開始 Stage2。

模型證據須記錄即時請求而非 cache/health：provider/model/deployment/version、request/invocation group、actor、purpose、時間、token/latency（可取得者）、outcome、redaction run、preparation / project / Snapshot / workflow refs、脫敏 input/output digest。未經 user 授權的 candidate 不得 formalize，模型不決定正式法律 outcome。

## 法律 Gold 與使用者測試

沿用 [F0/F1 五條件](../real_regulatory_acceptance_readiness.md)。F1 介面讀取既有 schemas，僅匯入 L2 草稿，經 canonical actor/CAS review / publish；不可由 JSON 填 approved_by/date。須正式 appointment、來源核實、case pins、獨立 expected semantics、criteria、Gold review。模板不是 Gold，LLM 答案不是獨立預期。

參照 [case-01/review_checklist.md](case-01/review_checklist.md)；缺少原始文件、API 憑證與正式 Gold 時，完整 E2E 及法律準確性保持 BLOCKED / NOT_EXECUTED。材料齊備後先跑一例、逐項比對及記錄差異，再擴展；不得以自動化入口 smoke 取代用戶驗收。
