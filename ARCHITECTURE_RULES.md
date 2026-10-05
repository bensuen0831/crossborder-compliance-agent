# ARCHITECTURE_RULES.md — 跨境數據合規智能體 V3.6

> 本文件是 Phase 1+ Coding 的強制架構守門規則。任何違反項不得以「先做 Demo」為由繞過；若確需例外，必須提交 Architecture Decision Record，說明分類（DATA / CONFIG / RULE / PROMPT / KNOWLEDGE / TEMPLATE / REGISTRY / CORE ALGORITHM）、原因、替代方案與回滾策略。

1. Frontend 不含合規判斷。
2. Frontend 不 Hard Code 業務 Metadata。
3. LangGraph Node / Router / Subgraph 不直接讀 DB。
4. LangGraph Node / Router / Subgraph 不直接調 LLM Provider。
5. Agent 不直接讀 ORM。
6. Agent 不直接查 pgvector。
7. Agent 不 Hard Code Country Rule。
8. Skill 不自行選 Model Provider。
9. RuleEngine 不調 Agent。
10. KnowledgeService 不調 Agent。
11. RiskEngine 不修改 Legal Obligation。
12. DocumentEngine 不重新判定法律義務。
13. Enterprise Template 不覆蓋 Regulatory Requirement。
14. Admin Draft 不直接進 Runtime。
15. Vector Similarity 不得突破 Scope。
16. 正式數量統計不得由 LLM 生成。
17. Agent / Skill 必須 Typed Schema。
18. 跨模組不得傳對方 ORM Object。
19. Workflow 必須固定 Analysis Snapshot。
20. Human Edit 必須 Invalidate 下游。
21. Visualization 只消費 Structured Result。
22. Audit 使用 Event-driven。
23. Runtime Knowledge 不修改 Knowledge。
24. 新增資料不得要求修改 Main Workflow。
25. Web / VSCode / API 不得建立獨立 Compliance Engine。
26. Domain Result 與 Presentation 分離。
27. LangGraph 是 Workflow Orchestration Runtime，不是 Domain Logic Layer。
28. LangGraph Checkpoint 不等於 AnalysisSnapshot，兩者不得合併。
29. Production LangGraph 必須使用 Durable Checkpointer；`InMemorySaver` 只可用於開發 / 測試。
30. LangGraph Node / Router / Subgraph 不得直接依賴 ORM、Vector DB、Provider SDK。
31. Human Review 必須使用 Durable Interrupt / Resume 語義；Interrupt Node 的 Side Effect 必須 Idempotent。
32. Raw LangGraph Stream / Event Format 不得直接成為 Third-party API Contract；必須轉換為 Canonical `WorkflowEvent`。
33. LangGraph Store / Checkpoint 不得取代 KnowledgeService / Regulation Knowledge Base / RAG。
34. Large Document、Binary、全量 Knowledge Chunk 不得放入 LangGraph State，只保存 Reference / ID / Small Structured Result。
35. Country / Product / Scenario 差異不得通過新增專屬 Graph Hard Code；必須經 Registry / Scope / Rule / Capability 動態處理。
36. LangGraph Node Retry 與 Task Queue Retry 必須分責；Business Conflict 不得當作 transient failure Retry。
37. `thread_id` 必須由 Backend 生成與授權，不信任 Client 自行傳入作資源邊界。
38. Workflow Graph Version / LangGraph Runtime Version 必須納入 AnalysisSnapshot / Audit Provenance。
39. 自有 workflow table 與 LangGraph Checkpointer 不得同時保存同一份完整 Graph State，避免雙 Source of Truth。
40. LangGraph-specific API 只允許存在於 Workflow Adapter / Graph Runtime 邊界，不得滲入 Domain Model。
41. CountryComplianceSkill 必須作 Facade，Country Capability 由 Registry / Config 組合，不得一國一套 Root Graph。
42. Regulatory Document Requirement 必須由通用 Skill + Metadata / Rule / Template 驅動，不得為每種文件建立固定 Python Skill。
43. Rule Engine 禁止使用 `eval()` / `exec()` 或任意 Python Expression；必須使用 Safe Rule DSL / Validated AST。
44. Project Party / Legal Role 必須結構化；ResponsibilityAgent 不得只依賴組織名稱自由文本。
45. Classification 必須綁定 ClassificationScheme / Level / Jurisdiction / Version / Evidence，不得使用單一全局固定分類。
46. Agent API / Skill API 不得繞過 CapabilityExecutionService、Auth、Scope、Snapshot、Policy、Audit。
47. `REDACTION_REQUIRED` 必須經 DataRedactionService，Redaction 失敗不得直接使用 External Model。
48. LLM Wiki 必須經 Source Binding / Evidence Validation / Review / Publish，不得自動生成後直接 ACTIVE。
49. Diagram / Vision Result 必須保留 bbox / page-region provenance；Vision 只產生 Candidate Fact / Flow。
50. LangGraph Runtime Context 與持久化 State 分離，DI Service / Secret 不得存入 Graph State。
51. LangGraph 必須設 recursion / max-step guard，避免 Router / Graph 無限循環。
52. Checkpoint Retention / Delete / Legal Hold / Tenant Cleanup 必須有正式 Policy。
53. Regulatory Monitoring 自動抓取結果不得未經 Review 直接替換 ACTIVE Regulation。
54. Governance / Cost Model 若進入計算模式，公式必須使用 Safe Expression Engine，不得 Python eval。
55. Stage 1 Result 不得只輸出自然語言與表格，必須包含強制可視化區域。
56. Workflow Stepper 必須基於真實 LangGraph / AnalysisStageResult 狀態，不得使用假進度。
57. KPI / Count / Distribution 必須由 Backend Structured Result 計算，Frontend / LLM 不得估算正式數值。
58. Data Transfer Visualization 與 Compliance Path Visualization 必須為結構化可交互視圖。
59. Visualization 不得從 LLM Narrative 重新解析生成正式結論。
60. Compliance Status 與 Risk Level 必須使用獨立視覺語義，不得互相映射。
61. Legal Basis 必須可追溯 Regulation Version / Article or Section / Official Source / Evidence。
62. Data Item UI 必須能回溯 Original Document Page / Section / Table / Row。
63. VS Code 不需複製完整 Web Visualization，但必須能取得一致結果並 Open Visualization。
64. Third-party API 返回 Visualization DTO 時不得暴露 LangGraph Raw Event / Internal State。
65. Export 必須保留核心 Data Transfer / Risk / Compliance Path Visual Result。

