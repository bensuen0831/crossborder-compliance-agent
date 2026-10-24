> Historical source459/d9 measured report retained. Current product733a748 security changes/status: final_technical_acceptance.md and security-review/. Old counts/timings below are not new-head PASS.

# KB01-G0-002 修復及剩餘處置

已修復 floating base/APT universe 與 CI映像 provenance 缺口。linux/amd64 Debian base `sha256:4876fdea29cac1a33a3195f1eb1952feb1fca7dd6dd00be3e2f1879cf20d34d2` 已核對實際manifest/config；Debian+security snapshot20261021T000000Z，HTTPS／signed InRelease／index／.deb hashes／package/source version 保存。只關閉 historical snapshot Valid-Until，未關閉GPG/TLS。

新實際映像290個installed packages、10個critical executable hashes、五個parser source hashes、Containerfile/inventory helper hashes均綁實際OCI identity。SPDX2.3通過固定官方schema。七個新CI image獨立生成provenance/SBOM/scan/OCI archive，逐一驗ZIP digest及所有OCI blobs，package inventory及關鍵工具hash均與固定來源本機映像一致。Docker config ID、OCI manifest、archive hash、GitHub ZIP digest各自記錄，不互換。

GitHub七份實際Archive均已下載驗證，可在到期前重取；API顯示expires_at=2027-01-20T05:23:24Z。這是短期artifact retention，不是長期registry、簽署或獨立clean-host還原。Local OCI roundtrip PASS；long-term retention／clean-host restore=EXTERNAL_DEPENDENCY。

掃描執行 PASS，但 security acceptance=BLOCKED_REVIEW_REQUIRED：實際每份映像 LOW302/MEDIUM250/HIGH134/CRITICAL1/UNKNOWN5，共692個package findings；HIGH/CRITICAL合計44個不同CVE。Critical CVE-2026-6653/libxml2 未回報FixedVersion。這不是已證實可利用性，亦不能推定可接受風險；沒有隱藏unfixed、抑制finding或冒簽risk acceptance。

Network isolation/non-root/read-only/drop capabilities/resource limits/malware scan/archive sandbox維持；新映像重新通過parser、RAR4/RAR5/ZIP、容量及安全回歸。Official CVD main/daily/bytecode的hash與ClamAV engine/executable各自保存。

Formal Security Reviewer仍須評估可達性與處置。若要求依賴更新，須最小新產品commit與完整新exact-head gate；不能以本次成功測試取代新source證據。Medium重現性修復已完成，最終安全批准未完成。


PR29 保持 Draft／未合併；Main060cbb5與 v3.7-stage1-e2e-pass 不變。Formal Reviewer Approval=PENDING；MASTER full-text reconciliation=INPUT_REQUIRED；Formal requirement change approval=NOT_VERIFIED。KB01-F1=BLOCKED_EXTERNAL_EVIDENCE_PENDING，LEGAL L2／Production Deployment=NOT ACCEPTED；Real Regulatory Acceptance／Production UAT／Paid Internet LLM=NOT EXECUTED；Stage2=NOT STARTED。
