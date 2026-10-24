# KB01-Technical-UAT-RC1

新增可重現local lifecycle wrapper，復用既有uat.py、ci_services.py、canonical routers/workers與React應用。專用PostgreSQL17+pgvector、Redis按manifest固定，只綁loopback；S3保留原private credentials/versioning/data，stop/start不重seed。只支援經驗證的Linux/amd64流程；Windows原生與遠端Staging不在本輪接受範圍。

start/stop/status/health/demo/logs/diagnose/reset齊備；reset必須提供exact owned instance，僅處理自有volumes，其他state檔案保留封存。沒有公開Cloud URL。前端UAT專屬Reviewer/Publisher/Restricted按鈕受雙demo feature gate限制；作者不授予新KB approve/publish，server仍唯一授權來源。

參見 ../uat/RC1_quick_start.md、installation_guide、user_test_cases、test_accounts_and_roles、known_limitations、feedback_template、troubleshooting。18項UAT案例為操作指引，不預填人類PASS；自動smoke／Browser與restart實測另外記錄。

本輪修復授權：使用者提交 STAGE1-GAP-KB01-G1-R1；不是正式 Reviewer Approval。產品仍沿用 PR29 Draft／原分支，Main060cbb5、Release Tag不變。F1 BLOCKED、Legal L2／部署未接受、Production UAT／Paid LLM 未執行、MASTER原文INPUT_REQUIRED、Stage2 NOT STARTED。所有最終 PASS 必須以新 exact-head 完整 CI 與獨立 evidence 證明；此設計／定向紀錄不能替代。

首次RC1整合Smoke在source50cb54e發現CVD配置位於sandbox mount root之外，正確fail closed為SCANNER_UNAVAILABLE。修復僅把launcher的official-signatures路徑移至既有services/scan根內；sandbox guard、assertions、timeouts與Browser retries均不放寬。舊失敗／中止驗證保留，完整最終Gate於新Head重跑。
