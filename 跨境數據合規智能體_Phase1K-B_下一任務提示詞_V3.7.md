# Phase 1K-B 下一任務提示詞 V3.7
# LLM Invocation Governance + Multi-provider / Multi-model Control Plane

你是一名企業級 AI 系統架構師、合規平台架構師、LLM 平台架構師、後台管理平台架構師及全棧工程師。

本輪使用：

**GPT-6.1 Sol / High Reasoning**

本任務是 Stage 1 Full E2E 前第一個剩餘主要前置工作包。

請完整閱讀並遵守同目錄最新正式基線：

- `跨境數據合規智能體_Codex_Master_Specification_V3.7.md`
- `跨境數據合規智能體_Phase0_架構與開發前設計_V3.7.md`
- `ARCHITECTURE_RULES.md`

V3.7 是 V3.6 的增量收口，不是重設計；既有 verified implementation contract 優先保留。

---

# 0. VERIFIED BASELINE / START GATE

Repository：

`bensuen0831/crossborder-compliance-agent`

唯一正式開發 baseline：

`efda0955342de8d1ea36aa0f754d63c9b421fec8`

Annotated tag：

`v3.6-m2d-pass`

Alembic：

`0015_m2d_review_governance`

Coding 前重新驗證：

```text
main == efda0955342de8d1ea36aa0f754d63c9b421fec8
v3.6-m2d-pass -> same exact commit
Alembic head == 0015_m2d_review_governance
```

任何不一致：STOP，輸出：

`PHASE1K-B START GATE = BLOCKED — BASELINE_CHANGED`

V3.7 規格文檔已先行提交至 GitHub branch：

`phase1kb-multi-provider-llm-governance`

該 branch 以 implementation baseline `efda0955342de8d1ea36aa0f754d63c9b421fec8` 為祖先。Pre-coding documentation lineage 已包含：

- `95f2e5d132b2d1b69e8cdaff371607c385de5340` — read-only D0 inventory；
- `52a09676729c9821a8190623ede49c2bb5951278` — Master Specification V3.7；
- `a44bcc606741a51d2610e366fb143baabcf79ab8` — Phase0 Architecture V3.7；
- `15c8cd69dba384050849b34ec015e1ea7afa9969` — V3.7 design consistency / delta summary；
- `3e8f2855de35c4e235c74cf2432a4a09102299ef` — executable Phase1K-B V3.7 task prompt。

在開始產品 Coding 前，必須驗證從 `efda095...` 到當前 pre-development head 的差異只包含上述規格 / 設計 / D0 inventory / task-prompt 文檔；不得包含產品源碼、Migration、Workflow、Frontend product source 或測試邏輯變更。若已有後續 Codex commit，則先將「第一個產品實作 commit」之前的 lineage 與上述 pre-development documentation lineage 分界並記錄，不得把 pre-development 文檔 commit 誤當 product implementation baseline。

**本任務不要重新建立 branch。** 直接 checkout / continue：

`phase1kb-multi-provider-llm-governance`

並在該 branch 上繼續 Phase1K-B 開發。

Draft PR target：`main`。

不得從舊 Phase1K-A branch、M2 branch 或 evidence branch 開發。

---

# 1. CORE POSITIONING — MUST FREEZE BEFORE CODING

本系統不是 LLM-first 法律 Chatbot。

正式 Stage 1 原則：

```text
RAG-FIRST
RULE-FIRST
EVIDENCE-FIRST
LLM-WHEN-NEEDED
```

主工作流：

```text
User / Document Inputs
→ Formal Context
→ Knowledge Scope
→ RAG / Hybrid Retrieval / Rerank
→ Evidence Sufficiency
→ Governed Rule / Formal Decision Owners
→ Stage1 Formal Result
```

LLM 是受控增強能力，主要用於：

1. 非結構化需求文檔語義理解；
2. deterministic extraction 置信不足時的 Candidate extraction；
3. Knowledge/RAG 不足時的 Query Expansion / Missing Evidence Analysis；
4. Formal Result 的自然語言 explanation；
5. 未來 Stage 2 文檔/合同生成與審核。

