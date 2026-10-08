# 跨境數據合規智能體
## Codex Master Specification — Consolidated Implementation / Integration Baseline V3.7

> 用途：作為 Codex 後續進行架構設計、數據模型、API、LangGraph、Agent/Skill、前後端及運維開發的唯一 Master Specification，目標是讓 Codex 最終開發出可實際部署、運行、運維及對外提供服務的產品級智能體。  
> 本文件整合：既有分層工作流架構圖、界面示意、研究內容、合規路徑輸出要求、H5 前端、多渠道使用方式、產品知識隔離、Document-first 分析、知識運維、可視化、合同/文檔能力、模組解耦及資料與邏輯分離要求。  
> **V3.7 Consolidation（2026-10-08）**：在不改變 V3.6 主架構的前提下，吸收 M2-A～M2-D 已驗證實作契約，並正式凍結 LLM 調用邊界、多 Provider / 多 Model 控制平面、Northbound Third-party API 與 Stage 1 Full E2E 驗收標準。

---

# 0. 開發前總則

本系統為企業級「跨境數據合規智能體」，面向境外實際項目，不是普通法律問答 Chatbot，也不是單純 PDF + RAG 工具。

後續所有 Codex 開發必須遵循：

- `DATA ≠ LOGIC`
- `CONFIG ≠ CODE`
- `RULE ≠ CODE`
- `PROMPT ≠ CODE`
- `KNOWLEDGE ≠ CODE`
- `TEMPLATE ≠ CODE`
- `RESULT ≠ PRESENTATION`
- `CHANNEL ≠ BUSINESS LOGIC`

最重要原則：

> **新增資料，不應等於修改程式。**

新增以下內容原則上不得修改核心 Python / React / LangGraph Root Graph：

- 國家 / 法域
- 業務場景
- 產品 / 產品域 / 產品標籤
- Data Type / Classification
- Data Flow Type
- 法規 / 法規版本 / 法條
- 案例
- Rule / Risk Rule
- Prompt
- Model
- Regulatory Template
- Enterprise Contract Template
- Clause
- UI Metadata Option

只有新增真正的新算法、通用能力、核心 Service 或新處理機制時，才允許修改核心 Code。

## 0.1 規格表達與示例通用化原則

本 Master Specification 中如出現任何國家、地區、產品、產品域、行業、場景、平台或文件名稱，均只能視為說明概念或測試方法的非規範性示例，不得被 Codex 解讀為固定枚舉、默認映射、特殊分支或硬編碼邏輯。

正式實現必須使用抽象、可配置及可擴展語義，例如：

- `selected_product_scope`
- `unrelated_product_scope`
- `source_jurisdiction`
- `destination_jurisdiction`
- `selected_scenario`
- `detected_product_context`
- `allowed_knowledge_scope`
- `excluded_knowledge_scope`

規範性要求必須描述「適用於任意產品 / 任意法域 / 任意場景」的通用規則，而不是只對某一個產品、某一個國家或某一份示例文檔成立。

示例可以存在於：

- Test Fixture
- Demo Data
- Seed Data
- Documentation Example

但不得存在於：

- Core Domain Logic
- LangGraph Branch Condition
- Agent Routing Hard Code
- RAG Scope Hard Code
- Frontend Option Hard Code
- Rule Engine Core Code


---

## 0.2 Production-ready 目標

本項目最終不是 Demo / Prototype，而是需要形成可實際使用的企業級智能體。

Codex 後續實現必須同時滿足：

1. **Local Deployable**
   - 可在單台本地 / 私有服務器上部署；
   - 具備完整 Web H5、API、Worker、Database、Vector Retrieval、Object Storage、Knowledge Operations；
   - 不要求依賴開發者電腦上的臨時服務；
   - 可通過標準配置切換外部模型或本地 / 私有模型服務。

2. **Cloud Deployable**
   - 可部署至公有雲 / 私有雲 / 企業容器平台；
   - API 與 Worker 可水平擴展；
   - Database、Redis、Object Storage、Search 等可切換為 Managed Service；
   - 支持 Ingress / API Gateway / TLS / Secret Manager / Observability。

