# Medium 001：Bounded taxonomy page projection

保留原 COUNT／definition filters／排序／分頁，再以三次 tenant-bound SQL 讀取 selected versions、creator、latest actor。ACTIVE 取 exact active_version_id；draft 用 DISTINCT ON 最高 version_no；不載入全部歷史版本，不使用跨租戶 cache。Response 使用與單筆 reader 同一 projection。

真實 PostgreSQL 以固定39c3581 Git blob 原 reader 作 oracle；DRAFT/ACTIVE/MIXED × page1/4/25/100 × 三locale完整 JSON 相等；每個新 read固定5 SQL。空頁2 SQL，缺version/actor保持null，權限仍由 server拒絕。新增counterexample發現原enabled filter在多draft時丟失correlation而CardinalityViolation；最小修復重用原tenant-bound selected-version expression，不改enabled語義，另作明確回歸。

既有30＋新增7 taxonomy tests共37 PASS；另3 lifecycle safety tests PASS。所有source-scope manifests保留，沿用有限Git blob proof新增此次授權檔案，不能用live工作檔hash自我認證。後續新Head全量Gate尚需獨立確認。

本輪修復授權：使用者提交 STAGE1-GAP-KB01-G1-R1；不是正式 Reviewer Approval。產品仍沿用 PR29 Draft／原分支，Main060cbb5、Release Tag不變。F1 BLOCKED、Legal L2／部署未接受、Production UAT／Paid LLM 未執行、MASTER原文INPUT_REQUIRED、Stage2 NOT STARTED。所有最終 PASS 必須以新 exact-head 完整 CI 與獨立 evidence 證明；此設計／定向紀錄不能替代。
