# RC1 快速啟動

先閱讀 installation guide 與 known limitations，尤其安全掃描的未接受 findings。取得 PR29 產品分支的指定 RC1 commit；正式 `v3.7-stage1-e2e-pass` 仍是舊 main，不能拿它當 RC1。

```bash
git clone https://github.com/bensuen0831/crossborder-compliance-agent.git
cd crossborder-compliance-agent
git switch fix/stage1-regulatory-knowledge-management
git rev-parse HEAD
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/kb01/rc1.py start --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py demo --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py status --state-dir /absolute/private/kb01-rc1
```

將 `/absolute/private/kb01-rc1` 換成你有寫入權限的專用目錄。首輪需下載固定 dependency/toolchain 與官方 ClamAV CVD，並產生 SBOM、OCI archive、漏洞報告；不是瞬間啟動。

實際程序啟動後，本機網址：`http://127.0.0.1:15173/admin?admin_resource=knowledge-management`；Backend liveness：`http://127.0.0.1:18010/health/live`。這些是**執行該命令的電腦**的 loopback，不能在另一台電腦打開 Codex Cloud 的 127.0.0.1，也沒有持續公開 Cloud URL。

登入 A（AUTHOR），再用 Reviewer / Publisher 按鈕切換角色。demo 產生真正六格式 synthetic originals 與經 canonical review/publish 的合成分類；原檔路徑在 state-dir/demo-originals/originals.json。使用 UI 上傳，沒有預種法律結果。

```bash
python scripts/kb01/rc1.py stop --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py start --state-dir /absolute/private/kb01-rc1
```

Stop 保留 PostgreSQL volumes、versioned S3 originals 與 persona manifest；start 重用同一資料，不重新 seed 身份。不得把此測試 Host bind 到 0.0.0.0 或以 tunnel 公開。

版本：`KB01-Technical-UAT-RC1`。只限 `LOCAL / ISOLATED TECHNICAL TESTING ONLY`。使用既有 React 前端、UAT Host、PostgreSQL、Redis、versioned S3 與 canonical Workers；不是 Production Auth，也不提供公開網址。

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Acceptance / Production UAT / Paid Internet LLM = NOT EXECUTED；Reviewer Approval = Pending；MASTER reconciliation = INPUT_REQUIRED；PR29 Draft；Main merge 未授權；Release Tag 不變；Stage2 NOT STARTED。