LLM 不得成為正式法律判定 owner。

---

# 2. FORMAL OWNER BOUNDARY

以下不得由 LLM 直接決定：

```text
Classification / Grading
Regulation Applicability
Cross-border Assessment
Compliance Obligation
Risk Result
Candidate/Final Compliance Path
RequiredDocument RequirementLevel
```

禁止：

```text
GPT / DeepSeek / Qwen / GLM output
→ direct Formal Result write
```

禁止：

```text
multi-model majority vote
→ legal conclusion
```

Formal Result 必須繼續來自既有 Formal Input + pinned Knowledge/Evidence + Rule/Policy/Formal Owner。

---

# 3. LLM PARAMETRIC KNOWLEDGE IS NOT EVIDENCE

正式鎖定：

```text
LLM Parametric Knowledge != Legal Evidence
```

如果 Knowledge/RAG insufficient：

```text
Evidence Sufficiency = INSUFFICIENT
↓
optional LLM query expansion / regulation-name candidate / missing-evidence analysis
↓
re-retrieval
```

如果仍不足：

```text
INSUFFICIENT_EVIDENCE / REVIEW_REQUIRED
```

不得：

```text
knowledge base 沒有證據
→ 模型憑記憶回答
→ 寫成 LegalBasis / Evidence
```

---

# 4. D0 — EXISTING CONTRACT INVENTORY FIRST

Coding 前完整盤點 current main：

- `LLMServicePort`
- `LLMRequest / LLMResult`
- `ModelRegistry`
- Provider / Model / Deployment persistence
- `ModelUsagePolicy`
- `ModelRouter`
- `DataRedactionService`
- `HTTPProviderAdapter`
- `OpenAICompatibleProviderAdapter`
- Prompt registry/version/pins
- Snapshot LLM pins
- admin metadata/review/publish APIs
- current canonical frontend Admin shell
- current provider secret / configuration ports
- current health metadata
- current LLM audit port

回答：

1. 現有 schema 是否已可容納多 Provider instance？
2. 一個 Provider 是否已可配置多 Model / Deployment？
3. ProviderConnection 是否已存在 `secret_ref`？
4. Provider / Model / Deployment 哪一層是 SoT？
5. Admin API 哪些可直接 reuse？
6. 現有 Admin frontend 是否已有 Model metadata entry point？
7. Snapshot pin 已支持哪些 LLM pin types？
8. 現有 OpenAICompatibleProviderAdapter 的 wire contract 能直接支持哪些 endpoint？
9. DeepSeek / Qwen / GLM 哪些可走 OpenAI-compatible，哪些需 thin adapter？必須用真實協議測試證明，不得憑名稱猜測。
10. Phase1K-A 中哪些 production wiring 仍是明確 exclusion？
11. 是否真的需要 `0016` migration？

輸出：

`PHASE1K-B D0 INVENTORY = PASS`

才能 coding。

---

# 5. LLMInvocationPolicy

新增或在 repo existing policy framework 中正式實現 equivalent typed contract：

`LLMInvocationPolicy`

它負責：

> 決定某個 task/purpose 是否應調用生成式 LLM，以及所需 capability；不負責選最終 provider，也不負責法律判斷。

Stable Trigger Codes 至少支持：

```text
DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED
DOCUMENT_EXTRACTION_LOW_CONFIDENCE
DOCUMENT_FIELD_CONFLICT
RETRIEVAL_QUERY_EXPANSION_REQUIRED
KNOWLEDGE_EVIDENCE_INSUFFICIENT
RESULT_EXPLANATION_REQUESTED
DOCUMENT_GENERATION_REQUESTED
CONTRACT_GENERATION_REQUESTED
CONTRACT_REVIEW_REQUESTED
```

Stage 2 triggers 本輪只凍結 contract，不實作 Stage 2。

---

# 6. LLM USAGE MODE

