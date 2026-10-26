# 第一例操作及待交接材料

此案例包沒有預先決定法律 outcome。`input_manifest.json` 的空值必須由責任方提供真實 canonical IDs；它是準備清單，不能直接當成合法 Intake 或已批准 Gold 匯入。

| 步驟 | 操作者／最小材料 | 留存證據與通過條件 | 本輪 |
|---|---|---|---|
| 選定來源／目的法域及資料流 | 業務負責人：scope、product、typed facts、source != destination | 實際 node/edge/item links 與 ProjectVersion；非純文字流向 | 待提供 |
| 提供真實原始法規 | 授權用戶：官方來源、原檔、版本、日期、授權範圍 | 原檔 hash、KnowledgeVersion、條文及修訂／廢止關係 | 待上傳 |
| 解除檔案處理安全阻塞 | 工程師修復／正式安全 Reviewer | 受影響映像修復、新 SBOM/掃描、適用版本的處置；不能 AI 接受 Critical | Pending |
| 上傳及治理 | operator / reviewer / publisher | 掃描→解析→review→publish→index；條文引用可開原文 | 未執行 |
| 配置即時模型 | API 帳戶負責人：Provider、model/deployment、Secret Store、額度、資料使用限制 | 非 health/cache 的 workflow/preparation 即時請求；無 fixture fallback | 未提供 API 憑證 |
| 建空白項目、上傳需求 | 業務用戶 | 使用 requirements.txt 或經授權非敏感需求；doc/parse/source trace | 僅空白項目入口已 smoke |
| 確認候選 | 業務用戶 | 無決定時 Confirm 拒絕；明確接受／編輯／拒絕；actor/time | 完整案例未執行 |
| 執行正式分析 | 業務用戶 | project / workflow / snapshot / retrieval / invocation IDs；formal chain；非測試硬編碼 | 未執行 |
| 查看引用及結果 | 業務用戶 | Classification、Risk、Path、措施、LegalBasis、Evidence、原文，與 pins 一致 | 未執行 |
| 缺資訊／人工審核 | 已授權 reviewer | canonical ReviewTask / current-role decision / resume 或 successor；不改舊 Snapshot | 未執行 |
| 重載及重登 | 業務用戶 | same Snapshot、結果 semantics、來源／模型 pin；禁止 latest 重算 | 空白 draft 重登已 smoke；正式結果未執行 |
| 獨立 Gold | 項目負責人任命的法域專家 | appointment、case/Gold/source verification exact versions、identity/date/approval | 未提供 |
| 比對與差異 | QA + 獨立專家 | 授權 canonical reader 的 observed semantics 與預先批准 expected 完整比對；記錄法律錯誤及修復 | NOT_EXECUTED |

五類 F1 條件沿用原定義：授權原檔；來源／版本／有效性核實；獨立預期答案；正式身份／日期／版本／批准；案例／法域／標準。不得自行把法律專家欄位填成 approved，也不得把同機重啟當成異機還原。

問題紀錄最少包含 source SHA、時間、角色（非密碼）、project/version/snapshot/run、引用 locator、預期／實際差異、request ID、脫敏證據 hash。不要提交 raw provider body、API Key、登入 Cookie、個資或完整敏感需求。必要時私有保存原檔，只在 evidence 留 hash / reference。