3. **Third-party Callable**
   - 提供穩定、版本化、文檔完整的對外 API；
   - 支持 OAuth2 / Service Account；
   - 支持同步、異步、Webhook、Streaming；
   - 支持 OpenAPI 及 SDK；
   - 支持 Rate Limit、Quota、Idempotency、Audit。

4. **Operationally Maintainable**
   - 可啟動、停止、升級、回滾；
   - 有 Health Check、Metrics、Log、Trace；
   - 有 Database Migration；
   - 有 Backup / Restore；
   - 有知識庫重建 / Reindex；
   - 有任務失敗重試與恢復；
   - 有管理員 Bootstrap 流程。

5. **Reproducible**
   - 本地與雲環境使用相同核心 Codebase；
   - 差異只存在於 Deployment Profile、Config、Secret、Adapter；
   - 不得維護 Local / Cloud 兩套業務邏輯。

## 0.3 V3.6 LangGraph 技術決策基線

V3.6 正式凍結以下技術決策：

> **LangGraph 是本系統唯一默認的 Agent / Workflow Orchestration Runtime。**

不再保留「LangGraph 或內部自研 Workflow Runtime 二選一」的未決狀態。

同時保留框架隔離邊界：

```text
Application Use Case
↓
WorkflowRuntimePort
↓
LangGraphWorkflowRuntimeAdapter
↓
Compiled LangGraph StateGraph
↓
Node / Router / Subgraph
↓
Agent / Skill / Domain Service
```

因此：

- Domain 不得直接依賴 LangGraph API；
- Agent / Skill 不得直接持有 Compiled Graph；
- Application 通過 `WorkflowRuntimePort` 調度 Workflow；
- LangGraph-specific API 僅允許存在於 `workflows/langgraph/`、Adapter、Graph Definition、Node/Router/Subgraph Runtime 邊界；
- 未來如需升級或替換 Workflow Framework，只允許在 `WorkflowRuntimePort` 後完成，不得滲入 Compliance Domain。

### 0.3.1 LangGraph 職責

LangGraph 負責：

- `StateGraph` Workflow Orchestration
- Conditional Routing
- Subgraph Composition
- Human-in-the-loop Interrupt / Resume
- Durable Checkpoint
- Streaming / Runtime Events
- Node Retry / Timeout Policy
- Long-running Workflow State Recovery

LangGraph 不負責：

- Regulation Knowledge Base
- RAG Knowledge Storage
- Rule Engine
- Risk Engine
- Domain Database
- Product Scope Policy
- Legal / Compliance Business Logic
- Enterprise Audit Source of Truth

### 0.3.2 Source of Truth 邊界

必須區分：

```text
AnalysisSnapshot
= 一次正式合規分析所使用的 Knowledge / Rule / Prompt / Model / Template / Workflow Version 快照
```

與：

```text
LangGraph Checkpoint
= LangGraph 運行時的 State / Pending Write / Interrupt / Execution Position 持久化
```

兩者不得合併，也不得互相替代。

正式關係：

```text
AnalysisSnapshot
↓
WorkflowRun
↓
LangGraph thread_id
↓
LangGraph Checkpoints
```

---


# 0.4 V3.6 Final Architecture 收口要求

V3.6 在既有 LangGraph Baseline 基礎上完成最後一輪架構補強。

本版本不再變更主架構，重點補足以下 Production / Domain 收口能力：

1. `ProjectParty / LegalEntity / PartyRoleAssignment`
   - 正式描述 Controller、Processor、Exporter、Importer、Recipient、Subprocessor 等法律責任主體；
   - Data Flow、Contract、Compliance Path Step 必須可以關聯責任主體。

2. `ClassificationScheme / ClassificationLevel / ClassificationResult`
   - 分類分級必須版本化、法域化、規則化；
   - 不得只保存自由文本分類結果。

3. 通用 Regulatory Requirement
   - 具體標準合同、評估文件、備案/申報文件類型由 Metadata / Rule / Country Skill / Template 驅動；
   - 不因新增某一法域文件類型而新增 Python Skill。