提供 typed/configurable：

```text
MINIMAL
STANDARD
ENHANCED
```

`STANDARD` 為建議預設：

- Document semantic extraction when needed；
- retrieval insufficiency-triggered query expansion；
- result explanation。

`ENHANCED` 可允許 multi-model candidate extraction / query expansion。

模式不得改變 Formal Owner。

---

# 7. MULTI-PROVIDER / MULTI-API REQUIREMENT

同一 Tenant 必須支持：

- 多個 Provider instances；
- 同一 Vendor 的多個 Endpoint / API account；
- 一個 Provider 下多個 Models / Deployments；
- External / Private Cloud / On-premise deployment classes。

例如產品層可呈現：

```text
OpenAI / GPT
DeepSeek
Qwen
GLM
Internal / Private Models
Other OpenAI-compatible
```

但正式 Domain/Router 不得 hardcode vendor-specific business logic。

---

# 8. VENDOR / PROTOCOL SUPPORT

至少完成可實際配置及測試的：

```text
OpenAI / GPT API
DeepSeek
Qwen
GLM / Zhipu-compatible
OpenAI-compatible self-hosted / enterprise gateway
```

重要：

- 「ChatGPT」產品要求在 runtime/API 層應實現為 OpenAI GPT API / compatible model service，不得 scraping ChatGPT Web。
- OpenAI / DeepSeek / Qwen / GLM 是 Product Preset / Adapter concern，不得形成 legal branch。
- 若某 vendor protocol 與 OpenAI-compatible 不同，只做 thin Infrastructure Adapter。

不得在：

```text
Domain
Rule Engine
LangGraph decision routing
Agent business logic
Frontend legal logic
```

寫 vendor-specific if/else。

---

# 9. SOUTHBOUND PROVIDER ADMIN CONTROL PLANE

在現有 canonical frontend 的 Admin / System Settings 增加：

`模型服務 / Model Providers`

不得復活另一個 standalone admin app。

Admin 至少可：

```text
List Providers
Create Provider
Edit Provider
Enable / Disable
Replace Secret
Test Connection
Discover Models
List Models
Configure Model
Enable / Disable Model
Test Model
View Health
```

---

# 10. PROVIDER CONFIG CONTRACT

至少：

```text
provider_id
display_name
vendor_preset optional
protocol
base_url
deployment_class
trust_level
data_boundary
secret_ref
enabled
health_status
version identity
```

Vendor preset 只是 Metadata / UX helper。

---

# 11. MODEL CONTRACT

至少：

```text
model_id
provider_id
deployment_id
display_name
remote_model_name
capabilities
operations
max_output_tokens
embedding_dimension optional
priority
enabled
health_status
```

相同 remote model name 可以存在於不同 Provider；identity 不得只用 model_name。

---

# 12. SECRET SECURITY

Admin 可輸入 API Key / Credential，但正式流程：

```text
Browser
→ Backend
→ SecretStorePort
→ secret_ref
→ Provider metadata
```

DB normal metadata 只存 `secret_ref`。

Secret 不得出現在：

```text
GET response
browser localStorage/sessionStorage
Workflow State
AnalysisSnapshot
Prompt
Audit payload
Application logs
Exception message
Screenshots
GitHub artifacts
Source code
```

保存後 UI 只顯示 masked / configured state。

---

# 13. ENDPOINT SECURITY

External Provider endpoint 必須繼續使用既有 SSRF / URL validation。

禁止：

- URL credentials；
- metadata endpoint abuse；
- loopback/private network through external class；
- query/path injection；
- arbitrary URL from normal user analysis request。

Internal / Private Cloud model 不得通過「關閉 SSRF protection」來支援；應使用 governed deployment class / internal provider policy。

---

# 14. TEST CONNECTION / MODEL DISCOVERY

Admin UI 提供：

```text
[測試連線]
[讀取模型]
[測試模型]
```

Test Connection 必須真實經 canonical ProviderAdapter。

Typed health/error：

