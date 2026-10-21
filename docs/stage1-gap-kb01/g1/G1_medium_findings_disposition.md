# G1 Medium Findings — Engineering Recommendations / Formal Decision Pending

準備日期：2026-10-21T04:10:03.812889+00:00。PR [#29](https://github.com/bensuen0831/crossborder-compliance-agent/pull/29)，Product Head `39c3581ca455df4e3ce9760ed2deab8905a5f588`，Main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`。本材料屬 AI 審查協調與工程建議，不是正式 Reviewer Approval，也不代表風險接受或合併授權。G0 Evidence `1193eb35096806fc0f885c0181de98b87d61980a` 與先前技術驗收 `bd30290c577e8ac16cbb88a20a0535553fb6bd00` 均為獨立證據身份。

## KB01-G0-001：taxonomy list N+1

固定來源 `src/crossborder_compliance/infrastructure/persistence/knowledge_taxonomy.py`：`_view` 242、actor reads 251/260、`list` 388。G1 真實 PostgreSQL、兩個隔離 synthetic tenant 各 100 列，ACTIVE 經 canonical submit/review/publish；每 page size 讀取三次。不改 production source；不以 mocked SQL 估算。

| Lifecycle | Page size | SQL statements/read | Median seconds，n=3 |
|---|---:|---:|---:|
| DRAFT | 1 | 5 | 0.007082 |
| DRAFT | 4 | 14 | 0.017537 |
| DRAFT | 25 | 77 | 0.089807 |
| DRAFT | 100 | 302 | 0.368497 |
| ACTIVE | 1 | 6 | 0.029187 |
| ACTIVE | 4 | 18 | 0.104122 |
| ACTIVE | 25 | 102 | 0.629162 |
| ACTIVE | 100 | 402 | 2.536919 |

公式 `2 + 3 × DRAFT rows + 4 × rows with active version`。上限 page_size=100，全 ACTIVE 實測 402 queries，median 2.536919s，三次 2.513563 / 2.536919 / 2.572379s。這是 loopback 工程測量，非 production 負載、P95 或 SLA 驗收。僅作網路往返估算，402 次序列查詢在 5/20ms RTT 下約增加 2.01/8.04s，並非遠端實測。

資料：[taxonomy_measurements.json](../../../evidence/stage1-gap-kb01/g1/taxonomy_measurements.json)；probe 在同目錄 `taxonomy_query_probe.py`。執行需既有測試環境、`PYTHONPATH=src:tests` 與獨立 fresh-0024 PostgreSQL DB；不得指向 production。Probe 以 canonical fixture 建資料並用 SQLAlchemy `before_cursor_execute` 計數，不儲存 SQL 參數／用戶原文。

**工程建議：FIX_BEFORE_MERGE；正式決定：PENDING_FORMAL_REVIEW。**

擬議最小方案：保留 tenant/kind/query/alias/localized/enabled filters、COUNT、穩定 `(code, definition_id)` 排序、limit/offset；只批量載入當頁 selected versions（ACTIVE exact ID，否則 latest version_no）、creator 與 latest actor。以有界 SQL/window/批量 maps 取代逐 row 查詢；joined versions 仍驗 tenant/kind，不能以 cache 跨租戶共用。建議 <=5 reads/page 為未實現目標，不宣稱已修好。

驗收必須比對 DRAFT/ACTIVE/mixed 的完整 JSON、排序、alias/localization/filter/page、tenant isolation、missing actor/version 邊界與權限撤銷；page 1/4/25/100 查詢數有界。預期無 schema 改動。估計 0.5–1.5 工程日，加完整 CI wall time，屬規劃估算，沒有已指定 owner 或承諾日期。

延後影響：行政列表每頁查詢線性增加，網路延遲及 DB 併發成本高，可能拖慢使用者與 worker 共用 DB；本次沒有證實資料錯誤或跨租戶洩漏。若 Reviewer 選 DEFER/ACCEPT，必須記錄實名 owner、期限、可接受 page/latency/容量條件、監控與追蹤 issue；目前皆未批准。

## KB01-G0-002：native toolchain 浮動依賴與重現性

`scripts/kb01/Containerfile` 第 2 行 `FROM debian:trixie-slim` 為 mutable tag；第 7 行 apt 安裝未鎖套件版本／repository snapshot。這不證明已發現惡意套件，但 Git alone 不能重建同一二進位解析／掃描環境。

G1 對 G0 本地已存在的 immutable image config ID `sha256:15fbf1cb1c8349e018de488f31ec4ae366b6ecebbbced32934d0127644d787ac` 作離線、read-only、non-root inventory：289 installed binary packages、10 關鍵 executable hashes、5 parser source hashes、APT source stanzas。其 `RepoDigests=[]`，不是已發布 OCI manifest digest；沒有可核實的 historical FROM builder attestation，local base image unavailable。

| 套件 | 觀測版本 |
|---|---|
| ClamAV / freshclam | 1.4.3+dfsg-1 |
| libarchive-tools / libarchive13t64 | 3.7.4-4+deb13u1 |
| libreoffice-writer | 4:25.2.3-2+deb13u8 |
| poppler-utils | 25.03.0-5+deb13u4 |
| python3.13 | 3.13.5-2+deb13u5 |
| tesseract-ocr | 5.5.0-1+b1 |

APT 觀測為 Debian `trixie trixie-updates` 與 `trixie-security`、main、Debian archive keyring Signed-By。這是已安裝資料／source 設定，不是當時 `.deb` 的完整 authenticated provenance。套件與可執行檔詳見 [toolchain_inventory.json](../../../evidence/stage1-gap-kb01/g1/toolchain_inventory.json)。

已交付 [SPDX 2.3 SBOM](../../../evidence/stage1-gap-kb01/g1/local_tool_image_sbom.spdx.json)，通過 pinned official schema、唯一 SPDXID 與 relationship references 核查，詳見 [validation](../../../evidence/stage1-gap-kb01/g1/sbom_validation.json)。僅 G0 本地映像 inventory；未驗證 license/download metadata 為 NOASSERTION，非 file-complete dependency graph，不能冒稱歷史 CI image SBOM。Vulnerability scan = NOT EXECUTED；published retention location = 未指定；restore test = NOT EXECUTED。ClamAV engine 與獨立 official CVD signature/version/hash 也不可混為一談。

**工程建議：FIX_BEFORE_MERGE（最小 reproducibility/provenance gate）；正式決定：PENDING_FORMAL_REVIEW。**

擬議策略與需正式確認項目：

1. 基底以經審查的 per-platform manifest digest 固定，保留來源／platform／取得時間；不要臆填本地未知 digest。
2. 用經驗證的 signed APT InRelease/Packages、受控 snapshot/套件版本與 `.deb` hashes；記錄 source package/版本、binary hashes。不要用關閉簽章驗證換取可 build。
3. 每個實際 CI tool image 都產生 SBOM、Containerfile/parser source hashes、builder provenance 與漏洞掃描結果，綁定該 image digest；禁止用本地 SBOM 代替 CI。
4. 由維運指定受控 registry，以 immutable manifest digest 保存；如另存 OCI archive，保存 archive SHA256、object version、存取與簽章驗證。Owner、位置、稽核保存期限尚待指定，不能宣稱已實施。
5. 在乾淨 runner 以 digest 還原並驗 executable/source hashes；missing artifact fail closed，不可悄悄 fresh build。保留歷史 image 供 replay。
6. 建立定期及 security-advisory refresh/triage、時限及責任人；更新產生新 digest、重新安全掃描與全套 CI，舊 release tag 不移動。Official CVD DB 需獨立受控更新與驗證。
7. 保留 network=none、non-root、read-only、cap-drop、資源限制和白名單；不能以重現性為由弱化 sandbox。

估計 1–2 工程日，加 registry/retention policy 協調與全量 CI；不是已批准計畫。延後可能使未來 rebuild 的 parser/scanner 行為不同，降低歷史重現、漏洞 triage 與 rollback 可稽核性。正式 Reviewer 應明確決定 merge 前最低控制與部署前後續控制，不能因 Production Deployment 未驗收而自動接受此風險。

## 正式處置紀錄

| Finding | Engineering recommendation | Approved disposition | Approver / record / date | Owner / deadline |
|---|---|---|---|---|
| KB01-G0-001 | FIX_BEFORE_MERGE | Pending | Pending | Pending |
| KB01-G0-002 | FIX_BEFORE_MERGE | Pending | Pending | Pending |

合法處置為 `FIX_BEFORE_MERGE / ACCEPT_RISK / DEFER_WITH_OWNER / BLOCK`。目前沒有任何批准、產品修復或已接受／延期風險。G0 的 non-blocking-for-review 是工程評估，不是正式處置。若批准修復，須在既有產品分支最小提交、新 head 全套必要回歸、actual CI checkout 證明及獨立 evidence，新增改動由 Reviewer 再確認；不得沿用 source39 的 PASS。
