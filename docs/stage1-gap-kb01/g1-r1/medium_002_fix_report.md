# Medium 002：Native tool source/identity controls

Containerfile固定經registry content hash與platform查核的Debian linux/amd64 manifest `sha256:4876fdea29cac1a33a3195f1eb1952feb1fca7dd6dd00be3e2f1879cf20d34d2`。APT固定20261021T000000Z Debian/security snapshot，保留GPG驗證及HTTPS/CA；historical Valid-Until只對該固定snapshot關閉。下載有60秒timeout／一次transport retry，與Browser Retries=0不同。

新image_inventory在實際build中保存三份signed InRelease及VALIDSIG、indices hashes、下載deb對signed index SHA256的逐件比對、package/source versions、critical binaries。build_tools對這個新image產生SPDX2.3（pinned official schema）、OCI layout archive/manifest digest、config ID、完整blob驗證／local Docker roundtrip，再對實際image跑pinned Trivy及保存DB/report hashes。Config ID不冒充registry manifest digest。

CI對每個實際工具映像保存SBOM/provenance及獨立OCI artifact（90天request，實際到期/metadata以GitHub artifact API為準）。長期registry、簽署與乾淨獨立host還原不自動視為已驗收；local roundtrip也不冒充獨立restore。

Scanner execution與security acceptance分開。不得ignore-unfixed、抹除findings或自動接受risk；High/Critical未處置則security_acceptance=BLOCKED_REVIEW_REQUIRED。早先舊G0 image掃描有687項（Critical1/High133），這不是新image結果；新image必須重新掃描並以其actual SHA封存。原offline/nonroot/read-only/capdrop/resource sandbox與ClamAV CVD獨立身份保持。

本輪修復授權：使用者提交 STAGE1-GAP-KB01-G1-R1；不是正式 Reviewer Approval。產品仍沿用 PR29 Draft／原分支，Main060cbb5、Release Tag不變。F1 BLOCKED、Legal L2／部署未接受、Production UAT／Paid LLM 未執行、MASTER原文INPUT_REQUIRED、Stage2 NOT STARTED。所有最終 PASS 必須以新 exact-head 完整 CI 與獨立 evidence 證明；此設計／定向紀錄不能替代。