## Phase 0.1 Source-of-Truth Normalization — Mandatory Addendum

66. `classification_results` 是 authoritative formal classification result；不得維護第二套 `data_classifications` 正式結果 Source of Truth，兼容需要只能使用 read-only view/projection。
67. `RegulatoryStructureNode` 是 canonical legal structure；Article / Section 只作 node type / locator / compatibility projection，不得另建平行 authoritative legal structure。
68. `WorkflowStageView` 只是由 `AnalysisStageResult` 產生的 Presenter Projection；不得持久化為第二套 Workflow/Legal Result Source of Truth。
69. `HumanReviewNode` 屬 LangGraph Workflow Node，不得註冊為 Agent；Human Review 必須經 `ReviewTask` + durable interrupt/resume。
70. `LegalBasis ↔ RuleHit` 必須支援 M:N；API 使用 `rule_hit_ids[]` 或等價 link contract，Persistence 使用 association relation。
71. Visualization `latitude/longitude` 只可來自 canonical/geocoded location data；LLM / Agent / Presenter 不得虛構精確座標。未知精度必須保留 nullable + location precision/status。
72. API Idempotency 與 Workflow Execution Idempotency 必須分離：`api_idempotency_records` 與 `execution_idempotency_records` 不得混用 key namespace、重試語義或 retention policy。
73. `Stage1ComplianceResult` 必須顯式包含 `cross_border_results[]`；不得要求消費者從 `data_flow_results` 或 narrative 推斷正式跨境結論。
74. Visualization Snapshot / Cache / Export 不是法律結果 Source of Truth；其內容必須可由同一版本 Structured Domain Result 重建。
75. LangGraph Checkpointer internal schema 由官方 checkpointer setup/upgrade path 管理；Domain Alembic 不得自行建立、修改、重命名或解讀其 internal tables。