4. Safe Rule DSL
   - Rule Condition / Action 使用受控 Declarative Expression；
   - 禁止 `eval()` / 任意 Python Code；
   - Rule Publish 前必須執行 Rule Test Case。

5. Agent / Skill API Security Boundary
   - Agent API / Skill API 默認屬 Internal / Trusted Integration Capability；
   - 對外不得繞過 Auth、Scope、AnalysisSnapshot、Audit、Review。

6. Model Data Protection Pipeline
   - `REDACTION_REQUIRED` 必須落實為真正的 DataRedactionService；
   - External Model Call 前完成 Policy、Redaction、Audit。

7. Country Skill Facade
   - 保留研究內容中的 Country Skill 概念；
   - 內部由多個 Country Capability 組合，避免一國一套巨大 Skill。

8. LLM Wiki Governance
   - Wiki 必須版本化、可審核、可發布、可追溯 Evidence；
   - 不得由 LLM 自動生成後直接 ACTIVE。

9. Regulatory Monitoring
   - 預留官方來源監測、Version Diff、Affected Project Impact；
   - 首期可不自動抓取，但 Domain / Workflow Contract 必須預留。

10. Multimodal Document Understanding
    - 支持架構圖、Data Flow Diagram、網絡拓撲等圖形內容；
    - OCR 僅負責文字，不可替代圖形關係理解。

11. LangGraph Production Hardening
    - `context_schema / Runtime`
    - Retry / Timeout Policy
    - recursion / max-step guard
    - Checkpointer setup / retention / deletion
    - interrupt side-effect idempotency
    - graph version provenance

12. Master / Prompt / Coding Gate 完全一致
    - Architecture / Knowledge / Production / LangGraph 四個 Gate 全部 PASS 才可開始 Phase 1。

本版本完成後，除非出現新的研究需求或核心算法能力，不再新增平行架構框架。

---


# 0.5 V3.6 Visualization / Result Contract 收口要求

V3.6 不改變既有已凍結主架構，重點將「分析結果輸出與可視化」由設計建議提升為強制 Product / API / Frontend Contract。

本版本強制要求：

1. Stage 1 合規分析結果不得只輸出自然語言報告或 Data Table。
2. H5 Result Page 必須同時提供：
   - Workflow Stepper
   - Analysis KPI / Summary
   - Data Transfer Map / Route / Topology
   - Risk Visualization
   - Compliance Path Visualization
   - Data Item Compliance Table
   - Evidence / Legal Basis Drawer
3. Workflow 五階段必須映射真實 LangGraph 執行狀態及結構化 `AnalysisStageResult`，不得只顯示假進度動畫。
4. Data Transfer 與 Compliance Path 至少必須提供可交互式結構化可視化。
5. Cross-border Status 與 Risk Level 必須使用兩套獨立視覺語義。
6. 每個 Data Item 結果必須可追溯至：
   - 原始需求文檔位置
   - Classification Result
   - Data Flow
   - Applicable Regulation / Legal Basis
   - Rule Hit
   - Risk
   - Recommendation
   - Compliance Path
   - Required Document
   - Evidence
7. 法規依據不得只返回法規名稱列表，需提供結構化 `LegalBasisItem`。
8. Visualization 只能消費 Backend Structured Result / DTO，不得從 LLM 自然語言重新解析形成正式圖形。
9. Frontend / Embed 不得重新推理、重新分類、重新判斷跨境結論。
10. Web / VS Code / Third-party API 必須共享同一 Domain Result；只有 Presentation 不同。
11. Export 必須可保留核心可視化內容，而不是只導出文字摘要。
12. Visualization Acceptance 必須進入 Phase 0 Gate、MVP Gate、Production E2E Gate。


---


# 0.3 V3.7 Consolidated Baseline / 已驗證實作基線

V3.7 是 **V3.6 的增量收口版本，不是架構重設計**。除非本文件明確標記為新增或修訂，V3.6 已凍結要求全部保留。

截至 2026-10-08，已驗證 implementation baseline：

