# Phase 1B — Domain Foundation Design

Phase 1B implements the V3.6 frozen Domain / Typed Contract as a PostgreSQL persistence foundation only. It excludes Country/Product/Regulation-specific rules, RAG business logic, risk scoring, final compliance decisions, country-agent implementation and production compliance orchestration.

## Domain aggregates
- Identity / Project: Tenant, Organization, UserContext, PermissionContext, Project, ProjectVersion.
- Party: LegalEntity, ProjectParty, PartyRoleAssignment, DataFlowPartyLink, ContractPartyLink, PathStepResponsibleParty.
- Document: Document, immutable DocumentVersion, SourceTraceRef, placeholder DocumentParseRun.
- Data Inventory: DataItem, DataItemGroup, DataFlowNode, DataFlowEdge, DataItemFlowLink, DataItemProductLink.
- Jurisdiction: Jurisdiction, JurisdictionRelation.
- Classification: ClassificationScheme, ClassificationCategory, ClassificationLevel, ClassificationResult; no country rules.
- Evidence / Legal Basis: EvidenceReference, Citation, LegalBasisItem, LegalBasisRuleHitLink, LegalBasisEvidenceLink.
- Analysis / Workflow: AnalysisSnapshot, WorkflowRun, WorkflowNodeRun, AnalysisStageResult, ReviewTask, ReviewDecision, ExecutionIdempotencyRecord.
- Interaction: ChannelContext, InteractionSession, ConversationThread, ConversationMessage.

## Source-of-Truth
classification_results is the sole formal classification result store; RegulatoryStructureNode is canonical legal structure; WorkflowStageView is projection-only; LegalBasis ↔ RuleHit is M:N; AnalysisSnapshot is separate from LangGraph checkpoint metadata; API idempotency is separate from workflow execution idempotency; Domain Alembic never owns checkpoint tables; ConversationThread is distinct from LangGraph thread_id.

## Versioning / mapping / authorization
Versioned roots use immutable version rows plus active pointer/status. Repository access is built from TenantContext + UserContext + PermissionContext, not request tenant_id. Mapping is centralized: SQLAlchemy model ↔ Domain/DTO ↔ Application DTO ↔ API DTO.