```text
HEALTHY
AUTHENTICATION_FAILED
ENDPOINT_UNREACHABLE
TLS_ERROR
MODEL_NOT_FOUND
CAPABILITY_UNSUPPORTED
SECRET_UNAVAILABLE
TIMEOUT
```

Remote `/models` result 只是 candidate discovery；不得自動 publish 到 canonical Model Registry。

---

# 15. USER MODEL SELECTION

普通分析用戶不得輸入 API Key / Base URL。

在分析確認/AI 輔助設定加入：

```text
AI Assistance Mode:
MINIMAL / STANDARD / ENHANCED

Model Selection:
AUTO / SINGLE / MULTI_MODEL
```

`AUTO`：ModelRouter 選擇。

`SINGLE`：用戶從 backend `eligible_models` 中選 1 個。

`MULTI_MODEL`：選 2..N 個 eligible models；N server-configured，首期可設定合理上限但不得散落 hardcode。

---

# 16. ELIGIBLE MODELS ARE BACKEND-OWNED

Frontend 只能呈現 backend eligible catalog。

Eligibility 至少受：

```text
tenant/project authorization
ModelUsagePolicy
data confidentiality/security
required capability
provider enabled
model enabled
health
trust/data boundary
```

即使用戶選擇 Model X，Backend 在 invocation 前仍需重新驗證。

---

# 17. SNAPSHOT MODEL PINNING

Draft 階段 model preference 可改。

Confirm / Start 後，Snapshot 必須 pin exact：

```text
selection_mode
selected model IDs
provider/model/deployment version IDs
ModelUsagePolicy version IDs
Prompt version IDs
LLM invocation policy version if governed/versioned
```

不得 pin credential value。

如果 confirmed analysis 後改 model preference：

不得 mutate S1 Snapshot；走 successor analysis/new snapshot semantics。

---

# 18. MULTI-MODEL INVOCATION

每個 model call 必須有：

```text
request_id
invocation_group_id optional
project_id
snapshot_id
provider_id/provider_version
model_id/deployment_id
operation/purpose
policy versions
prompt version
redaction run optional
status
usage if provider returns it
```

`MultiModelInvocationResult` 或 repo-equivalent 只能是 derived/candidate output。

不得把 multi-model consensus 寫進 Formal Result authority。

---

# 19. FIRST REAL WORKFLOW INTEGRATION

本輪至少把 real LLM wiring 接到一個真正 Stage 1 use case。

推薦優先：

```text
Real Requirement Document
↓
Parser
↓
LLMInvocationPolicy
↓
when semantic extraction is needed
↓
LLM-assisted Candidate Extraction
↓
Candidate BusinessFact / DataItem / DataFlow
↓
existing Context Resolution
↓
Formal Input
```

LLM output 必須：

- typed structured output；
- provenance / request identity 可追蹤；
- candidate only；
- conflict/low confidence 走 Context Resolution / Human Review。

不得讓 LLM 直接寫 formal fact/result。

---

# 20. KNOWLEDGE GAP INTEGRATION

第二個允許的 integration：

```text
RAG Retrieval
↓
Evidence Sufficiency = INSUFFICIENT
↓
LLM query expansion / missing-evidence analysis
↓
Re-retrieval within SAME allowed Knowledge Scope
```

LLM 不得放寬 scope。

如果仍不足：controlled stop / review。

---

# 21. RESULT EXPLANATION

可選實作：

```text
Formal Stage1 Result + LegalBasis + Evidence
↓
LLM Derived Explanation
```

Explanation 不得反向改 Formal Result。

---

# 22. FRONTEND UX

Admin UI 至少：

- Provider list / status；
- Provider editor；
- write-only API key input；
- test connection；
- discover models；
- model capability/config；
- model test；
- enabled/health state。

User Analysis UI 至少：

- AI Assistance Mode；
- AUTO / SINGLE / MULTI_MODEL；
- eligible model display name / provider / capability / health；
- policy-blocked/unavailable model 不得顯示為可選。