## Phase 1C Metadata / Registry / Admin Addendum

76. Registry 是 runtime projection，不是業務 Source of Truth；authoritative data 必須保留於 Database / Versioned Config。
77. Open-source / self-hosted LLM 必須經 ModelProviderAdapter / LLMService 以 API 接入；Agent / Skill / LangGraph 不得綁定 model serving framework、base URL 或具體 model name。
78. Model replacement 只允許透過 Model Registry / Model Config，不得要求修改 Agent / Skill / Graph。
79. Prompt 必須版本化並經 Registry；Business Prompt 不得 hard-code 在 Agent。
80. Admin Draft 不得被 Runtime Registry 解析為 ACTIVE。
81. Registry Refresh 必須在 Domain Publish 成功 commit 後執行；必須使用 Transactional Outbox 或等價可靠機制，避免 DB / Registry split-brain。
82. Existing AnalysisSnapshot 不得因 Registry Refresh 靜默切換版本；resume 必須使用 snapshot-pinned approved version。
83. Model credential 真值不得存入 Registry DTO / Frontend / Audit Log；metadata persistence 只可保存 secret_ref。


## Phase 1D Document Intelligence Addendum

84. Document Binary 不得進 LangGraph State；State 只保存 ID / Reference / Small Structured Result。
85. Canonical Document Structure 是正式解析 Source；LLM Narrative 不得取代 Canonical Structure。
86. OCR 是 fallback，不得覆蓋原始 Document Version；原始 binary 必須保持 immutable object-storage reference。
87. Vision / Diagram Result 只能產生 Candidate Fact / Flow / Relation，不得直接產生法律結論、Classification 或 Compliance Path。
88. 所有正式 Extracted Fact / Candidate DataItem / Candidate DataFlow 必須有 SourceTraceRef，可回溯 DocumentVersion / ParseRun / StructureNode / locator / original hash。
89. Spreadsheet 不得只轉成 plain text；row / column / header / formula / merged-cell provenance 必須保留。
90. Document Analysis Count 必須由 Backend structured persistence programmatic aggregation，不得由 LLM 估算。
91. Parse Run 必須 versioned；AnalysisSnapshot 必須 pin 指定 ParseRun，Resume 不得靜默切換。
92. Parser / OCR / Vision Provider 必須 Adapter 化；Provider-specific SDK 不得進 Domain / Application / LangGraph。
93. Document Parse Quality 未達 Gate 時，不得靜默進正式分析；必須保留 WARNING / REVIEW_REQUIRED / FAILED 狀態。


## Phase 1E Context Resolution / Formal Data Inventory / Data Flow Addendum

94. Phase 1D Candidate 不得直接成為正式 Compliance Input；任何 Candidate → Formal Object 必須保留 Resolution / Validation Record。
95. Product Context 必須由 Registry / Evidence / Explicit User Selection 解決；產品業務值不得 hard-code 於 Domain / Application Service。
96. Explicit Product Selection 與 Document-detected Product 發生實質衝突時，必須輸出 `PRODUCT_CONTEXT_CONFLICT`，不得靜默覆蓋任一來源。
97. 未選 Product 但已有 Document Evidence 時必須 Document-first；不得因未選 Product 自動擴大至所有 Product Knowledge Scope。
98. Formal `data_items` 必須可回溯所有 Candidate / SourceTrace；Candidate 不得因 Resolution 而刪除。
99. Original Field Count、Normalized Data Item Count、Data Group Count 必須分離並由 structured persistence programmatic aggregation。
100. Formal DataFlow 必須使用 authoritative `data_flow_nodes` / `data_flow_edges` / `data_item_flow_links`，不得以 narrative 或第二套 formal flow store 取代。
101. Jurisdiction Context 只表示位置/管轄上下文，不等於 Regulation Applicability 或 Cross-border Legal Status。
102. AI / Semantic Resolution 只能形成 Candidate / Confidence / Suggestion；不得直接 merge Formal DataItem 或形成正式 Context。
103. Data Item / Data Flow / Context 更新必須 versioned 並可由 AnalysisSnapshot pin；既有 Snapshot / Resume 不得靜默切換新 Context。

## Phase 1E.1 delivery evidence references

