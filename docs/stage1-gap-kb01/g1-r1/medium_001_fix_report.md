# KB01-G0-001 修復結果

N_PLUS_ONE_FIX = PASS。沿用既有 list owner、COUNT／filters／排序／分頁，selected versions、creator、latest actor 改三次 tenant-bound batch read，非空頁固定5SQL；空頁2SQL。ACTIVE 仍取 exact active_version_id；非 ACTIVE 取最高version_no；沒有跨租戶 cache 或第二 Metadata SoT。

真正 PostgreSQL，同一資料與連線環境，以 `git show 39c3581...:knowledge_taxonomy.py` 的舊 reader 作獨立測試 oracle，DRAFT/ACTIVE/MIXED × page1/4/25/100完整JSON相等；三locale、缺actor/version、租戶隔離、權限、exact-active不被較新draft覆蓋均有回歸。既有30＋新增7 taxonomy tests=37PASS。

額外實證舊enabled-filter在多draft時丟失correlation而CardinalityViolation。最小修復重用tenant-bound selected-version expression，保持 intended enabled semantics；該原本失敗請求的修復獨立列出，未冒稱可以對不存在的舊response作parity。

ACTIVE100，3次paired讀取中位：402→5 SQL，2.627473→0.036336秒。全部12個頁面／lifecycle組合與完整response SHA256見 taxonomy_performance.json／taxonomy_response_parity.json。這是隔離PG測量，非生產SLA。

實際測試產品 `4593a355d0711a9ba955b1624926a2ec71d60430`；完整新Head回歸與actual jobcheckout封存於本獨立evidence。

PR29 保持 Draft／未合併；Main060cbb5與 v3.7-stage1-e2e-pass 不變。Formal Reviewer Approval=PENDING；MASTER full-text reconciliation=INPUT_REQUIRED；Formal requirement change approval=NOT_VERIFIED。KB01-F1=BLOCKED_EXTERNAL_EVIDENCE_PENDING，LEGAL L2／Production Deployment=NOT ACCEPTED；Real Regulatory Acceptance／Production UAT／Paid Internet LLM=NOT EXECUTED；Stage2=NOT STARTED。