三語言：

```text
zh-CN
zh-HK
en-US
```

---

# 23. FRONTEND SMOKE

Browser smoke 至少：

```text
Admin Provider page renders
Create Provider works
Secret stays masked
Test Connection works
Model list/discovery works
Model test works
New Analysis works
AI Assistance settings render
AUTO works
SINGLE works
MULTI_MODEL works
```

要求：

```text
0 uncaught JS errors
0 owned i18n missing keys
0 unexpected console errors
0 retries
```

---

# 24. LOCAL CI PROVIDERS

Mandatory CI 不依賴 Internet / paid credential。

建立 protocol-realistic local test servers，至少模擬多 Provider identities / 多 Models，並真正經 HTTP ProviderAdapter。

至少證明：

```text
Provider A -> model A1/A2
Provider B -> model B1/B2
```

以及：

```text
AUTO
SINGLE A1
SINGLE B1
MULTI A1+B1
```

不得 mock `LLMServicePort` 後宣稱 Provider integration PASS。

可另提供 opt-in real external acceptance，例如 `REAL_LLM_E2E=1`，但 credential 不得進 evidence。

---

# 25. BACKEND TEST MATRIX

至少：

- multiple providers same tenant；
- multiple models per provider；
- same model name on different providers；
- create/edit/enable/disable provider；
- secret create/replace/non-return；
- endpoint/SSRF validation；
- health / connection test；
- discovery；
- OpenAI-compatible chat / structured / embedding；
- vendor thin adapter where empirically required；
- invalid key / timeout / unavailable model；
- eligible model filtering；
- AUTO/SINGLE/MULTI；
- policy denied；
- redaction required；
- cross-tenant denial；
- audit identity；
- snapshot pinning；
- historical snapshot unchanged；
- LLM cannot own legal result。

---

# 26. ARCHITECTURE CHECKS

在 existing 242 baseline 上新增 equivalent checks：

```text
single_model_registry
single_provider_registry
llm_invocation_requires_policy_trigger
rag_first_boundary_preserved
llm_parametric_knowledge_is_not_evidence
frontend_never_calls_provider_directly
admin_secret_is_write_only
api_key_never_returned
multiple_provider_instances_supported
multiple_models_per_provider_supported
vendor_preset_not_legal_logic
user_model_selection_is_allowlisted
user_selection_does_not_bypass_policy
model_selection_is_snapshot_pinned
multi_model_output_is_derived
multi_model_vote_not_legal_authority
llm_cannot_own_classification
llm_cannot_own_applicability
llm_cannot_own_crossborder
llm_cannot_own_risk
llm_cannot_own_final_path
stage2_not_started
```

既有 architecture checks 全部保留。

---

# 27. MIGRATION POLICY

先證明是否需要 migration。

如果 existing Phase1C model/provider/deployment schema 足夠，優先 reuse，`NO MIGRATION`。

只有確有缺失才允許 additive：

`0016_phase1kb_multi_provider_llm_governance`

不得修改 `0001–0015`，不得 parallel head。

---

# 28. EXTERNAL AGENT API BOUNDARY — DESIGN FREEZE ONLY

本輪不要實作完整 Northbound External Agent API，但必須鎖定下一階段 M2-E 不得破壞的 boundary：

```text
Third-party Platform
→ Public Agent API
→ Unified Application Use Cases
→ SAME Intake / Document / Snapshot / Workflow / Formal Result
```

與：

```text
LLMServicePort
→ ProviderAdapter
→ Model Provider
```

是不同 trust boundary。

確認 External API 未來只能傳：

- canonical business input；
- document upload/reference；
- registered eligible model-selection request；

不能傳：

- provider API key；
- arbitrary base URL；
- unregistered model；
- Formal Result injection；
- raw LangGraph state。

---

# 29. EXISTING REGRESSION BASELINE

不得降低：

