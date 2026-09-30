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
