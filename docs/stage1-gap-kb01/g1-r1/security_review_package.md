# Formal Security Reviewer Package

產品 `733a7483439cd919c186ed0064b8f3752904ebb6`；前一產品 `4593a355d0711a9ba955b1624926a2ec71d60430`；前一獨立證據 `d9adf53241c8e86ec264913713bf52b2fedcc36e`。本輪工程核實／建議不是正式 Reviewer 決定。

正式安全審查=PENDING，RC1正式技術接受仍BLOCKED。產品scope只有Containerfile明確gpg alternative、既有source proof保留v20/v21並新增v22，加入cached Containerfile/inventory guard與tamper回歸；0001–0024、正式法律owner、runtime/checkpointer、RBAC與UI業務邏輯均未改。最新Head所有mandatory CI必須重跑，不能沿用459。

Critical CVE-2026-6653：Debian官方tracker將trixie `2.12.7+dfsg+really2.9.14-2.1+deb13u3`列vulnerable；runtime `xmlParserVersion=20914`證實底層仍2.9.14，不能被2.12.7字面誤導。實測LibreOffice libmergedlo.so連結libxml2.so.2。上游CNA建議>=2.11.0；Debian tracker第一個unstable修復版本2.14.5+dfsg-0.1、目前forky/sid2.15.4。這不是已核實的trixie安全更新。官方將trixie列no-dsa/minor不等於本項目已接受Trivy Critical風險。

官方修復commit463bbeeca1805b5c4828f50d0fefc4eebaf620df實際涉及7個C/header/test檔案、276新增/227刪除並變更entity/parser結構，不是可無證據套用的一行補丁。本輪沒有混用sid ABI、替換系統libxml而假稱保持受支持來源，也未自維護未充分驗證的parser fork。下一步需Dependency Maintainer選定vendor-supported backport/受審base遷移路徑，驗證6格式/引用/OCR/安全/容量後再進行新exact-head gate；如等待供應商，任何time-bound剩餘風險接受只能由適用版本的正式Reviewer批准。

暴露：掃描器、LibreOffice與OCR會處理不受信任原件；libclamav/libtesseract/libtiff相關High不能僅以tool image或無直接呼叫免除。其他transitive套件的精確可利用性未證明，保持UNKNOWN/PENDING，沒有誤報／不適用判定。Sandbox network=none/read-only/non-root/dropcap/no-newprivileges/cpu2/pids64/受控RAM與mounts降低blast radius，但不修復native UAF、解碼或資源消耗漏洞。

RC1 API與React目前是host processes；PostgreSQL/Redis/S3不是這135筆工具映像scan的同一範圍。不得把tool image Trivy報告宣稱為完整host、DB、Redis或production application image審查。此次修復選擇必需gpg而不安裝dirmngr/gnupg/gnupg-l10n/gpg-agent/gpgsm/pinentry，保留所有10個critical parser/scanner可執行檔與原hash；實際apt dependency/inventory/scan與真實測試驗證移除。

供審者核對：逐筆135ledger +新DB發現、官方45份tracker raw/hash及CNA、兩次同DB新舊scan、SBOM284套件、OCI blobs/config/manifest/archive、APT簽章與package hashes、新head CI/checkout/log/artifact/test IDs、F1/MASTER缺口。Formal reviewer name/approval/scope/expiry均留Pending，不發Review Request、不改Draft、不merge/tag。
