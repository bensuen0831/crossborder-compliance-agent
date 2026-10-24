# KB01/RC1 security, MASTER and F1 closure status

產品 `733a7483439cd919c186ed0064b8f3752904ebb6`；上一產品 `4593a355d0711a9ba955b1624926a2ec71d60430`，舊證據d9adf53只作historical。PR29保持Draft；main060cbb5、release tag不變。獨立evidence commit不是產品SHA。

| Gate | 本輪狀態／原因 |
|---|---|
| Technical UAT Candidate | READY，僅local/isolated/synthetic；新映像已實際啟動 |
| Functional exact-head regression | PASS：Backend1336×4／Architecture456／Runtime25／Frontend180／Browser89，retry0；12/12CI、22/22actualcheckout |
| Formal Security Review | PENDING，沒有Reviewer任命／批准／risk acceptance |
| Security acceptance | BLOCKED：newlocal130High/1Critical、45unique CVEs；CI逐映像數量另列 |
| Repo MasterV3.7 | 1000個logical行（999個換行、EOF無換行）／42sections完整比對，17符合、13部分、9out-of-scope、3證據不足；9個聚焦要求另列未符合項 |
| KB01-MASTER V2原文 | INPUT_REQUIRED；缺原文及正式變更批准，不以D0代替 |
| F1 / Legal L2 | BLOCKED_EXTERNAL_EVIDENCE_PENDING／NOT ACCEPTED，五類外部證據缺口保留 |
| RC1正式技術接受 | BLOCKED_SECURITY_REVIEW_PENDING；不以功能CI綠燈代正式審查 |

## 本輪實際修復／證據

明確選用gpg alternative，移除6個非必要GnuPG套件、5個High package occurrences；固定base/APT、安全signature及10個critical可執行檔hash保持。新實際image284packages SPDX2.3、manifest `sha256:07be6daf20dbe2feb33424afa26466421783d95504487e7ffd8548cb3064b61c`、config `sha256:35765d74c83509652f2a7c5112fb983ec2398e1709a05f144177a12a16321e19`、archive SHA256 `5d5c37376b9fd459a44d215ebd6e1a677c0f814b84cae410d4993d54f541e508`。原始135finding每筆、45份官方公告raw/hash、DB版本／時間、8個原image與current7CI+1local身份關聯均在security-review目錄。

同一最新DB：oldimage135High/1Critical→new130High/1Critical，沒有dependency-introducedHigh/Critical；新DB額外通報libbrotli1/CVE-2026-111497同樣影響oldimage。相比原scan134High/1Critical只看差額4會混淆DB變化。Critical libxml2 runtime20914仍受影響；未混入sid套件或自行維護未驗證的parserfork。正式剩餘風險未批准。

新跑local75source/CI/lifecycle＋39native/archive/F0＋7PGtaxonomy，均0fail/error/skip/deselect；9authority456/456；newimage角色Browser1PASS/retry0；18ACTIVE原件exacthash持續一致。RC1重啟前PG/Redis已停而liveness仍200；正常ownedstop/start恢復後有真DBreadonlyquery與原件下載證明，沒有把liveness當DBready。舊2.627→0.036s是459時的歷史測量；本輪7PGcase重驗三locale/完整JSON/402→5SQL，不冒稱重跑舊pairedwalltimes。

另外修復cached tool-evidence的來源驗證缺口：原launcher在未指定新proof時可沿用舊Containerfile映像proof；本輪用受信任舊Git blob重現，並在cached／supplied兩條路徑核對Containerfile與inventory reader雜湊，在migration／worker前拒絕不符來源。兩個新增negative cases和counterexample證據已保留；這是技術修復，正式Reviewer處置仍Pending。

## 最新完整回歸

Backend1336PASS（四個獨立CIexecution，每個原1332testIDs全部保留+4additive tamper/cached-source cases）、failed/errors/skipped/deselected0；Architecture456/456、Runtime25/25、Frontend180、typecheck/lint/build/i18nPASS；Browser89/89、全部原89IDs保留、retries0；12/12mandatorySUCCESS，22/22actualjobcheckout=733a7483439cd919c186ed0064b8f3752904ebb6。補充contractsubsetskips/deselections獨立披露於ci-complete.json，未混入全量PG。Artifact ZIP 34與7OCI所有blobs已實際verify，不借用459CI。

## 待決與邊界

security_review_package、MASTER_full_text_reconciliation、F1_external_evidence_review及acceptance_status.json是本輪入口。Registry短期artifact實際到期日見image_retention.json；long-term registry/signing/retention與真正independenthost restore外部未完成。MASTER0.2.4／Phase0Part20C是運維來源；它們不冒充F1五條法律證據，也不被本輪自行取消。

正式Reviewer與Maintainer決定仍需適用當前Head/Digest；security材料完成不等於reviewPASS。F1未完成不降低A–E門檻，亦不妨礙isolatedsyntheticUAT。MASTER42section對照不等於缺失KB01原文已全文閉環。Production IAM／cloud／正式部署、Legal L2、Production UAT與PaidInternetLLM未接受或未執行；Stage2NOTSTARTED。不轉Ready、不發reviewrequest、不merge/mainpush/tag/release。
