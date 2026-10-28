# Stage1 native security recovery — 2026-10-28

本紀錄是 PR #30 的工程修復及安全審查材料，不是正式 Reviewer Approval、真實法律驗收或 Production Ready 聲明。產品 source 為 `3d322e864a6c98c34d42657289e421c77f6c9ed1`；本文件所在 evidence branch 的 commit 不是產品 Head。

## 實際執行與資料保留

Shell、Git HTTPS、GitHub API 均已實測可用。管理環境當前 running／connected、revision7；沒有 Provider Secret 綁定。原 checkout `/workspace/crossborder-compliance-agent`、舊 PostgreSQL／Redis volumes、舊 evidence worktrees 及未提交內容均保留；本輪只在獨立 `/workspace/stage1-native-security-20261028` 工作樹和新建 task-labelled PG／Redis／S3 資料區操作。這不代表原有環境或 revision14 已恢復。沒有 reset／clean、沒有將原資料庫當作測試庫。

PR #29 保持 Draft、Head733a748；PR #30 保持 Draft、base733a748。Main060cbb5及 annotated release tag object3144c1d →060cbb5保持不變。不 merge、不 retag、不啟動 Stage2。

## Critical libxml2：已實作受支援修復

舊工具 config image `sha256:35765d74c83509652f2a7c5112fb983ec2398e1709a05f144177a12a16321e19` 含 `2.12.7+dfsg+really2.9.14-2.1+deb13u3`。其源碼實際為2.9.14；同一映像中的 LibreOffice `libmergedlo.so` 和 ClamAV `libclamav.so.12` 實際連結 libxml2.so.2。不能以「工具映像／未直接呼叫」排除風險。

CVE-2026-6653 為 internal subset/entity 處理的 use-after-free；Debian原發行版尚受影響。Ubuntu官方公告給24.04LTS的修復版本為 `2.9.14+dfsg-1.3ubuntu3.8`。本次採用 coherent Ubuntu24.04LTS、固定 amd64 OCI manifest、20261028T000000Z Ubuntu簽章 APT snapshot；實裝 `libxml2:amd64 2.9.14+dfsg-1.3ubuntu3.10`。沒有混裝 Debian／Ubuntu ABI；Containerfile 加入最低修補版本檢查。