- `main = efda0955342de8d1ea36aa0f754d63c9b421fec8`
- annotated tag：`v3.6-m2d-pass`
- Alembic：`0015_m2d_review_governance`
- M2-A Structured Intake：PASS + MAIN
- M2-B Production Document / Temporal Snapshot：PASS + MAIN
- M2-C Formal Result Authority / Result Workspace：PASS + MAIN
- M2-D Governed Human Review / Resume / Successor Snapshot：PASS + MAIN

V3.7 將以下已驗證契約提升為正式 Master Baseline：

1. **Structured Intake + Document Input 共存**：Structured Input 與 Document Provenance 是兩種正式來源，不得互相偽裝。
2. **Immutable Snapshot / Temporal Read**：Canonical identity 可穩定；正式狀態、provenance、policy/template/model pins 必須版本化並由 Snapshot 精確引用；future input 不得改變歷史分析語義。
3. **Cross-border Assessment Authority ≠ Final Path Status**：跨境法律狀態由獨立 Formal Owner 產生，禁止由 `FinalPath.status` 推導。
4. **RequiredDocument 是 Stage 1 Formal Result**：`REQUIRED / CONDITIONAL / RECOMMENDED / NOT_APPLICABLE` 與是否使用平台生成文件分離；Stage 2 必須 user opt-in。
5. **Governed Human Review**：ReviewDecision 可治理 review，但不得直接 patch Classification / CrossBorder / Risk / FinalPath / RequiredDocument；正式輸入改動必須形成 successor version/snapshot/run。
6. **RAG-FIRST / RULE-FIRST / EVIDENCE-FIRST / LLM-WHEN-NEEDED**：生成式 LLM 是受控增強能力，不是 Stage 1 法律結論來源。
7. **Multi-provider / Multi-model**：後台可管理多個 Provider instance 與多個 Model；普通用戶只能在 policy-eligible model 中選擇 AUTO / SINGLE / MULTI_MODEL；最終仍由 `ModelUsagePolicy + ModelRouter` 授權。
8. **Northbound / Southbound API 分離**：本系統調模型的 Provider API 與第三方系統調用本智能體的 Public Agent API 是兩個不同 trust boundary、credential domain 與 audit domain。
9. **Channel Parity**：Web / VS Code / Third-party API 只可有 Channel / Presentation 差異；必須共用 Application Use Case、Snapshot、Workflow Runtime、Formal Result Authority。
10. **Stage 1 Full E2E**：正式驗收必須從真實前端或 Public API 輸入場景/法域/數據流/文件開始，經 Knowledge/RAG/Evidence、Classification、Applicability、Cross-border、Risk、Recommendation、Final Path 到 Result Workspace；不得以分散 milestone 測試相加代替單一路徑 E2E。

## 0.4 LLM 使用總原則（V3.7 新增）

正式原則：

> **RAG-FIRST → RULE-FIRST → EVIDENCE-FIRST → LLM-WHEN-NEEDED**

具體約束：

- 有完整 Structured Input 時，不得為了「使用 AI」而再次讓 LLM 重做相同事實判斷。
- Knowledge/RAG 已有充分、版本化、可引用 Evidence 時，正式法律判斷由 Rule/Policy/Formal Owner 執行；LLM 只可做 derived explanation。
- `LLM parametric knowledge ≠ Legal Evidence`。模型記憶、常識或自由生成內容不得直接成為 LegalBasis / Evidence。
- Knowledge insufficiency 時，LLM 可協助 query expansion、法規名稱候選、missing-evidence analysis；重新檢索後仍不足時，正式狀態必須是 `INSUFFICIENT_EVIDENCE / REVIEW_REQUIRED` 或其他受治理狀態，禁止用模型記憶補成確定法律結論。
- LLM 可形成 Candidate / Derived Explanation / Generated Artifact；不得成為 Classification、Applicability、Cross-border Assessment、Risk、Final Path、RequiredDocument 的 authoritative owner。

# 1. 系統定位

系統定位：

> **面向境外實際項目的企業級跨境數據合規分析、合規路徑推薦及實施支撐平台。**

主要服務角色：

- 國際公司及境外機構
- DICT 團隊
- 產品團隊
- 技術 / 網絡 / 雲 / AI 團隊
- 項目交付團隊
- 法務 / 合規 / 信息安全
- 知識運營及系統管理員

