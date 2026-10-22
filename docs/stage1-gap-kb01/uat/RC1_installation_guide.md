# RC1 安裝與相依條件

目標支援 Linux x86_64 / amd64、Python 3.12（專案相依支援 3.11–3.13）、Node >=22.12、npm、Git full clone、可用 local Docker socket `/var/run/docker.sock`。Windows 原生未驗證；WSL2 + Docker Desktop 可能提供 Linux 等效環境，但未實測前不列為已支援平台。

建議至少 16GiB RAM、30GiB 可用磁碟，容量 RAR/ZIP 測試另需 compressed+expanded+versioned objects 空間；這是規劃建議而非 SLA。既有大檔 scanner fixture 使用治理後的 4GiB budget。

使用 quick_start 中 venv 安裝命令；npm dependencies 在首次 start 時依 package-lock 執行 npm ci。不得更改 lock、TLS verification、proxy、CA 或 Docker registry credential 設定來繞過錯誤。Cloud 的 Buildx state 使用可寫 RC1 目錄；registry auth config 保留。

RC1 專用 PostgreSQL17+pgvector 與 Redis 映像由 `scripts/kb01/rc1_services.lock.json` 的已核實 linux/amd64 manifest digest 固定。PostgreSQL port65432、Redis16379只映射 loopback；S3 ports 以既有 ci_services offset100啟動，API18010，前端15173。不要與其他本地測試共用資料庫／bucket。

隨機本地 PostgreSQL/S3 credentials 自動寫入 state-dir 的私有600檔案，父目錄700；不需提供或複製生產帳密。Migration 只升級專用 kb01_rc1 DB，head0024，不修改 frozen migration 或既有 main DB。

工具映像固定 Debian OCI digest 與 authenticated snapshot；build_tools 保存實際新映像 package hashes、signed InRelease、SBOM、OCI manifest/archive、roundtrip restore 與 Trivy report。Historical Valid-Until 僅對固定 snapshot 關閉，GPG 套件簽章與 HTTPS verification 保留。Image config ID 與 OCI manifest digest 分開記錄。

精確 Source Commit、平台、已執行 smoke 及安全 Gate 以新 Head 獨立 evidence 為準；安裝步驟不等於 Production Deployment Acceptance。

版本：`KB01-Technical-UAT-RC1`。只限 `LOCAL / ISOLATED TECHNICAL TESTING ONLY`。使用既有 React 前端、UAT Host、PostgreSQL、Redis、versioned S3 與 canonical Workers；不是 Production Auth，也不提供公開網址。

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Acceptance / Production UAT / Paid Internet LLM = NOT EXECUTED；Reviewer Approval = Pending；MASTER reconciliation = INPUT_REQUIRED；PR29 Draft；Main merge 未授權；Release Tag 不變；Stage2 NOT STARTED。

## 本輪已執行的交付身份

產品 `4593a355d0711a9ba955b1624926a2ec71d60430`，PR29 Draft。本獨立 evidence branch 只保存測量／操作說明，不是新的產品 Head；請 clone 完整 repository 後 checkout 上述產品 Commit。Linux x86_64／Python3.12.14／Node24.19.0／PostgreSQL17.11+pgvector0.8.7／Redis7.4.11 已實測；Windows 原生及 Docker Desktop/WSL 未獨立驗收。

本輪工具映像漏洞掃描已完成，但134 High +1 Critical（套件 finding，並非135個不同CVE）的正式處置未批准。`TECHNICAL_UAT_CANDIDATE=READY` 僅表示隔離合成資料功能可操作；`RC1_TECHNICAL_ACCEPTANCE=BLOCKED_SECURITY_REVIEW_PENDING`，不等於可部署／可對外提供服務。不要使用敏感文件或對外暴露 synthetic session。
