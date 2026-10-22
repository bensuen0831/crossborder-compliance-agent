# Real PostgreSQL performance comparison

Baseline39c3581，same-process old/new reader同一資料、tenant與engine，三語系／四page size。每個new read三次；完整JSONSHA與數量由tests/test_kb01_taxonomy_batch_postgres.py實測產出。不是Mock SQL count，也不是production SLA。

| Lifecycle，100 rows，en-US | Before SQL | After SQL | 同次舊read秒 | 新read median秒 |
|---|---:|---:|---:|---:|
| DRAFT | 302 | 5 | 0.320781 | 0.015758 |
| ACTIVE | 402 | 5 | 2.480517 | 0.035040 |
| MIXED | 352 | 5 | 1.124199 | 0.023593 |

G1前一時段ACTIVE100 median2.536919秒獨立保留；不可把它與本次不同環境／時段值當同次速度比。完整定向pytest37 PASS，所有case identities及XML需一併封存。

本輪修復授權：使用者提交 STAGE1-GAP-KB01-G1-R1；不是正式 Reviewer Approval。產品仍沿用 PR29 Draft／原分支，Main060cbb5、Release Tag不變。F1 BLOCKED、Legal L2／部署未接受、Production UAT／Paid LLM 未執行、MASTER原文INPUT_REQUIRED、Stage2 NOT STARTED。所有最終 PASS 必須以新 exact-head 完整 CI 與獨立 evidence 證明；此設計／定向紀錄不能替代。
