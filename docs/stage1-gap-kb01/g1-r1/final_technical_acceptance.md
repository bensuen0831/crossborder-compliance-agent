# KB01-G1-R1 最終技術交付

N_PLUS_ONE_FIX = PASS
TOOLCHAIN_REPRODUCIBILITY_CONTROLS = PASS（外部保存／clean-host依賴另列）
TECHNICAL_UAT_CANDIDATE = READY — LOCAL / ISOLATED SYNTHETIC TECHNICAL TESTING ONLY
FUNCTIONAL_REGRESSION = PASS
RC1_TECHNICAL_ACCEPTANCE = BLOCKED — SECURITY_REVIEW_PENDING

| 新exact產品Head Gate | 實測 |
|---|---|
| Source | `4593a355d0711a9ba955b1624926a2ec71d60430` |
| Full PostgreSQL | 1332PASS，4個獨立CI執行 |
| Failed / errors / skipped / deselected | 0/0/0/0 |
| 原完整backend IDs / 新增 | 1315全部保留 / 17 |
| Local directed PG | 320PASS=303原用例+17新增 |
| Architecture | 456/456PASS |
| Runtime | 25/25PASS |
| Frontend | 180PASS |
| Typecheck/lint/build/i18n | PASS |
| Browser | 89/89PASS=88原必跑+1RC1角色 |
| Browser retries | 0 |
| Mandatory CI | 12/12SUCCESS |
| Actual checkout | 22/22MATCH |
| Source/test/fixture hashes | 739 verified |
| Artifact ZIP / OCI image | 34 /7 verified |
| Alembic | 0024唯一head，0001–0024 byte unchanged |

**阻塞項：** 固定實際工具映像134High+1Critical package findings尚無正式批准處置。Trivy scan execution PASS不等於security acceptance PASS；未冒簽review或risk acceptance。已交付能啟動及操作的隔離技術候選，不能宣稱整體RC1驗收、正式部署或法律接受PASS。

已完成兩項程式修復；安全Reviewer需確認依賴漏洞的修復／風險處置。長期registry/簽署/保存與獨立clean-host restore=EXTERNAL_DEPENDENCY；GitHub短期OCI artifact已真實保存驗證。MASTER原文及指定正式Reviewer仍待提供，不重複推定批准。

CI/source/log/artifact/test IDs與safe hashes見 `evidence/stage1-gap-kb01/g1-r1/`。本文件在獨立evidence branch封存，不推進產品Head/Main；完整CI只對上面產品SHA成立。舊source50/04的CI取消與local全套143終止被保留為superseded development，未借用PASS。曾有scanner掛載路徑及CI fixture少一case兩項開發失敗，均最小修正後對新459重新跑12個workflows；未加browser retry／刪除skip或弱化assertion。


PR29 保持 Draft／未合併；Main060cbb5與 v3.7-stage1-e2e-pass 不變。Formal Reviewer Approval=PENDING；MASTER full-text reconciliation=INPUT_REQUIRED；Formal requirement change approval=NOT_VERIFIED。KB01-F1=BLOCKED_EXTERNAL_EVIDENCE_PENDING，LEGAL L2／Production Deployment=NOT ACCEPTED；Real Regulatory Acceptance／Production UAT／Paid Internet LLM=NOT EXECUTED；Stage2=NOT STARTED。

補充contract-tests子集的實際 skipped/deselected 數見 `supplemental_contract_subsets.json`，與四個完整PG suite分開，沒有冒稱subset為全量。
