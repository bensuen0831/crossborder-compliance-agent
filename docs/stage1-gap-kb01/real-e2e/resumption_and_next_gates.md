# 真實法規／即時模型 E2E 接續執行紀錄

2026-10-26（香港時間）。完整用戶法律 E2E 仍不能開始；本輪已恢復可操作的隔離入口、修復政策頁接線、重驗相關行為並更新安全證據。沒有執行真實模型業務請求，也沒有法律準確性 PASS。

產品 Head：`e7efe5368c1ee7be2c62284d199275517dea2323`；修復提交：`59462e530d4b920870b25266a05e7700477f3520`；Draft PR #30，base為Draft PR #29的733a748。前一產品893c4a2及獨立證據d12be12保留作歷史紀錄；新Head不能繼承其完整CI結果。新證據分支：`evidence/stage1-real-e2e-e7efe53`，直接從新產品Head建立，文件提交不是產品baseline。

## 本輪實際操作與驗證

- 核對既有容器的owner label及保留volume後，只啟動原有PostgreSQL與Redis；既有versioned S3使用resume，未reset、drop或重seed業務／法律資料。
- 業務前端15174、後端18011均200；PostgreSQL只讀查詢、Redis連線通過。上午3個實測Project ID全部仍存在。這是同機資料保留，沒有冒充獨立主機還原。
- 真正Chromium三語系重新執行登入、空白項目、重載／重登、越權拒絕、模型設定入口、法規檔案選擇與F0入口：3/3 PASS、internal retries0。不是完整法律旅程。
- 經既有HTTP application owner建立技術上傳政策DRAFT；approved_by、approved_at、published_at均NULL，未提交Review、批准或Publish。這不是安全豁免，也沒有啟用真實原檔處理。
- 政策頁曾宣告並呼叫未提供的public registry list，回傳404。修正為已有的canonical admin version/history入口，沒有新增API、權限、法律owner或Registry。實際瀏覽器已可讀出exact DRAFT版本及scan_required=true，無該404。診斷腳本的DRAFT option/badge及textarea locator問題另行修正並披露，未靠重試或放寬斷言取得通過。

| 新Head本輪Gate | 實測 | 範圍 |
|---|---|---|
| PostgreSQL host／source ownership | 71 PASS，failed/errors/skipped/deselected0 | 兩個受影響檔案；不是全Backend |
| Architecture | 456/456 PASS | 九組既有authority；沒有刪checks |
| Frontend | 181 PASS，failed/pending0 | 完整frontend unit suite |
| typecheck / lint / build / i18n | PASS | 三語系897 keys、missing0；原大bundle警告保留 |
| 三語系入口 | 3/3 PASS，Retries0 | 登入／draft／重登／管理入口 |
| exact政策草稿讀回 | 1 PASS，Retries0 | en-US，僅讀DRAFT，不批准 |
| Alembic | 單head0024；0001–0024與733a748 byte-identical | 無新migration，未重跑DB遷移矩陣 |

既有893c4a2的完整1352 backend PASS（0failed/errors/skipped）屬前一Head CI artifact，不當作此Head結果；Runtime25、原89browser及完整backend均需新的remote CI完成後才能核實。沒有降Gate、隱藏skips或移除測試。

## 安全重掃及可處置項目

同一實際工具image config：`sha256:35765d74c83509652f2a7c5112fb983ec2398e1709a05f144177a12a16321e19`；OCI manifest：`sha256:07be6daf20dbe2feb33424afa26466421783d95504487e7ffd8548cb3064b61c`。映像沒有重建，既有284-package SPDX2.3身份不變；本輪以既定固定Trivy0.76.1與2026-10-26更新的DB重新掃描，沒有ignore/suppression。新report SHA256：`9c17bb933fd52e4dd3e2d6144e783677af5040856e654067191659916f8418bf`。

| | 舊2026-10-24 | 新2026-10-26 |
|---|---:|---:|
| High套件findings | 130 | 131 |
| Critical套件findings | 1 | 1 |
| 唯一CVE（High/Critical） | 45 | 46 |

新增：CVE-2025-71436／libraptor2-0 2.0.16-6，High；scan未提供fixed version。沒有已修復或移除finding。完整132筆逐項處置建議、package/source/version/image/scan DB身份與待審欄位見 `security-finding-dispositions.json`；132筆套件findings不是132個獨立漏洞，Reviewer決定全部PENDING。

Critical仍為CVE-2026-6653／libxml2。官方Debian tracker本輪HTTP200，trixie及bookworm列vulnerable，forky/sid列fixed；不能直接把unstable ABI塞入受支援工具。現有132筆中僅CVE-2026-111497／libbrotli1提供fixed version `1.1.0-2+deb13u1`；這是待驗證的vendor update候選，尚未安裝或聲稱修復。需Dependency Maintainer完成受支援backport/base方案與固定重建、parser／scanner／六格式／引用／容量／安全回歸，再由正式Security Reviewer處置適用版本。沒有自行接受Critical風險。

業務app仍綁原有已核對provenance／scan（130High1Critical）；新的獨立重掃132筆是補充證據，不改寫原attestation。兩份均BLOCKED，native worker與業務原檔處理仍未啟用，不會因report更新而自動放行。

## 入口與資料保留重啟

在執行主機：

