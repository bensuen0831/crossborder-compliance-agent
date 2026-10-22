# RC1 使用者技術驗收案例

版本：`KB01-Technical-UAT-RC1`。只限 `LOCAL / ISOLATED TECHNICAL TESTING ONLY`。使用既有 React 前端、UAT Host、PostgreSQL、Redis、versioned S3 與 canonical Workers；不是 Production Auth，也不提供公開網址。

KB01-F1 = BLOCKED — EXTERNAL_EVIDENCE_PENDING；LEGAL L2 / Production Deployment = NOT ACCEPTED；Real Regulatory Acceptance / Production UAT / Paid Internet LLM = NOT EXECUTED；Reviewer Approval = Pending；MASTER reconciliation = INPUT_REQUIRED；PR29 Draft；Main merge 未授權；Release Tag 不變；Stage2 NOT STARTED。

依次操作，記錄實際結果；以下是預期，不是預填人類 UAT PASS。UAT-17 自動 SQL counter 證據由新增 PostgreSQL regression 提供，不新增暴露 SQL 的前端debug endpoint。

| ID | 操作 | 步驟 | 預期 | 人類結果 |
|---|---|---|---|---|
| UAT-01 | 新增國家／地區 | Author 建草稿，送審；Reviewer批准、Publisher發布 | 分類樹顯示正式發布版本 | Pending |
| UAT-02 | 修改國家名稱 | 建立新版本並完成治理 | 新畫面／DB一致；舊版可追溯 | Pending |
| UAT-03 | 新增法規類型 | 建立分類並發布 | 可用作文件分類 | Pending |
| UAT-04 | 修改／停用分類 | 新版本／停用治理 | 關聯與統計按正式版本 | Pending |
| UAT-05 | PDF上傳 | demo-originals真PDF→掃描→解析 | exact original、parse/status可讀 | Pending |
| UAT-06 | 其餘五格式 | DOC/DOCX/TXT/HTML/XHTML逐一上傳 | 每檔來源、解析與citations可查 | Pending |
| UAT-07 | 多文件／資料夾 | 批量選取，確認 mapping | 逐檔技術狀態與失敗原因 | Pending |
| UAT-08 | RAR/ZIP | 真RAR4/RAR5/ZIP預覽再確認 | 安全成員、原件、分類與進度 | Pending |
| UAT-09 | 無Excel導入 | 不提供任何manifest完成batch | 可成功，Excel僅可選 | Pending |
| UAT-10 | 編輯元資料 | Author更改文件metadata | CAS、版本與audit保留 | Pending |
| UAT-11 | 新增版本 | 同一文件建立後繼版本 | 原版本與pins仍可追溯 | Pending |
| UAT-12 | 刪未引用草稿 | 先impact preview，再依policy刪除 | 具權限且無保留限制可刪 | Pending |
| UAT-13 | 刪已引用文件 | 使用已被snapshot/hold引用的synthetic資料 | 拒絕破壞性操作，stable reason | Pending |
| UAT-14 | 審核／發布 | 不同AUTHOR/REVIEWER/PUBLISHER操作 | 無自批越權，ACTIVE/READY分離 | Pending |
| UAT-15 | 統計 | 新增、分類、archive後重讀 | SQL count/交叉維度與資料一致 | Pending |
| UAT-16 | 隔離拒絕 | B讀A真ID；RESTRICTED操作 | 403/404 fail closed，不洩漏資料 | Pending |
| UAT-17 | 列表100條 | demo --taxonomy-rows100；執行定向PG測量 | 每頁<=5SQL，完整JSON parity | Pending |
| UAT-18 | 重啟保存 | 記下document/version IDs及hash→stop/start→重讀 | 同資料、原件、audit；重新登入 | Pending |