來源：[Ubuntu公告](https://ubuntu.com/security/CVE-2026-6653)、[Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-6653)。原頁 bytes、擷取時間、SHA256保存於本 evidence 目錄。官方 priority 與不同來源 CVSS 不同，均保留，不自行降級。

新版實際工具 config image：`sha256:426a0c6384cfcd4cdb0b4a6ffafa222d3bb1e17b5b30bf60bc082f3a7304feb8`。
OCI manifest：`sha256:1039279faaf896abfc999db325422861d79ea1d3287f87f11d0b99af892170cd`。
實際 clean build 的 source241337f；最終3d322e8僅更新 host gate、測試及 scope seal，對 build context 的 Git blobs 已逐項核對無變更。沒有把這個映像冒稱為另一 Head 的新 build。

284套件 SPDX2.3 SBOM、GPG／APT release/index/archive來源、工具 hashes及 OCI archive雜湊已保存。local OCI save/load content roundtrip通過，**未完成獨立主機還原或長期 Registry 保存**；約866MB archive保留在私有 task artifact 目錄，沒有塞進 Git，也沒有宣稱已上傳至長期 Registry。

## 掃描比較及仍未閉環的安全風險

| 比較 | Critical | High | Medium | Low |
| --- | ---: | ---: | ---: | ---: |
| 交接舊報告（歷史提供，非本輪重跑） | 1 | 134 | 未在此重計 | 未在此重計 |
| 舊映像，本輪同一漏洞DB重掃 | 1 | 131 | 247 | 291 |
| 新映像，本輪同一漏洞DB重掃 | 0 | 0 | 60 | 27 |

Trivy0.76.1，DB SHA256 `2c8f4b04f224aded9ecd149b9b5304146736668220dfa403403358fb423a52fd`。舊DB與新DB的 finding count 不能直接當成修復數量；原135筆是 package findings，亦不等於135個獨立CVE。本輪舊映像High/Critical共46個唯一CVE。兩個映像的完整 normalized findings、原報告hash、時間與資料來源分別保存，不隱藏 Unknown。

**raw0High／0Critical不等於正式安全接受。** 七個舊High CVE仍出現在新映像，僅改列Ubuntu Medium。進一步按全部來源 CVSS>=7.0核對，新映像共有32筆套件 findings、21個唯一CVE。host 現以 raw severity、CVSS及24小時掃描新鮮度共同 fail closed；目前真實文件 native processing = BLOCKED。沒有 suppression、ignore-unfixed、風險自批或 severity rewrite。

`remaining-findings-disposition.json` 是逐項 Reviewer package，包含 package/version、CVSS、原severity、官方來源、修補狀態、責任角色及下一個動作，所有正式決定均 Pending。21個CVE的Ubuntu官方頁面本輪均取得HTTP200並保存hash及noble行原文。Tesseract的七項相關漏洞（含新比對發現的88049）已有 `5.3.4-1ubuntu0.1~esm1` 修補，但官方列為ESM Apps／Ubuntu Pro；沒有現有授權綁定，未購買或啟用新付費服務。其他部分套件仍 Vulnerable／fix deferred。多source-package公告逐列保留，不因其中一個package已修補便宣稱另一個亦已修補。

下一個合規動作：工具維護者取得既有合法ESM來源（若組織已有授權），或提出受支援的套件／上游修補；重新固定來源、建置、SBOM、掃描與 native regressions。尚無修補的項目，由正式安全Reviewer核實適用性、影響、緩解及責任期限，不由AI批准誤報或風險接受。資料使用許可不能由合成測試自動擴張。

## 附帶發現並完成的 canonical wiring 修復

原生 Python入口採實際 `/usr/bin/python3`，不建立假的python3.13 alias；sandbox 保持有限 executable allowlist，沒有增加 shell／網路權限。genuine DOC fixture 的生成亦使用實際安裝的 interpreter。

原先 genuine ClamAV CVD 路徑位於scanner-owned root外，會被現有mount boundary正確拒絕。launcher現於HTTP啟動計時前，經既有下載器將官方main/daily/bytecode CVD下載／驗簽於該scanner root內，綁定映像及逐檔size/hash；錯誤映像、缺檔、symlink及tamper仍拒絕，沒有放寬掛載限制。

官方genuineCVD下載／sigtool驗簽、clean／EICAR拒絕、錯誤manifest拒絕皆有本輪紀錄。source241337f曾完成 canonical app + scoped empty worker cycle；其當時raw severity preflight為clear。**這是更嚴格CVSS guard新增之前的工程結果，不能拿來主張最終3d322e8可啟用真實文件。** 原本 synthetic EICAR-only testDB也與genuineCVD證據分開標示。

## 驗證身份及限制

| 本輪實際執行 | 來源 | 結果 |
| --- | --- | --- |
| Native formats/OCR/isolation focused | 初期未提交patch，後納入41e0a54 | 51 PASS，非exact-commit full suite |
| Native／PG／S3／scanner／scope integration | 34e348d | 140 PASS |
| Host／scope／RC1 | 241337f | 81 PASS |
| 最終host CVSS gate／scope／RC1 | **3d322e8** | **84 PASS** |
| 全部9組架構checker | **3d322e8** | **456/456 PASS** |

上述重疊suite不相加，逐項test ID、JUnit hash、elapsed time保存於 `local-validation.json`。最終84項failed/errors/skipped/deselected皆0。fresh隔離DB升級0024通過，PR30相對e7沒有任何migration byte變更；本輪未將舊完整遷移矩陣冒稱為新Head結果。遇到的本機helper PATH／JSON彙整失敗已修正並重跑；不隱藏在成功測試數內。

歷史e7efe53的遠端12/12、實際checkout22/22已重新讀取logs核對；Phase1KB artifact的1352 backend JUnit ID亦實際重新下載核實。它們是**舊Head歷史證據**，不能替代3d322e8。最新12組CI及每個completed job的實際checkout線記於 `current-ci-identity.json`；仍在執行者保持Pending，只有完成並核對後才可封板。沒有借用PR29舊驗證。

## revision14完整內容審查

revision14完整欄位snapshot hash為 `4d501933781a963876e2de437a792ebc5f9b31e1cb08f92208e7f4af0c685554`。install_script仍產生含 trust-initdb、default5432建庫及unconditional Alembic的舊helper，而start_skill禁止使用該helper，兩者有衝突；另有live APT/pip、舊路徑/PID及main ref需再核對。完整snapshot留本地，安全摘要於 `revision14-review.json`。**沒有套用、發布或執行該generated helper；原服務與資料未刪除／重建。**

## MASTER、F1與使用者就緒閘門

已依repo V3.7 MASTER／Phase0／ARCHITECTURE_RULES維持one canonical pipeline、candidate consent、exact pins／historical immutability；沒有新增Registry、legal rule、migration或Stage2。KB01-MASTER V2完整原文與正式變更批准仍未提供，全文比對保持INPUT_REQUIRED，不能以現有traceability重建原文後宣稱完整。

F1沿用原五條件：授權原檔；來源／版本／有效性核實；獨立法律預期答案；正式專家身份／日期／版本／批准紀錄；明確案例／法域／評估標準。Provider API、真實法規、獨立Gold是三個獨立外部依賴，不阻止本輪工程修復，也不能靠ChatGPT訂閱、LLM答案或raw法規互相替代。詳細責任方及解除動作在 `environment-and-boundaries.json`。

`BUSINESS_UI_E2E=BLOCKED`、`REAL_REGULATORY_DATA=BLOCKED`、`LIVE_MODEL_WORKFLOW=BLOCKED`、`LEGAL_GOLD_AND_CRITERIA=BLOCKED`、`LEGAL_ACCURACY_EXECUTION=NOT_EXECUTED`、`USER_E2E_TEST_READINESS=BLOCKED`、`FORMAL_SECURITY_ACCEPTANCE=PENDING`。未接入APIkey／真正法規／Gold，未執行paid模型或法律L2／Production UAT。修復與測試完成不代表正式Reviewer已通過。

新獨立業務入口的實際啟停及登入／blank-project smoke（如已完成）以 `business-entry-smoke.json`及 `local-entry-operations.json` 為準。只可在執行主機loopback開啟；沒有公開持續託管URL，也沒有將原環境恢復視為已完成。完整真實E2E須先解除native安全閘門，再由授權者提供Provider、發布真實法規和獨立Gold，以新Project完整跑一例並實測比對。

## 最新補充實測（同一3d322e8產品）

本機Frontend完整181PASS，typecheck／lint／build／check:i18n均PASS；三語系各897keys、missing0。初次npm cache路徑及多餘錯誤script名稱的執行失敗已在`frontend-current.json`披露並更正，沒有改lockfile或放寬測試。

Chromium工程smoke實際完成登入、建立blank Project、reload同一Project；owned launcher stop/start後重新登入同一DRAFT，Snapshot仍NULL，普通business帳號讀取F0管理template得到403。沒有模擬授權、法律結果、Provider呼叫或Reviewer批准；同主機重啟不是異機還原。入口目前在執行主機127.0.0.1:15174，使用者另機不能直接開啟。啟停指令及私密帳號配置方式見`local-entry-operations.json`，密碼沒有輸出至證據。

新Head KB01 workflow [40684105550](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/40684105550) SUCCESS。實際下載verified acceptance artifact12815945056並核對zip/member hashes：312PG test IDs、181frontend、8management及4capacity browser IDs、retries0；500MB+單檔及1GB+RAR4/RAR5/ZIP合成工程資料發布驗證保留。此結果是L1工程驗收，**不是F1或正式安全Review**。三個small toolchain artifacts亦逐一下載驗hash，source3d322e8一致，各自imageID不同、rawscan60Medium/27Low；不能用本地imageID替代CIimageID。遠端OCI archive存在及expiry記於artifact index，尚未下載驗證其大檔內容或宣稱長期保存。

此封存時全倉庫mandatory CI尚未全數完成，以`current-ci-identity.json`的timestamp為準；未執行完畢的完整backend/runtime/full browser保持PENDING。下一輪應先核對PR30仍3d322e8，再讀完成run的actual checkout和完整產物，補充獨立evidence；若失敗，保留job/step/SHA原因後修復，不借用舊SHA。

最新snapshot2026-10-28T12:20:43Z：全倉庫7/12workflow SUCCESS，22個實際job中已完成並取得logs的16個checkout MATCH，其餘未完成保持Pending。Stage1 Full Business E2E workflow40684105546已SUCCESS，實際下載aggregate artifact12815990570：29focused business tests、61owning regressions及12/12outcome×locale journeys PASS、retries0，來源均3d322e8。這仍是明確標記SYNTHETIC_GOVERNED_TEST_DATA的驗收，沒有把它算作即時付費模型、真實法規或專家Gold。完整backend/runtime還在獨立mandatory jobs執行中，沒有用29/61/312項子集替代全量。