核心分析對象：

- Project
- Business Scenario
- Product / Product Domain
- Document
- Data Item
- Data Flow
- Jurisdiction
- Regulation / Rule
- Risk
- Compliance Path
- Required Document
- Evidence

---

# 2. 研究內容映射

系統必須支撐以下研究能力：

1. 跨境數據合規知識庫  
   - 原始法規
   - 國別合規方案
   - 典型案例
   - 治理框架
   - 成本模型
   - AI 監管要求
   - 標準化合規文檔模板
   - 研究報告 / 學術論文

2. RAG
   - Metadata Filter
   - Keyword Search
   - Vector Search
   - Hybrid Retrieval
   - Rerank
   - Evidence Retrieval

3. LLM Wiki
   - Country Wiki
   - Regulation Wiki
   - Scenario Wiki
   - Product Wiki
   - Data Category Wiki
   - Compliance Mechanism Wiki
   - Template Wiki

4. Knowledge Graph
   - Regulation → Article → Requirement → Measure / Mechanism → Document → Template
   - Scenario → Requirement
   - Product → Data Category
   - Enterprise Template → Clause → Requirement

5. Vertical Agent + Country Skill + Generic Skill

6. 合規工作流
   - 需求/場景識別
   - 數據分類分級
   - 風險分析
   - 合規建議
   - 合規路徑推薦
   - 文檔生成 / 合同審核

7. 標準化集成
   - Business API
   - Agent API
   - Skill API
   - H5 Embed
   - VS Code Client
   - Third-party API

---

# 3. 三種智能體使用方式

系統必須採用：

> **ONE INTELLIGENCE CORE + MULTIPLE ACCESS CHANNELS**

三種主要使用方式：

## 3.1 HTML5 Web Frontend

主要使用界面：

- 企業級 Midnight 深夜模式
- H5 / React + TypeScript
- 可獨立運行
- 可 iframe 嵌入
- 可 Deep Link
- 可 JS SDK 調起
- 可預留 Micro Frontend / Web Component

## 3.2 VS Code Conversational Client

以對話方式使用智能體：

- 分析 Current File
- 分析 Selection
- 分析 Workspace File
- Review Contract
- Explain Compliance Result
- Show Evidence
- Generate Compliance Path
- Generate Document
- Open Visualization

VS Code 不得實現自己的合規邏輯，只作 Client / Channel Adapter。

## 3.3 Third-party API

供其他企業系統直接調用：

- REST API
- Async Task
- SSE / WebSocket
- Webhook
- SDK
- OpenAPI

適用於各類企業內部或外部業務平台，例如：

- 項目 / DICT 管理平台
- 能力協同 / 研發管理平台
- 合規管理平台
- AI / 模型服務平台
- 項目管理系統
- 其他經授權企業平台

以上僅為平台類型示意，不構成固定集成清單。

三種渠道必須共用：

- Domain Model
- Application Use Case
- LangGraph
- Agent / Skill
- Rule / Risk
- Knowledge / Evidence
- Review
- Audit

渠道差異只允許存在於：

- Authentication
- Input Adapter
- Streaming
- Presentation
- Client Interaction

---

# 4. HTML5 Frontend 要求

## 4.1 技術形態

推薦：

- React
- TypeScript
- HTML5
- CSS / Design Token
- REST
- SSE / WebSocket

不得依賴：

- Windows 專有 UI
- Electron 專有能力
- 單一內部平台 UI Framework

## 4.2 前端交付模式

至少支持：

### Standalone
完整工作台。

### iframe Embed
示例：

- `/embed/project/{project_id}`
- `/embed/result/{analysis_id}`
- `/embed/visualization/{project_id}`
- `/embed/path/{project_id}`
- `/embed/contract-review/{review_id}`

### Deep Link
示例：

- `/projects/{project_id}`
- `/projects/{project_id}/analysis`
- `/projects/{project_id}/data-flow`
- `/projects/{project_id}/compliance-path`
- `/projects/{project_id}/visualization`

### JavaScript SDK
概念 API：

