# Phase 1G Entry Decision

Phase: **1F — Knowledge Ingestion & Scope Resolver Foundation 的正式 Exit / Entry 治理簽發**。
簽發日期：2026-10-02（Asia/Shanghai）。

**Phase 1F Technical Gate = PASS**

**Phase 1F Empirical Gate = PASS**

**Phase 1F Delivery Closure = PASS**

**Phase 1F Formal Exit Gate = PASS**

**Phase 1G Entry Recommendation = ALLOWED**

本文件在 documentation-closure PR head 完成完整遠端 CI 後簽發。簽發依據為 GitHub Actions REST、Checks 的實測摘要、artifact metadata 與相同 code 的本地完整 PostgreSQL/runtime evidence；不是沿用 Phase 1E baseline。GitHub Checks 的 counts 與 source/runner identities 已獨立核對。

| Final pre-issuance empirical identity | Verified result |
|---|---|
| PR | [#9](https://github.com/bensuen0831/crossborder-compliance-agent/pull/9), base main；未 merge |
| Final tested PR head SHA | `1784f10409012918aae709e2a5dc492edbe272e2` |
| Runner merge SHA | `1113ebbcd7534f456e0157024884936aeda6070a` |
| Final Run ID / number / attempt | [36968764193](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/36968764193) / 92 / 1 |
| Workflow conclusion | SUCCESS；mandatory-runtime-smoke 與 contract-tests 均 SUCCESS |
| Artifact ID | `11210258936` |
| Artifact digest（GitHub 提供） | `sha256:5fe9dcefcdd266127b5fa081bfb5f31c53dc5c33d57bbff5385d11c1ca5d07bc` |
| Full PostgreSQL/runtime pytest | **137 passed / 0 skipped / 0 deselected** |
| Phase 1F schema | **29/29 PASS** |
| Architecture checks | **77/77 PASS** |
| Alembic head | **0006_phase1f** |
| Phase 1A official runtime/checkpoint/restart/resume/retry | **25/25 PASS** |
| Phase 1B / 1C / 1D / 1E schema | **16/16; 20/20; 15/15; 22/22 PASS** |
| Phase 1A–1E regression | **PASS**；完整 suite 保留所有既有 tests |
| Required Phase 1F delivery documents | **16/16 已交付**；本文件是第 17 份治理文件 |
| Full gate log | GitHub artifact 內 `ci_complete.log`；62033 bytes |
| Full gate log SHA256（runner 實測） | `35b7a05ef4169c086f88d76bd44d1daf9caf5a29ed3311a50f1410fdb194500f` |

Formal Exit assertions:

| Gate | Result |
|---|---|
| Repository Start Gate | PASS |
| Knowledge Source | PASS |
| Canonical Knowledge Model | PASS |
| Knowledge Versioning | PASS |
| RegulatoryStructureNode | PASS |
| Structure-aware Chunking | PASS |
| Knowledge Binding | PASS |
| Knowledge Quality | PASS |
| Translation Provenance | PASS |
| Evidence / Citation | PASS |
| Permission Scope | PASS |
| Product Scope | PASS |
| Jurisdiction Scope | PASS |
| Scenario Scope | PASS |
| Industry Scope | PASS |
| Data Category Scope | PASS |
| Multi-product Isolation | PASS |
| Product Conflict Fail-safe | PASS |
| Hard Filter Contract | PASS |
| Index Foundation | PASS |
| Snapshot Pinning | PASS |
| Tenant Isolation | PASS |
| PostgreSQL Migration | PASS |
| Architecture Rules | PASS |
| Phase 1A–1E Regression | PASS |
| Required Delivery Documents | PASS |
| Final Remote CI Evidence | PASS |

Source of Truth：PostgreSQL canonical knowledge 與既有 Phase 1B/C source、binding、legal structure、citation、review、model registry foundation。Runtime Scope 只使用 Phase 1E formal context；FTS/vector/registry 是 derived。Quality/review precede ACTIVE；snapshot pin immutable；permission/source revocation fail closed。

Governance commit boundary：本簽發及其 final identifiers 更新只改 documentation/evidence；與 tested PR head 的 domain、API、migration、tests、CI workflow、dependencies 無 diff。Final tested PR head 是簽發前的最後完整 CI 對象，不能將尚未測試的簽發 commit SHA 偽裝成該 run 的 head。簽發 commit 後的完整 CI 另作 governance verification。

Known exclusions：只完成 Phase 1F foundation。Canonical structured JSON ingestion、deterministic whitespace token count、test storage/embedding adapters 的實際範圍見交付文件。PDF legal auto-import、actual provider execution、affected-project impact calculation 及所有 Phase 1G retrieval/reranking/RAG、classification、regulation applicability、risk、country compliance、compliance path、legal answer 與 Production Agent 均未實作。

Evidence storage limitation：remote full gate log / JUnit / schema / runtime / architecture evidence 已由 GitHub Actions artifact 保存；artifact ID/digest 及 runner log hash 已核對。本環境的 archive redirect 仍受 egress policy 限制，沒有聲稱已本地下載 remote ZIP，也沒有將本地 log hash 當成 GitHub artifact digest。已保存的 API/Checks records 在 [evidence/phase1f](evidence/phase1f)，正式 manifest 為 [phase1f_final_remote.json](evidence/phase1f_final_remote.json)。這不影響已核實的 remote gate 與遠端原始 log 保存。

本輪已完成並停止在 Phase 1F。ALLOWED 是下一輪的進入建議；未自行開始任何 Phase 1G 實作。
