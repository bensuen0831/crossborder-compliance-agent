# Phase 1F Preflight Repository Status

檢查日期：2026-10-02。下列 Start Gate 區段記錄實作前的 main ancestry 與完整回歸；末段記錄 Phase 1F 實作後的遠端核對。

**Phase 1F Start Gate = PASS**

**Safe to create phase1f-knowledge-scope from verified main = YES**

Phase 1A–1E Technical / Empirical Gates = PASS。Phase 1E Delivery / Entry Governance = PASS。Phase 1F Entry Recommendation = ALLOWED。

## Verified repository base

| 項目 | 結果 |
|---|---|
| Current / tested remote main SHA | `efa8fd395e2fe63254660370b386bf3fe71a942d` |
| Final Phase 1E empirical baseline SHA | `1b54030dfc8147beaf19c6ab2ead9f428191a8af` |
| Latest integrated Phase 1E source head | `51e838caeb4655d3911b3bf81d88d88331205971` |
| main contains original Phase 1B head | PASS：2c50591f8a0853e8df86674f42a76ea48a59d4b2 是 main ancestor |
| main contains original Phase 1C head | PASS：d1834908982c1e858aa1bed5fdd70c17ef04be37 是 main ancestor |
| main contains original Phase 1D head | PASS：51429bc147a843f67ef43e88f7ae61094f6144f1 是 main ancestor |
| main contains Phase 1E / delivery head | PASS：51e838caeb4655d3911b3bf81d88d88331205971 是 main ancestor |
| Migration files | 0001_phase1a 至 0005_phase1e 均存在 |
| Runtime source tree vs integrated Phase 1E | src / tests / scripts / smoke / alembic / workflow / dependencies 沒有 diff |
| Remote main drift check before release | PASS；測試後重新讀取 remote main 仍為相同 SHA |
| Release tag target | v3.6-phase1e-pass → verified main SHA `efa8fd395e2fe63254660370b386bf3fe71a942d` |
| Phase 1F branch base | phase1f-knowledge-scope 從 verified main SHA 建立 |

## Actual integration ancestry

遠端在本次復查前已完成 merge：#8 合入 Phase 1D、#7 合入 Phase 1C、#6 合入 Phase 1B，再由 #5 合入 main；#4 亦合入 main。這些是從 actual Git commit parents / ancestry 觀察的已完成操作，本次沒有再 merge 或 retarget 已完成 PR。原 Phase heads 全部保留，沒有 squash / ancestry loss。

```text
efa8fd395e2fe63254660370b386bf3fe71a942d Merge pull request #4 from bensuen0831/phase1a2-empirical-trigger-2
26670bcea486b96bf799a6bc1df04b74a59244e6 Merge pull request #5 from bensuen0831/phase1b-domain-foundation
a889b311fe3ab4a995e0f21114ff19b4407d3a78 Merge pull request #6 from bensuen0831/phase1c-metadata-registry
9152239a9cfbc309d4d55e8838ec40b18096fa4e Merge pull request #7 from bensuen0831/phase1d-document-intelligence
65d1d6a5515411f210db8dbd1c3f5f334e863d5a Merge pull request #8 from bensuen0831/phase1e-context-resolution
```

此前 main=1807cc7 與 BLOCKED_BY_REPOSITORY_INTEGRATION 是歷史 preflight 快照；目前 Git objects 已證明 repository integration 完成，不能沿用該舊狀態。

## Actual main full regression

使用原有 smoke/run_gate.sh，對實際 main SHA 在 fresh PostgreSQL 16 + pgvector、Redis 執行，不是對先前 local merge preview 執行。

