# Phase 1G Repository Start Gate

核對時間：2026-10-02T15:15:10.847348+08:00（Asia/Shanghai）。

**Phase 1G Entry Recommendation = ALLOWED**，依據已簽發的 [Phase1G_entry_decision.md](Phase1G_entry_decision.md)。

**Phase 1G Start Gate = PASS**。

本 Gate 驗證 PR #9 整合後的實際 main；不是沿用 PR merge preview 或 Phase 1E baseline。PR #9 已由 agent 審查 canonical model、migration、tenant/API、quality/review、scope isolation、snapshot 與既有 regression 邊界，未發現 blocking findings；沒有聲稱取得獨立人工 GitHub approval。之後標記 Ready 並按使用者指示以 merge commit 合併。

| Repository assertion | Verified result |
|---|---|
| PR #9 | Ready → merged / closed |
| Reviewed PR source head | `817ef5f2762dfc95295f0fcf109506059774dce5` |
| Actual tested main / merge SHA | `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95` |
| Merge parents | `efa8fd395e2fe63254660370b386bf3fe71a942d` + reviewed PR head |
| Main source tree vs reviewed PR head | Identical; full ancestry preserved |
| Alembic main head | **0006_phase1f** |
| Remote main CI | [36976551120](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/36976551120); Run Number 98, Attempt 1, **SUCCESS** |
| CI trigger / runner checkout | workflow_dispatch on main / `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95` |
| Full PostgreSQL/runtime pytest | **142 passed / 0 skipped / 0 deselected** |
| Phase 1F PostgreSQL schema | **29/29 PASS** |
| Architecture executable checks | **77/77 PASS** |
| Phase 1A runtime / checkpoint / restart / resume / retry | **25/25 PASS** |
| Phase 1B / 1C / 1D / 1E schema | **16/16; 20/20; 15/15; 22/22 PASS** |
| Phase 1A–1F complete regression | **PASS** |
| Tenant / Source-of-Truth / checkpoint ownership | **PASS** |
| Remote artifact ID | `11214060286` |
| Remote artifact digest | `sha256:d1da94207a7bbcf258b2ac70094f241ab66d60508ede084d11d721b1d80e7667` |
| Release tag | `v3.6-phase1f-pass`, annotated object `2419e1a51816801873bc7b610e82639b68e0da2c` |
| Tag target | `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95`; pushed after main CI PASS |
| Phase 1G branch | `phase1g-retrieval-rag`; created and pushed from tested main |
| Branch creation SHA | `fe4e1bb8b0002aa9b4c68106bea5ebc0898fed95` |
| Open stacked PR dependency | None; PR #5–#9 integrated into main |

Evidence: [main_gate_manifest.json](evidence/phase1g-start-gate/main_gate_manifest.json), [review result](evidence/phase1g-start-gate/pr9_review_result.json), [merge result](evidence/phase1g-start-gate/merge_result.json), [release/branch result](evidence/phase1g-start-gate/release_branch_result.json), [remote API/Checks](evidence/phase1g-start-gate/main_remote/empirical_summary.json), [complete local main log](evidence/phase1g-start-gate/main_local/ci_complete.log).

Local corroboration used an isolated fresh PostgreSQL 17.11/Redis 8.0.2 database against the same exact main SHA. Remote CI used PostgreSQL 16 + pgvector and Redis 7. Both full gates passed independently. The remote artifact stores the complete runner log (62031 bytes, SHA256 `d0348ad8dddfe3ac9bf4171c891dd50cd7977f3fca5624895411ee87366ef027`). Archive redirects remain restricted in this environment; remote ZIP was not locally downloaded. Raw API/Checks evidence and the separately measured complete local log are preserved without substituting their hashes for the GitHub artifact digest.

The release tag stays on the tested main SHA. This preflight report and evidence are documentation-only additions on Phase 1G branch; they are not represented as code tested by the main CI. No Phase 1G retrieval/reranking/RAG or compliance feature has been implemented in this preflight step. The specific Phase 1G implementation scope and Exit Gate have been requested and are not yet supplied.
