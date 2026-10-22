# RC1 已知限制

- 技術驗收與正式審查分離。兩項 Medium 的修復授權不等於風險接受、Reviewer Approval、Ready 或 Merge 授權。
- 漏洞掃描執行完成不等於零漏洞；查看 toolchain/provenance.json 與 vulnerabilities.json 的實測 severity。High/Critical 未正式處置時 security_acceptance 保持 BLOCKED_REVIEW_REQUIRED，不能宣稱安全／RC1 最終技術接受 PASS。
- Github Actions 上的 OCI artifact 留存以實際 upload artifact ID、SHA256、到期日為準；本地檔案不是 durable registry，也沒有 Production 長期保存／乾淨獨立 host 還原批准。Local Docker roundtrip 只證明 archive content 完整。
- 沒有可公開存取的持續 Cloud UAT 網址；clone 固定 commit 後在自己的受支援 Linux 電腦啟動。Synthetic UAT 不可公開曝露；遠端 staging 需獨立正式身份及網路授權。
- Native parser sandbox、scanner/refusal、資源限制仍適用；密文、archive bombs、巢狀壓縮、逃逸路徑、無法完整掃描的內容 fail closed。
- 文件／分類 delete 受歷史引用、hold、retention 與 lifecycle 約束；不能承諾所有 active/pinned records 都可刪除。按功能的 canonical equivalent 使用停用、archive、alias merge。
- 所有示範法規標記 SYNTHETIC_GOVERNED_TEST_DATA，不能當成真實法律或 Gold Standard。F1、L2、部署、Production UAT 與 paid LLM 的未接受邊界保留。

版本：`KB01-Technical-UAT-RC1`。只限 `LOCAL / ISOLATED TECHNICAL TESTING ONLY`。使用既有 React 前端、UAT Host、PostgreSQL、Redis、versioned S3 與 canonical Workers；不是 Production Auth，也不提供公開網址。

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Acceptance / Production UAT / Paid Internet LLM = NOT EXECUTED；Reviewer Approval = Pending；MASTER reconciliation = INPUT_REQUIRED；PR29 Draft；Main merge 未授權；Release Tag 不變；Stage2 NOT STARTED。

## 本輪已執行的交付身份

產品 `4593a355d0711a9ba955b1624926a2ec71d60430`，PR29 Draft。本獨立 evidence branch 只保存測量／操作說明，不是新的產品 Head；請 clone 完整 repository 後 checkout 上述產品 Commit。Linux x86_64／Python3.12.14／Node24.19.0／PostgreSQL17.11+pgvector0.8.7／Redis7.4.11 已實測；Windows 原生及 Docker Desktop/WSL 未獨立驗收。

本輪工具映像漏洞掃描已完成，但134 High +1 Critical（套件 finding，並非135個不同CVE）的正式處置未批准。`TECHNICAL_UAT_CANDIDATE=READY` 僅表示隔離合成資料功能可操作；`RC1_TECHNICAL_ACCEPTANCE=BLOCKED_SECURITY_REVIEW_PENDING`，不等於可部署／可對外提供服務。不要使用敏感文件或對外暴露 synthetic session。