- `openProject()`
- `openAnalysis()`
- `openCompliancePath()`
- `openVisualization()`
- `openContractReview()`
- `openDocumentGenerator()`

## 4.3 Embed UI Mode

支持：

- FULL
- EMBED
- READONLY
- REVIEW
- VISUALIZATION_ONLY

不同模式重用同一 Feature Component，不複製業務邏輯。

## 4.4 Host Integration

iframe 使用：

- `window.postMessage`
- Origin 驗證
- Configurable Allowed Origins

事件：

- COMPLIANCE_READY
- PROJECT_LOADED
- ANALYSIS_STARTED
- ANALYSIS_COMPLETED
- REVIEW_REQUIRED
- DOCUMENT_GENERATED
- NAVIGATION_CHANGED
- CLOSE_REQUESTED

---

# 5. Frontend Design System

整體風格：

> **Midnight Enterprise / 深夜企業級模式**

要求：

- 深海軍藍 / Charcoal 背景
- Dark Elevated Cards
- Blue / Cyan 主色
- Semantic Risk Color
- 高可讀性法規 / 表格 / 合同長文本
- 不採用過度 Cyberpunk / Neon
- 高信息密度、專業、穩定

## 5.1 Design Token

禁止業務 Component 硬寫顏色。

至少建立：

- `color.background.canvas`
- `color.background.surface`
- `color.background.elevated`
- `color.text.primary`
- `color.text.secondary`
- `color.border.default`
- `color.primary`
- `color.success`
- `color.warning`
- `color.danger`
- `color.info`
- `color.risk.low`
- `color.risk.medium`
- `color.risk.high`
- `color.risk.critical`
- `color.compliance.direct`
- `color.compliance.conditional`
- `color.compliance.blocked`
- `color.compliance.review`

## 5.2 Layout

- Left Sidebar
- Top Header
- Main Workspace
- Right Insight Drawer
- Optional Bottom Contextual Chat

## 5.3 主導航

- 工作台
- 新建分析
- 我的項目 / 任務
- 法規知識庫
- 國別知識
- 合同與模板中心
- 合同智能審核
- 人工覆核
- 知識運營
- 運維管理
- 系統設置


## 5.4 Analysis Result Page Components

至少建立：

- ComplianceWorkflowStepper
- AnalysisSummaryCards
- CrossBorderStatusDistribution
- RiskDistributionView
- JurisdictionDistributionView
- ComplianceMapView
- DataTransferRouteView
- ComplianceTopologyView
- RiskVisualizationPanel
- CompliancePathTimeline
- CompliancePathFlowView
- DataItemComplianceTable
- DataItemDetailDrawer
- EvidenceDrawer
- LegalBasisDrawer
- SourceDocumentTracePanel
- VisualizationLegend
- VisualizationFilterBar
- ComplianceResultExportView

組件不得直接包含：

- Regulation Decision Logic
- Risk Calculation
- Cross-border Decision Logic
- Compliance Path Generation

---

# 6. 業務總體閉環

```text
境外項目
↓
項目輸入 / 文檔上傳
↓
需求 / 業務場景識別
↓
業務事實提取
↓
產品 / 系統 / 設備識別
↓
Data Item 提取
↓
Data Flow 識別
↓
Jurisdiction 識別
↓
Analysis Context
↓
Knowledge Scope
↓
Vertical Agent / Country Skill
↓
Data Classification
↓
Applicable Regulation / Rule
↓
Compliance Obligation
↓
Candidate Compliance Path
↓
Risk Analysis
↓
Compliance Recommendation
↓
Final Compliance Path
↓
Required Document
↓
Regulatory Template
↓
Enterprise Template Suggestion
↓
Visualization
↓
Stage 1 Output
↓
User Confirmation
↓
Stage 2 Document / Contract
↓
Human Review
↓
Audit / Feedback
```

---

# 7. 對外五階段工作流

前端統一顯示：

1. 需求 / 場景識別
2. 數據分類分級
3. 風險分析
4. 合規建議
5. 合規路徑推薦

工作流狀態：

- WAITING
- RUNNING
- COMPLETED
- WARNING
- REVIEW_REQUIRED
- FAILED

