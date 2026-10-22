# KB01-Technical-UAT-RC1

TECHNICAL_UAT_CANDIDATE = READY（僅限隔離合成資料功能測試）
RC1_TECHNICAL_ACCEPTANCE = BLOCKED — SECURITY_REVIEW_PENDING

產品 `4593a355d0711a9ba955b1624926a2ec71d60430`，既有PR29產品分支。Linux/amd64已實測，Python3.12.14/Node24.19.0/PostgreSQL17.11+pgvector0.8.7/Redis7.4.11，migration0024。未驗證Windows原生/WSL，不宣稱已支援。

Start/Stop/Health/Demo/Logs/Diagnose/Reset沿用既有UAT Host、React、canonical知識服務及workers。AUTHOR/REVIEWER/PUBLISHER/RESTRICTED為不同actor/permissions；不提供production身份。100個ACTIVE分類與18個六格式原檔已實際stop/start保留exact bytes/hash；另以一次性Dockerresources實測Reset只清exact owned containers/volumes，原檔封存與獨立volume保留。

操作指南：`../uat/RC1_quick_start.md`、installation、user_test_cases、roles、known_limitations、troubleshooting、feedback_template。前端 `http://127.0.0.1:15173/admin?admin_resource=knowledge-management`；backend `http://127.0.0.1:18010/health/live`，本輪兩者實際200。Loopback只屬執行命令那台電腦；沒有公開Cloud URL或持續託管承諾。請依固定SHA clone本機執行，不可暴露synthetic login到Internet。

定向PG320PASS保留原303+17新增，完整遠端PG 1332PASS保留原1315；architecture456/456，runtime25/25，frontend180，browser89/89（原88+角色切換1），retries0。12/12 mandatory workflows SUCCESS；22/22 actual jobcheckout MATCH。全量PG無failed/errors/skipped/deselected；supplemental contract選取另外披露。

Security scan有134High+1Critical待正式處置，不能宣稱RC1整體安全接受。UAT01–18的人類結果保持Pending，工程自動化不代替Production UAT或法律審核。


PR29 保持 Draft／未合併；Main060cbb5與 v3.7-stage1-e2e-pass 不變。Formal Reviewer Approval=PENDING；MASTER full-text reconciliation=INPUT_REQUIRED；Formal requirement change approval=NOT_VERIFIED。KB01-F1=BLOCKED_EXTERNAL_EVIDENCE_PENDING，LEGAL L2／Production Deployment=NOT ACCEPTED；Real Regulatory Acceptance／Production UAT／Paid Internet LLM=NOT EXECUTED；Stage2=NOT STARTED。