- 業務：`http://127.0.0.1:15174/intake`
- 上傳：`http://127.0.0.1:15174/admin?admin_resource=knowledge-management`
- 政策：`http://127.0.0.1:15174/admin?admin_resource=knowledge-management-policies`
- 模型：`http://127.0.0.1:15174/admin?admin_resource=models`
- F1紀錄：`http://127.0.0.1:15174/admin?admin_resource=regulatory-acceptance`
- Review：`http://127.0.0.1:15174/reviews`

**全部僅限執行主機loopback；不是可在用戶另一台電腦／手機開啟的Cloud URL。** 用戶可按README在自己的隔離主機安裝並自行離線設定密碼；不公開測試身份服務，不在聊天／GitHub提供登入密碼。

本Cloud既有state：`/workspace/stage1-business-acceptance`；shared services state：`/workspace/kb01-rc1`。不再執行init，不刪既有state。只重啟業務程序且保留DB/S3：

```bash
source /workspace/compliance-tools/runtime.sh
export PYTHONPATH=src:.
python scripts/kb01/business.py stop --state-dir /workspace/stage1-business-acceptance --services-state /workspace/kb01-rc1
python scripts/kb01/business.py start --state-dir /workspace/stage1-business-acceptance --services-state /workspace/kb01-rc1
python scripts/kb01/business.py status --state-dir /workspace/stage1-business-acceptance --services-state /workspace/kb01-rc1
```

若underlying services也停了，必須先核對既有owner label並resume原有PG／Redis容器及S3，不能用reset、重新seed或新volume取代。此次已實際完成；`ci_services.py --resume`的合成EICAR fixture不作真實scanner資料庫，business environment仍只引用既有已核對official main/daily/bytecode CVD。native gate未清除時不啟用worker。

政策定義ID：`cc5fbba2-993b-4577-a679-b0aeb7b0388e`；版本ID：`506bec30-97c6-491d-853d-30ba152aadf7`。具權限的人員在政策頁的Definition ID欄輸入定義ID、Open history即可查看DRAFT原文；提供這些ID不是審批授權，也沒有替正式Reviewer選擇處置。

## 真實法規、模型與F1外部Gate

本租戶實際Provider0、Deployment0、KnowledgeVersion0、Snapshot0、F0紀錄0；只增加上述未批准技術policy draft。ChatGPT訂閱／網頁登入不等於後端API credential，沒有讀取Cookie或以本聊天冒充業務Gateway調用。已請API／額度負責人確認既有Provider、model/deployment、額度及透過secret store綁定憑證。

官方法規取得嘗試均保留：gov.cn舊xinwen及zhengce全文URL返回404；NPC官方URL返回503；EUR-Lex ELI返回202空body，未確認全文。沒有繞過存取限制、使用鏡像摘要、LLM記憶或補造原檔。須授權用戶供應genuine原檔，待安全處理就緒後透過既有六格式上傳／解析／source verification／review／publish／index，取得真正KnowledgeVersion與條文locator。目前沒有可作正式判定的已發布真實法規。

F1仍沿用五條件：授權原檔；來源／版本／有效性核驗；獨立法律預期答案；專家授權／身份／日期／版本／正式批准；指定案例／法域／標準。Registry長期保存與異機還原不被新增成F1法律條件。原KB01-MASTER V2全文仍未提供（attachments為G0/G1-R1而非MASTER原文），完整逐字比對INPUT_REQUIRED。

材料齊備後的第一步是單一空白項目完整journey，記錄project/preparation/decision/snapshot/workflow/retrieval/invocation/KnowledgeVersion，證明候選先由用戶確認、引用可開原文、模型即時非cache、正式結果由owner產生，再與預先批准的Gold實際比對。目前完整案例與法律準確性NOT_EXECUTED。材料與受支援安全工具就緒後第一例設定／串接／比對暫估8–16工程小時，不包含vendor修補、完整重建回歸、法律mapping及外部專家等待；外部等待無可承諾日期。

## CI與邊界

前一Head893c4a2的Phase1KB run40263233199因90分鐘上限取消；已按相同SHA重跑failed backend一次（attempt2），保留初次timeout。之後因政策頁實際缺陷產生新Head，所以該run只作歷史／效能診斷，不能替代新Head驗證。沒有為修復取消而提高timeout或縮減assertions。

新Head已觸發12組mandatory CI，仍需全部完成及實際job checkout核對後才能宣稱新Head remote PASS。此文件及先前1352 PASS不能提前替代其結果。PR #29／#30保持Draft；沒有Ready、Review Request、merge、tag、release或Stage2。

```ini
BUSINESS_ENTRY = OPERABLE_LOOPBACK_ONLY
BUSINESS_UI_E2E = BLOCKED
REAL_REGULATORY_DATA = BLOCKED
LIVE_MODEL_WORKFLOW = BLOCKED
LEGAL_GOLD_AND_CRITERIA = BLOCKED
LEGAL_ACCURACY_EXECUTION = NOT_EXECUTED
USER_E2E_TEST_READINESS = BLOCKED
FORMAL_SECURITY_ACCEPTANCE = PENDING_BLOCKED_REVIEW_REQUIRED
STAGE2 = NOT_STARTED
```

最新機器證據：`resumed-20261026/new-head-validation.json`、`native-comparison.json`、`security-finding-dispositions.json`、`browser-new-head.json`、`policy-draft-browser.json`及新Head CI snapshot。原Head資料和失敗診斷保留，未重標為新Head PASS。