| Gate | Result |
|---|---|
| Full PostgreSQL/runtime pytest | **82 passed / 0 skipped / 0 deselected**；1 個既有 Starlette deprecation warning |
| Fresh Alembic upgrade / head | **PASS；0005_phase1e** |
| Phase 1E schema | **22/22 PASS** |
| Architecture executable checks | **59/59 PASS** |
| Phase 1A runtime / checkpoint / restart / resume / retry | **25/25 PASS** |
| Phase 1B Domain / Persistence / tenant / Source of Truth | **PASS** |
| Phase 1C Registry / Admin / snapshot / metadata | **PASS** |
| Phase 1D Document Intelligence / parser / provenance / async parse | **PASS**；schema 15/15 |
| Phase 1E Context Resolution / formal Inventory / Flow | **PASS** |
| LangGraph checkpoint ownership | **PASS**；Domain metadata / Alembic 不擁有 checkpoint schema |
| Tenant / Source-of-Truth regression | **PASS** |

[Gate manifest](evidence/phase1f-main-start-gate/main_start_gate_manifest.json)、[full log](evidence/phase1f-main-start-gate/local-regression/ci_complete.log)、[pytest log](evidence/phase1f-main-start-gate/local-regression/pytest_full.log)、[runtime assertions](evidence/phase1f-main-start-gate/local-regression/runtime_verify.json)。

## Evidence identity boundary

這是 actual main 的本地 empirical regression，不宣稱為新 GitHub Actions run。Start Gate 驗證當時 GitHub API 被 egress policy 阻擋，因此該 main 本地 gate 沒有 remote Run ID / Artifact ID。後續 API 連線已恢復；Phase 1F 自身的遠端證據另列於正式 manifest，不能回填成該歷史 main 測試。

先前已核實 Phase 1E remote baseline 仍為 Run 36955707413、Run Number 83、SUCCESS、Artifact 11205402817、digest sha256:03b064bad2f93c577bdea98777e1a76ff70e1e594247ee20c49bb991a63d1fd5、tested SHA 1b54030；它與本次 actual main regression 是不同測試 identity。

本輪用戶指定的 main full regression / ancestry / checkpoint / tenant / Source of Truth Start Gate 已按上述本地實測滿足。未來 Phase 1F Formal Exit Gate 仍需其自身 final remote CI，不能沿用本次 Start Gate 當 Phase 1F implementation 已完成。

## Old trigger PR review

- PR #4 head 1d381d7c5d2cdbcf73f7b78cc77b44a8451c5d6a 已是 actual main ancestor，Git history 顯示已 merge；無需再關閉。
- PR #3 head 8dfb4fc644b6c36bc09bb573b0a835511bf1fa39 不是 main ancestor，且包含唯一有效邏輯：load_authoritative_workflow_context 與 _assert_checkpoint_matches_domain 存在於 #3 port/runtime adapter，main 中沒有。不能視為純 trigger / 無唯一內容，當時未自行關閉；本輪不將其改動併入已驗收 baseline。最新 API 顯示 PR #3 已 closed、未 merged，本輪沒有操作其狀態。當時未取得 live API 狀態；最新 PR 狀態已另存 repository_final_status.json。

## Coding boundary

Start Gate 階段僅完成 main integration verification、tag / branch 與 documentation / evidence 更新，當時尚未新增 Phase 1F code；後續已按任務完成 Phase 1F foundation，沒有進入 Phase 1G。Phase 1F branch 的治理文件 commit 與已測 main / release tag SHA 不同，不能宣稱其新 commit 已被本次 main Gate 測試。

## Phase 1F delivery-time repository verification

GitHub REST 已核對：main 仍為 `efa8fd395e2fe63254660370b386bf3fe71a942d`；PR #5–#8 全部已 merged。Phase 1F PR #9 base 為 main，保持 draft/open；本輪沒有 merge PR。實測實作與最後 CI identities 見 [phase1f_final_remote.json](evidence/phase1f_final_remote.json)，repository 狀態見 [repository_final_status.json](evidence/phase1f/repository_final_status.json)。歷史 main 的 82-test／0005 gate 與 Phase 1F 的 142-test／0006 gate 保持不同 identity。
