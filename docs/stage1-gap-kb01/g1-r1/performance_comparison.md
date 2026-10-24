> Historical source459/d9 measured report retained. Current product733a748 security changes/status: final_technical_acceptance.md and security-review/. Old counts/timings below are not new-head PASS.

# 同環境 PostgreSQL paired comparison

每個case相同資料/engine，舊新reader各3次讀取，保留每次wall time及SQL count；未mock SQL計數。完整JSON逐次相等，digest保存。

| Lifecycle | Rows | Before SQL | After SQL | Before median s | After median s |
|---|---:|---:|---:|---:|---:|
| DRAFT | 1 | 5 | 5 | 0.008806 | 0.008139 |
| DRAFT | 4 | 14 | 5 | 0.017273 | 0.006456 |
| DRAFT | 25 | 77 | 5 | 0.090935 | 0.009094 |
| DRAFT | 100 | 302 | 5 | 0.352884 | 0.017628 |
| ACTIVE | 1 | 6 | 5 | 0.029567 | 0.007432 |
| ACTIVE | 4 | 18 | 5 | 0.110082 | 0.008806 |
| ACTIVE | 25 | 102 | 5 | 0.646783 | 0.015916 |
| ACTIVE | 100 | 402 | 5 | 2.627473 | 0.036336 |
| MIXED | 1 | 6 | 5 | 0.015078 | 0.006297 |
| MIXED | 4 | 17 | 5 | 0.051854 | 0.006922 |
| MIXED | 25 | 92 | 5 | 0.300380 | 0.011509 |
| MIXED | 100 | 352 | 5 | 1.158433 | 0.024106 |

G1既有2.536919秒是不同session的歷史測量，未拿它計算同環境加速比。舊查詢依page行數線性增加，新查詢非空頁固定5SQL；沒有把計數查詢或授權／actor讀取排除。

PR29 保持 Draft／未合併；Main060cbb5與 v3.7-stage1-e2e-pass 不變。Formal Reviewer Approval=PENDING；MASTER full-text reconciliation=INPUT_REQUIRED；Formal requirement change approval=NOT_VERIFIED。KB01-F1=BLOCKED_EXTERNAL_EVIDENCE_PENDING，LEGAL L2／Production Deployment=NOT ACCEPTED；Real Regulatory Acceptance／Production UAT／Paid Internet LLM=NOT EXECUTED；Stage2=NOT STARTED。