Phase 1E implementation baseline: source SHA `6d05588a02752dc5479658f63bc4b6ab8c29331e`, runner merge SHA `fac2806d819694b4fb8210179ec90348f73791ca`, GitHub Actions Run `36950913643`, Attempt `1` (user-provided verified baseline).

Baseline results: full PostgreSQL/runtime pytest **82 passed / 0 skipped / 0 deselected**, Phase 1E schema **22/22 PASS**, executable architecture checks **59/59 PASS**, Alembic head **0005_phase1e**, Phase 1A–1D regressions **PASS**.

Actual executable checks and limitations are documented in [architecture_rule_check.md](architecture_rule_check.md). Scope and source-of-truth boundaries are in [Phase1E_context_resolution_design.md](Phase1E_context_resolution_design.md); evidence attribution is recorded in [baseline_manifest.json](evidence/phase1e/baseline_manifest.json).

These references document the existing rules; they do not change implementation or add rule behavior. The documentation closure head requires a new complete CI result before any Phase 1F entry decision. Baseline/local artifacts are not substitutes for that final run.


104. Knowledge Platform is canonical PostgreSQL knowledge, not a Vector DB.
105. Scope Resolver decides allowed scope only; no retrieval or ranking.
106. Tenant, permission, lifecycle, version, product and jurisdiction hard filters precede similarity search.
107. PRODUCT_SPECIFIC knowledge incompatible with effective_product_scope is excluded before retrieval.
108. Unresolved/conflicting product context cannot broaden product-specific knowledge.
109. Every KnowledgeChunk preserves version, structure, citation and source provenance.
110. Vector and FTS indexes are derived, never authoritative knowledge.
111. Knowledge version, binding, index and embedding configuration are immutable snapshot pins.
112. AI translation without human review cannot become official evidence.
113. Knowledge cannot become ACTIVE without quality and independent durable review.
114. Phase 1F consumes formal Phase 1E context, never infers context again from raw documents.

115. Retrieval consumes Phase 1F KnowledgeScope / KnowledgeFilterSpec and cannot broaden scope.
116. Tenant / Permission / Lifecycle / Version / Product / Jurisdiction hard filters precede similarity search.
117. FTS / pgvector / Search Engine / Graph Index are derived and never Knowledge Source of Truth.
118. Hybrid merge is deterministic, versioned-policy driven, with independent score provenance.
119. Rerankers only reorder allowed candidates; injected identifiers are dropped and audited.
120. Scope must be revalidated after reranking and before evidence assembly.
121. EvidencePack retains complete citation, source, version, index, policy and snapshot provenance.
122. Retrieval results / EvidencePack / RAGContextPack are derived evidence, not legal Source of Truth.
123. Knowledge Sufficiency is computed from versioned policy and verified evidence, never an LLM decision.
124. Generic GLOBAL / shared evidence cannot alone establish jurisdiction-specific sufficiency.
125. External augmentation preserves original tenant / permission / jurisdiction / product scope.
126. LLM memory and unverified web are discovery-only and cannot become LegalBasis.
127. T1/T2 external evidence requires authority / provenance / effective-date / content-hash validation.
128. Runtime external evidence cannot automatically become ACTIVE canonical knowledge.
129. Referenced external evidence must be immutable, snapshot-pinnable and reproducible.
130. Insufficient / partial / conflicted evidence must retain nonempty actionable fallback guidance.
131. Fallback guidance is not Candidate / Final Compliance Path and cannot fabricate legal obligations.
132. Retrieval, sufficiency and trust parameters come from versioned policy / config / registry, never Agent routing.

133. Normal content publication automatically propagates through the existing transactional registry outbox to runtime projections and derived retrieval assets. New analyses require ACTIVE + READY assets. Manual refresh/reindex is recovery tooling only; existing snapshots never change their knowledge/index/embedding/policy pins.

## Phase 1H Safe Rule Engine / Formal Classification Addendum