```text
Backend       >= 763
Architecture  >= 242 existing + new K-B checks
Runtime       25/25
Frontend      >= 121

M2-D 3/3
M2-C 3/3
M2-B 3/3
M2-A 3/3
M1   3/3
M0   36/36
Retries 0
```

以及 typecheck / lint / build / i18n / migration PASS。

---

# 30. DEDICATED CI

新增 dedicated workflow：

`Phase1KB Multi-provider LLM Governance`

至少覆蓋：

- architecture；
- PostgreSQL；
- multi-provider local servers；
- secret boundary；
- provider/model health；
- AUTO/SINGLE/MULTI；
- real HTTP invocation；
- real workflow candidate extraction；
- frontend admin/user model UI；
- three-locale smoke；
- regression。

---

# 31. EXACT-HEAD CLOSURE

Final PR Head 必須：

```text
tested_pr_head_sha
== runner_checkout_sha
== PHASE1KB_FINAL_SHA
```

不得借用 earlier commit evidence。

PR 保持 Draft，未完成 exact-head closure 前不得 merge。

---

# 32. REQUIRED DELIVERABLES

至少：

```text
docs/phase1kb/Phase1KB_design.md
docs/phase1kb/Phase1KB_llm_invocation_policy.md
docs/phase1kb/Phase1KB_multi_provider_contract.md
docs/phase1kb/Phase1KB_model_selection_contract.md
docs/phase1kb/Phase1KB_secret_security.md
docs/phase1kb/Phase1KB_admin_ui.md
docs/phase1kb/Phase1KB_user_model_ui.md
docs/phase1kb/Phase1KB_workflow_integration.md
docs/phase1kb/Phase1KB_test_result.md
docs/phase1kb/Phase1KB_m2e_handoff.md
```

以及 machine-readable measured evidence。

---

# 33. HIGH REASONING ESCALATION

以下任一出現立即 STOP：

```text
need second ModelRegistry
need second Provider registry
API key must be plaintext persisted
user selection bypasses ModelUsagePolicy
LLM must directly write Formal Result
knowledge insufficiency requires using model memory as evidence
snapshot model identity cannot be pinned immutably
multi-model requires second workflow runtime/checkpointer
vendor support requires country/legal hardcode
```

輸出：

`HIGH_REASONING_ESCALATION_REQUIRED — PHASE1K-B = BLOCKED`

提供 exact contract/counterexample/minimum resolution options。

---

# 34. FINAL PASS DEFINITION

只有以下全部成立：

```text
LLMInvocationPolicy PASS
RAG-first/Evidence-first boundary PASS
OpenAI/GPT API support PASS
DeepSeek support PASS
Qwen support PASS
GLM support PASS
Multiple Provider instances PASS
Multiple Models per Provider PASS
Admin Provider/Model Control Plane PASS
Secret Boundary PASS
Connection Test PASS
Model Test/Discovery PASS
AUTO PASS
SINGLE PASS
MULTI_MODEL PASS
Snapshot Model Pinning PASS
Real HTTP Provider Invocation PASS
Real Workflow Candidate Extraction PASS
Knowledge Gap Query Expansion Boundary PASS
Frontend Smoke PASS
Three Locales PASS
Full Regression PASS
Exact-head CI PASS
```

才輸出：

```text
PHASE1K-B = PASS
M2-E EXTERNAL AGENT API ENTRY = ALLOWED
STAGE1 FULL E2E ENTRY = BLOCKED UNTIL M2-E MAIN CLOSURE
Stage 2 = NOT STARTED
```

---

# 35. FINAL EXECUTION ORDER

```text
1. Verify exact baseline main/tag/Alembic
2. Create Phase1K-B branch/worktree
3. Read Master V3.7 / Phase0 V3.7 / Architecture Rules
4. D0 inventory
5. Freeze LLMInvocationPolicy
6. Freeze provider/model/secret ownership
7. Implement multi-provider backend
8. Implement connection/model test & health
9. Implement Admin model control plane UI
10. Implement eligible model API
11. Implement AUTO/SINGLE/MULTI_MODEL