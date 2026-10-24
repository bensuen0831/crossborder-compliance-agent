# RC1 final acceptance gate

本文件定義交付門檻；最終測量由新Head的獨立evidence封存，不能把本文件存在或舊39c3581的PASS當新驗收。

需保留Backend>=1315（含新增case）、Architecture>=456、Runtime25/25、Frontend>=180、Browser>=88及新增rolejourney、Retries0；完整PG failed/errors/skipped/deselected均0。12 mandatory workflows必須全SUCCESS，actual jobcheckout/source/test/fixture/log/artifact identity核實後才可報RC1_TECHNICAL_ACCEPTANCE=PASS。

Toolchain須實測base/APT/SBOM/tool/OCI identity、parser/archive/security/capacity；official CVD與engine分開。掃描完成但有未處置High/Critical時不能宣稱security acceptance PASS；保持BLOCKED_REVIEW_REQUIRED，不自行代Reviewer簽risk acceptance。資料保存／restore證據不存在時明確EXTERNAL_DEPENDENCY。

本機UAT可啟動與技術接受／正式Production UAT是分開的狀態。交付必須附sourceSHA、commands、supportedplatform、URLs、roles、health、stop/reset與安全邊界。PR保持Draft；未得到新授權不得Ready、Merge、Tag或Stage2。

本輪修復授權：使用者提交 STAGE1-GAP-KB01-G1-R1；不是正式 Reviewer Approval。產品仍沿用 PR29 Draft／原分支，Main060cbb5、Release Tag不變。F1 BLOCKED、Legal L2／部署未接受、Production UAT／Paid LLM 未執行、MASTER原文INPUT_REQUIRED、Stage2 NOT STARTED。所有最終 PASS 必須以新 exact-head 完整 CI 與獨立 evidence 證明；此設計／定向紀錄不能替代。
