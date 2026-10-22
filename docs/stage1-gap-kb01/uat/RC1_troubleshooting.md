# RC1 操作與故障排查

```bash
python scripts/kb01/rc1.py health --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py diagnose --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py logs --service backend --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py logs --service frontend --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py logs --service services --state-dir /absolute/private/kb01-rc1
python scripts/kb01/rc1.py logs --service tools --state-dir /absolute/private/kb01-rc1
```

僅讀取專用目錄 log；輸出最多80行並移除常見 signed query／DB credential。分享前仍需人工檢查，CLI redaction 不等於完整 DLP。Backend uses access_log=False。

`PORTS_ALREADY_IN_USE`：先核對是否本 RC1 已跑，勿 kill 全機程序。`CONTAINER_OWNER_MISMATCH`：不能接管同名他人容器。DB/S3 startup失敗：先 stop owned RC1 再 start，保留 private logs、原件與 evidence，不用 docker system prune。S3 resume 使用同一 credentials/data/bucket；不得手工刪 originals 令測試通過。

TLS/proxy/download錯誤：保留 injected proxy/CA，不能 --insecure。首次 APT snapshot 可慢，查看 forward progress；不要重複啟動 builder。Official CVD 與 synthetic EICAR DB 不能混用；UAT 必須記錄驗證過的 official main/daily/bytecode。

Reset 只清除這一個 instance 的 owned DB/Redis volumes，原 S3/private files 另行封存；這是破壞測試 DB 的命令，先保存需要的測試證據。從 status 取得準確 instance ID：

```bash
python scripts/kb01/rc1.py reset --state-dir /absolute/private/kb01-rc1 --confirm-reset <exact-instance-id>
python scripts/kb01/rc1.py start --state-dir /absolute/private/kb01-rc1
```

不接受 global reset/drop/prune，也不更動 main、release tag、其他服務或正式資料庫。

版本：`KB01-Technical-UAT-RC1`。只限 `LOCAL / ISOLATED TECHNICAL TESTING ONLY`。使用既有 React 前端、UAT Host、PostgreSQL、Redis、versioned S3 與 canonical Workers；不是 Production Auth，也不提供公開網址。

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Acceptance / Production UAT / Paid Internet LLM = NOT EXECUTED；Reviewer Approval = Pending；MASTER reconciliation = INPUT_REQUIRED；PR29 Draft；Main merge 未授權；Release Tag 不變；Stage2 NOT STARTED。
