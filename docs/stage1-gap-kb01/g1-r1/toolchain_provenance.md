# Toolchain provenance and acceptance interpretation

來源只有既有Containerfile＋五個stdlib parser/archive檔案＋bounded inventory helper，不複製repo/credentials進image。Base manifest/config raw bytes以sha256核實linux/amd64。APT來源、signed release signatures、index/archive hashes、source versions保存於image及inventory。所有新image/provenance必須對照實際source hashes。

`image_id`為Docker config identity；`oci_manifest_digest`為可還原OCI archive的manifest content identity。Artifact archive SHA256、GitHub artifact ZIP digest與source SHA屬不同層，不可互換。OCI exporter/restore逐一驗size/hash，無extractall；local content roundtrip不宣稱clean-host restore。

每個CI使用的新image獨立產生SBOM、tool hashes、Trivy report與build provenance。沒有虛構歷史CI builder attestation，也沒有把G1本地289package SBOM移植成新版證據。Package inventory不代表license audit或zero vulnerabilities。Current vulnerability DB與critical findings需如實披露；正式risk acceptance待Reviewer。

Production long-term immutable registry/retention owner與policy仍未指定。GitHub90天artifact只有實際upload完成、metadata/digest核實後才可記錄短期retention PASS；未完成要保留EXTERNAL_DEPENDENCY。

本輪修復授權：使用者提交 STAGE1-GAP-KB01-G1-R1；不是正式 Reviewer Approval。產品仍沿用 PR29 Draft／原分支，Main060cbb5、Release Tag不變。F1 BLOCKED、Legal L2／部署未接受、Production UAT／Paid LLM 未執行、MASTER原文INPUT_REQUIRED、Stage2 NOT STARTED。所有最終 PASS 必須以新 exact-head 完整 CI 與獨立 evidence 證明；此設計／定向紀錄不能替代。
