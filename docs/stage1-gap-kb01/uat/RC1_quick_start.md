# RC1 快速啟動

先閱讀 installation guide 與 known limitations，尤其安全掃描的未接受 findings。取得 PR29 產品分支的指定 RC1 commit；正式 `v3.7-stage1-e2e-pass` 仍是舊 main，不能拿它當 RC1。

```bash
git clone https://github.com/bensuen0831/crossborder-compliance-agent.git
cd crossborder-compliance-agent
git checkout --detach 4593a355d0711a9ba955b1624926a2ec71d60430
git rev-parse HEAD
python3.12 -m venv "$HOME/.local/share/kb01-rc1-venv"
. "$HOME/.local/share/kb01-rc1-venv/bin/activate"
python -m pip install -e '.[dev]'
python scripts/kb01/rc1.py start --state-dir "$HOME/.local/share/kb01-rc1"
python scripts/kb01/rc1.py demo --state-dir "$HOME/.local/share/kb01-rc1"
python scripts/kb01/rc1.py status --state-dir "$HOME/.local/share/kb01-rc1"
```

將 `"$HOME/.local/share/kb01-rc1"` 換成你有寫入權限的專用目錄。首輪需下載固定 dependency/toolchain 與官方 ClamAV CVD，並產生 SBOM、OCI archive、漏洞報告；不是瞬間啟動。

實際程序啟動後，本機網址：`http://127.0.0.1:15173/admin?admin_resource=knowledge-management`；Backend liveness：`http://127.0.0.1:18010/health/live`。這些是**執行該命令的電腦**的 loopback，不能在另一台電腦打開 Codex Cloud 的 127.0.0.1，也沒有持續公開 Cloud URL。

登入 A（AUTHOR），再用 Reviewer / Publisher 按鈕切換角色。demo 產生真正六格式 synthetic originals 與經 canonical review/publish 的合成分類；原檔路徑在 state-dir/demo-originals/originals.json。使用 UI 上傳，沒有預種法律結果。

```bash
python scripts/kb01/rc1.py stop --state-dir "$HOME/.local/share/kb01-rc1"
python scripts/kb01/rc1.py start --state-dir "$HOME/.local/share/kb01-rc1"
```

Stop 保留 PostgreSQL volumes、versioned S3 originals 與 persona manifest；start 重用同一資料，不重新 seed 身份。不得把此測試 Host bind 到 0.0.0.0 或以 tunnel 公開。

版本：`KB01-Technical-UAT-RC1`。只限 `LOCAL / ISOLATED TECHNICAL TESTING ONLY`。使用既有 React 前端、UAT Host、PostgreSQL、Redis、versioned S3 與 canonical Workers；不是 Production Auth，也不提供公開網址。

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Acceptance / Production UAT / Paid Internet LLM = NOT EXECUTED；Reviewer Approval = Pending；MASTER reconciliation = INPUT_REQUIRED；PR29 Draft；Main merge 未授權；Release Tag 不變；Stage2 NOT STARTED。

## 本輪已執行的交付身份

產品 `4593a355d0711a9ba955b1624926a2ec71d60430`，PR29 Draft。本獨立 evidence branch 只保存測量／操作說明，不是新的產品 Head；請 clone 完整 repository 後 checkout 上述產品 Commit。Linux x86_64／Python3.12.14／Node24.19.0／PostgreSQL17.11+pgvector0.8.7／Redis7.4.11 已實測；Windows 原生及 Docker Desktop/WSL 未獨立驗收。

本輪工具映像漏洞掃描已完成，但134 High +1 Critical（套件 finding，並非135個不同CVE）的正式處置未批准。`TECHNICAL_UAT_CANDIDATE=READY` 僅表示隔離合成資料功能可操作；`RC1_TECHNICAL_ACCEPTANCE=BLOCKED_SECURITY_REVIEW_PENDING`，不等於可部署／可對外提供服務。不要使用敏感文件或對外暴露 synthetic session。