134. Rule runtime accepts only statically validated typed AST over declared flat fields. Rule DSL cannot invoke Python, imports, reflection, shell, filesystem, network or models. Missing/type-invalid inputs cannot silently become a formal decision.
135. Rule Engine is pure Domain evaluation over authorized Typed RuleFactContext and snapshot-pinned approved rule versions; it cannot fetch Database, Knowledge, retrieval, LLM or Agent services.
136. Formal ClassificationResult must retain subject, tenant/project, jurisdiction, scheme version, RuleHits, authorized evidence, source facts, reason codes and analysis/context pins. It persists only in canonical classification_results; narrative and model output are not accepted as a formal result.
137. Missing DataItem or insufficient facts/evidence produces a typed NOT_APPLICABLE/INSUFFICIENT_INPUT outcome without fabricated classification. Non-matched rules require review only when the input facts already require review.
138. Executable rule publication must pass schema/AST/static validation, persisted rule tests, conflict/priority checks and independent durable review inside the existing Admin Publish/outbox transaction. Approved rule/scheme content and formal results are immutable; retries cannot create competing formal results for one snapshot/subject/scheme version.
139. Classification consumes formal Phase 1E context and existing Phase 1F/1G evidence through authorized, scope-revalidating interfaces. Configuration pins are explicit and immutable; execution cannot silently select new rules or broaden knowledge scope.

## Phase 1I Applicability / Country / Scenario Addendum

140. Regulation applicability must reference canonical KnowledgeDocumentVersion, RegulatoryStructureNode and LegalBasis identities; no duplicate regulation, article or legal-basis source of truth.
141. CountryComplianceProfile, ScenarioAdjustmentProfile, CountryCapability and applicability/rule-pack configuration use existing versioned metadata, independent review, publish outbox and registry projections.
142. Scenario adjustment deterministically merges configuration within the fixed standard pipeline. Required/disabled skills, evidence profiles and contradictory checks/priorities cannot be silently resolved.
143. Generic country capabilities are configuration/discovery boundaries; classification consumes Phase1H. No country-specific root graph, classifier, Python legal mechanism or core country branch.
144. Applicability consumes validated Phase1E context, Phase1F pinned scope, Phase1G revalidated evidence/sufficiency/fallback and Phase1H formal classification/RuleHits. Reference-only clients cannot supply facts, identity, scope or decisions.
145. New configuration pins require approved ACTIVE effective versions; legal sources also require READY and an existing authorized snapshot scope. Historical replay retains exact profile/rule/knowledge/binding pins and revalidates current access.
146. Missing, partial, insufficient or conflicted evidence must conservatively preserve review/conflict and fallback. Contradictory RuleHits cannot produce a last-writer-wins applicability result.
147. Scenario-only applicability requires independent validated facts, scenario/jurisdiction and sufficient project evidence. Explicit scenario RuleHits delegate to the existing Phase1H engine; no data item means no fabricated ClassificationResult.
148. Applicability results retain full canonical provenance, immutable snapshot identity and idempotent persistence. Existing LegalBasis M:N links associate only matching canonical RuleHits and article evidence.
149. Phase1I ends at applicability and capability availability: no Phase1J obligation/path/risk/recommendation/final decision, full workflow, frontend, LLM gateway or document generation.
150. Only Phase1I owns0009; migrations0001–0008 remain frozen. Empty PostgreSQL and exact verified0008 upgrades must be equivalent; downgrade must refuse retained authoritative I data.
151. Presentation locale (zh-CN/zh-HK/en-US) is distinct from machine status/reason codes and official source/evidence/citation language. Governed generic localized display payloads reuse existing MetadataVersion/JurisdictionConfig; API fallback is deterministic and cannot invoke runtime machine translation or alter formal applicability semantics.

## Phase1J Formal Decision Addendum

152. Formal decision dependency order is applicability→obligation→candidate→risk→recommendation→final; risk and capability availability cannot create legal obligations/prohibitions or change applicability/viability.
153. Authoritative J evaluation/ranking is deterministic, governed and pinned; LLM may explain formal results only and cannot decide obligations, viability, scores, recommendations or paths.
154. Final/recommendation results cannot conceal conflict, insufficiency, review or unmet legal conditions; unresolved selection remains absent and formal legal prohibition requires traceable legal authority.
155. J results retain canonical upstream/legal/evidence identities, immutable snapshot/config/policy provenance and idempotent authorization-revalidated persistence; workflow checkpoint/locale is not decision authority.