前端五階段必須映射實際 LangGraph Node / Subgraph 執行狀態，不得只是動畫。

## 7.1 AnalysisStageResult

每一個對外階段必須形成正式結構化結果：

`AnalysisStageResult`

至少：

- stage_result_id
- project_id
- analysis_run_id
- stage_code
- stage_name
- stage_sequence
- status
- started_at
- completed_at
- duration_ms
- summary
- key_findings
- statistics
- related_document_ids
- related_data_item_ids
- related_data_flow_ids
- related_classification_result_ids
- related_risk_item_ids
- related_recommendation_ids
- related_path_ids
- related_evidence_ids
- confidence
- review_required
- warning_codes
- error_code

`stage_code` 使用穩定技術代碼，例如：

- REQUIREMENT_SCENARIO_IDENTIFICATION
- DATA_CLASSIFICATION
- RISK_ANALYSIS
- COMPLIANCE_RECOMMENDATION
- COMPLIANCE_PATH

Display Label 由 i18n / Metadata Presentation Layer 決定。

## 7.2 Workflow Stepper

H5 必須提供：

`ComplianceWorkflowStepper`

每個 Stage 至少顯示：

- Stage Name
- Status
- Duration
- Summary
- Key Findings Count
- Warning / Review Badge
- Expand / Collapse
- Evidence / Result Link

Stage 完成後，用戶可以展開查看該階段的結構化業務結果。

禁止展示：

- Chain-of-thought
- 隱藏 Prompt
- 模型內部推理 token

只展示：

- Structured Result
- Evidence
- Rule / Regulation Basis
- Workflow Status
- User-reviewable Business Finding

## 7.3 Stage-to-LangGraph Mapping

對外五階段與內部 LangGraph 可一對多映射：

```text
Requirement / Scenario Identification
→ IntakeDocumentSubgraph
→ Business Fact
→ Product Context
→ Scenario
→ Data Flow / Jurisdiction Context

Data Classification
→ Classification Nodes
→ ClassificationScheme / Level / Result

Risk Analysis
→ Regulation Applicability
→ Obligation
→ Candidate Path
→ Risk Engine

Compliance Recommendation
→ Recommendation
→ Required Measures
→ Remediation / Filing / Contract Recommendation

Compliance Path
→ Final Path
→ Required Document
→ Evidence Validation
→ Result Aggregation
```

Frontend 不需要暴露所有內部 Node，但 Stage Status 必須由真實 Node 狀態聚合得到。

---

# 8. 路徑與風險順序統一

為避免研究描述與界面邏輯衝突，正式採用：

```text
Compliance Obligation
↓
Candidate Compliance Path
↓
Risk Analysis
↓
Compliance Recommendation
↓
Final Compliance Path
```

Candidate Path：

- 基於法規義務推導

Final Path：

- 結合實際 Risk / Gap / Recommendation 後形成

禁止形成 Risk ↔ Path 無限循環。

---

# 9. Project Intake

`ProjectIntakeContext` 至少包括：

- project_id
- project_name
- industry
- business_scenario
- scenario_description
- selected_product_domains
- selected_products
- source_locations
- destination_locations
- processing_locations
- storage_locations
- data_flow_description
- data_categories
- data_volume
- business_purpose
- organizations
- third_parties
- uploaded_documents
- requested_outputs
- analysis_as_of_date

`analysis_as_of_date` 必須控制使用哪個法規有效版本。

---


# 9A. Project Party / Legal Responsibility Domain

跨境合規不能只保存 organization / third_party 字符串。

必須建立正式責任主體 Domain。

## 9A.1 LegalEntity

至少：

- legal_entity_id
- tenant_id
- organization_id
- legal_name
- registration_country_or_region
- jurisdiction_id
- entity_type
- registration_identifier
- address
- status

## 9A.2 ProjectParty

表示某個 Project 中實際參與數據處理或合同關係的主體。

至少：

- project_party_id
- project_id
- legal_entity_id
- display_name
- party_category
- internal_or_external
- source_document_ids
- confidence
- confirmed_by_user
- status