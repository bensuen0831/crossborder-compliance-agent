# F1 external evidence verification

產品 `733a7483439cd919c186ed0064b8f3752904ebb6`；前一產品 `4593a355d0711a9ba955b1624926a2ec71d60430`；前一獨立證據 `d9adf53241c8e86ec264913713bf52b2fedcc36e`。本輪工程核實／建議不是正式 Reviewer 決定。

F1=BLOCKED—EXTERNAL_EVIDENCE_PENDING；LEGAL L2=NOT ACCEPTED。定義來自repo `real_regulatory_acceptance_readiness.md` lines1–13（記錄使用者已確認F0/F1拆分），typed F0 owner與原G1記錄相互吻合，未另創F1要求。

五條必備：授權真實原件；官方來源／法域／版本／有效性核驗；獨立專家法律預期答案；正式任命／身份／日期／版本／批准紀錄；明確案例／法域／評估標準。每條責任角色、取得方式、目前null evidence見machine checklist。現有schemas、模板、synthetic expert、原始法規本身、LLM答案或L1法規不能代Gold／專家批准。

本輪readonly inventory只查看既有RC1 tenantA，僅輸出四類acceptance metadata的dataset/lifecycle數量與文檔版本數，不讀出原件內容、actor credentials或cookie。該scope未找到獨立批准的真實Gold/任命；不把本地absence推廣成外部組織不存在材料。F0真PG機制／拒絕用例可驗證實作，但不是F1法律準確性PASS。未重試Drive登入、未繞過權限、未假設已獲授權專家或付費LLM。

Registry長期保存與獨立主機還原不在已確認F1五條法律條件內。它們分屬Master0.2.4的Backup/Restore、Phase0Part20C的PG backup/PITR/object-versioning/restore及G1-R1工具映像可重用保存證據。GitHub實際OCI artifact短期保存可核對；正式retention期限、簽署／registry owner與clean-host restore profile尚待Maintainer決定。不能因此取消運維gate，也不能將同機重啟或Docker archive roundtrip寫成independent-host PASS。

外部取得：Project owner透過canonical本地六格式/批量上傳提供授權法規；正式指定獨立法域專家與授權範圍；走既有 `REGULATORY_EXPERT_AUTHORIZATION`、`REGULATORY_SOURCE_VERIFICATION`、`REGULATORY_ACCEPTANCE_CASE`、`REGULATORY_GOLD_REVIEW` 的draft→review→publish，精確pin原始KnowledgeVersion/clauses/hash、case semantics、appointment與Gold版本。API `/api/v1/admin/knowledge-management/acceptance`已有templates/records/transitions/readiness；不新增第二Review/Knowledge authority。不得import body提供approved_by/approved_at冒充批准。

Required externals：真實原件與授權證明、source/effectivity核驗、獨立expert appointment/Gold/批准、cases/criteria；另有Registry retention owner/policy及真正另一台host提供的restore receipt。各自對法律F1／安全／運維的影響分開列，不互相冒充。完成材料準備不等於正式審查通過。
