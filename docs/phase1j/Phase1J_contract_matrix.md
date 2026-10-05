# Phase1J contract matrix

Baseline `594be84cfc471af4c12f28600b22cffb66f830f7`. All entries below are design decisions, not implemented classes/endpoints. REUSE = existing canonical contract/mechanism unchanged; EXTEND = additive versioned capability within the existing owner; CUSTOM_BUILD = proven missing pure decision behavior or typed result storage, never a replacement shared subsystem.

## Reuse-first audit

| Capability | Decision | Existing authority / required delta |
|---|---|---|
| Formal facts/items/flows/scenario/jurisdiction | REUSE | domain/context_resolution.py; persistence/context_models.py and context_repositories.py; validated E context pin |
| Snapshot/project identity | REUSE | domain/foundation.py AnalysisSnapshot; persistence/models.py; verify pinned ProjectVersion and exact subject |
| Knowledge authority/scope | REUSE | existing F KnowledgeDocumentVersion/RegulatoryStructureNode and pinned authorized scope; never copy regulation text |
| Evidence/sufficiency/fallback | REUSE | domain/retrieval.py EvidencePackItem/KnowledgeSufficiencyResult/ActionableFallbackGuidanceContext; existing G retrieval repository revalidation |
| Classification/RuleHits | REUSE | domain/classification.py, domain/rules.py; canonical H repository and immutable rule/version pins; no fabricated hit |
| LegalBasis/M:N | REUSE | LegalBasisItemEntity, LegalBasisRuleHitLinkEntity, LegalBasisEvidenceLinkEntity; no alternate citation/evidence table |
| Applicability | REUSE | RegulationApplicabilityResult and existing I read/preparation boundary; legal_obligation=False remains unchanged |
| Country/scenario/capability | REUSE | compliance_profiles.py and CountryComplianceSkill; availability remains distinct from legal effect |
| Conditions | REUSE | domain/rule_ast.py bounded typed JSON predicates; missing facts are unresolved, not false |
| Metadata/publish/registry | EXTEND | existing MetadataDefinition/MetadataVersion/admin review/outbox/RegistrySync; add four typed J policy kinds and validators, no registry/store |
| Localization | REUSE | localized_metadata.py, metadata_presenter.py; labels outside formal calculations, stable codes and original legal authority |
| Snapshot policy pins | EXTEND | existing AnalysisSnapshotRegistryPin and explicit initialization; J namespaces/dependency digest only |
| Obligation DTO | EXTEND | contracts.py ComplianceObligationDTO: v2 authoritative fields; v1 remains transport-compatible |
| Candidate DTO | EXTEND | CandidateCompliancePathDTO: v2 prerequisites/legal viability/availability/support fields |
| Risk DTO | EXTEND | RiskAssessmentDTO and RiskLevel: v2 dimensions/policy/sufficiency/typed decimal output |
| Recommendation DTO | EXTEND | ComplianceRecommendationDTO: v2 deterministic ranking/tie and selected candidate refs; description cannot decide |
| Final DTO | EXTEND | FinalCompliancePathDTO/CompliancePathStepDTO: v2 unresolved states/full provenance/conditions; no execution/approval fabrication |
| Pure stage calculations | CUSTOM_BUILD | Missing obligation binding, path generation, risk aggregation, deterministic recommendation and final assembly; reuse AST rather than new Rule Engine |
| Formal result persistence | CUSTOM_BUILD | No obligation/candidate/risk/recommendation/final result tables exist; existing CompliancePathStepEntity is project/sequence/name only, not snapshot decision authority |
| Repository/application boundary | EXTEND | CountryComplianceRepositoryPort/PostgresCountryComplianceRepository and existing service composition: stage prepare/save/read; existing sessions/scoped repositories, no new repository framework |
| Workflow/review | REUSE | L-A SemanticStep, StageExecutionRequest/Result and ReviewTask; result_ref points to persisted envelope; wiring deferred to L-B |
| Stage1/UI DTOs | REUSE | Stage1ComplianceResultDTO is a projection; no fabricated fill-in to satisfy old response shapes; no frontend implementation |

Audit anchors: `domain/contracts.py:105–125`, `domain/regulation_applicability.py:129`, `domain/rules.py:109`, `domain/retrieval.py:130/233`, `domain/metadata.py:573`, `persistence/models.py:353/497/507/551`, `persistence/applicability_models.py:9`, `application/country_compliance_services.py:44`, `application/workflow_skeleton.py:11/61/71`. Paths are relative to src/crossborder_compliance. Consumed handoffs: docs/delivery/phase1i/integration_handoff.md, stage1_alpha_integration_handoff.md, docs/phase1l_a/integration_handoff.md and snapshot_checkpoint_boundary_result.md. Their historical head/count notes do not supersede the verified round2 baseline.

## Typed shared envelope and references

Each stage envelope: `result_id:UUID`, `contract_version:Literal["2.0"]`, `stage_kind` fixed per stage, `tenant_id/project_id/analysis_snapshot_id:UUID`, `project_version_id:UUID`, `context_version:int>=1`, `subject_type:DATA_ITEM|DATA_FLOW|SCENARIO`, `subject_id:UUID`, `data_item_ids/data_flow_ids/scenario_definition_ids:tuple[UUID]`, `jurisdiction_ids:nonempty tuple[UUID]`, `analysis_as_of_date:date`, `upstream_refs:tuple[StageRef]`, `items:tuple[that stage's v2 DTO]`, `input_sufficiency:SUFFICIENT|INSUFFICIENT_EVIDENCE|UNKNOWN`, `conflict_state:CLEAR|CONFLICTED`, `review_required:bool`, `reason_codes:nonempty tuple[StableDisplayCode]`, `confidence:Decimal[0,1]`, `pins:tuple[PinRef]`, `input_digest/pins_digest:SHA256`, `engine_version`, `provenance`, immutable audit metadata. No untyped arbitrary decision dictionary.

`StageRef` = typed kind + envelope UUID + optional item UUID + content digest; `PinRef` = canonical existing pin UUID + definition/rule UUID + version UUID + version number + kind. `LegalSupport` = canonical applicability result refs, matched H RuleHit IDs/version refs, LegalBasis IDs, G evidence/pack/retrieval refs, knowledge version/node/citation/locator refs and fact refs. Official source language/text remains in the canonical authority. Validate every reference under tenant/snapshot/subject/jurisdiction/current permissions; a syntactically valid UUID is not sufficient.

`Condition` = policy entry UUID + stable code + predicate digest/reference + TRUE|FALSE|UNKNOWN evaluation + required fact/evidence refs. Preparation compiles the referenced predicate with the existing typed AST; results do not create a copied policy authority. `Action` = policy entry UUID + stable action code + responsible canonical party refs + conditions + dependency refs. Condition/action arrays cannot be replaced by localized prose. Empty items require explicit NOT_APPLICABLE or unresolved/coverage reason; they never imply permission.

Typed provenance retains originating StageRefs, canonical context/retrieval references, policy/rule/knowledge PinRefs, engine/schema versions, computation timestamp, request/correlation IDs and trusted actor reference. It cannot carry executable callbacks or caller-supplied decisions. Each item records the jurisdiction(s) and obligation/support coverage it actually assessed; envelope jurisdiction coverage does not imply every item applies everywhere. Required jurisdiction sets come from validated E/I context and pinned policy, never client narrowing. Confidence is policy-derived input/support coverage, not an LLM rating.

## Stage-specific payloads

| Stage / existing DTO kind | Required typed v2 fields beyond common identity/support | Ordinary summary outcomes |
|---|---|---|
| Obligation / ComplianceObligationDTO | obligation_id; requirement_id is stable UUID of the governed policy entry; obligation_code; legal_effect; fulfillment_state; conditions; responsible_party_ids; applicability_result_ids; rule_hits/legal_basis/evidence; policy_version_ref; prohibition/localization effect code if legally established | OBLIGATIONS_IDENTIFIED / NOT_APPLICABLE / UNDETERMINED |
| Candidate / CandidateCompliancePathDTO | candidate_path_id; path_code; governed template entry UUID/version; prerequisite conditions; obligation refs and coverage; unmet requirement refs; mechanism entry refs; ordered typed steps; LegalSupport; capability dependencies with availability; legal_viability; operational_availability; input/support provenance | CANDIDATES_IDENTIFIED / NO_VIABLE_PATH / NOT_APPLICABLE / UNDETERMINED |
| Risk / RiskAssessmentDTO | risk_assessment_id; assessed candidate/context refs; factor observations and fact/evidence refs; dimension scores/bands; aggregate score:Decimal|null; risk_level; risk_policy_version_ref; coverage/confidence; score mode/scale/rounding; review reasons | ASSESSED / NOT_APPLICABLE / UNKNOWN |
| Recommendation / ComplianceRecommendationDTO | recommendation_id; candidate/risk result refs; considered/excluded candidate refs with reasons; ordered policy criterion outcomes; priority codes; tied alternatives; selected_candidate_id:UUID|null; policy_version_ref; review/escalation flags | RECOMMENDED / CONDITIONAL_ALTERNATIVES / TIED / NO_RECOMMENDATION / NOT_APPLICABLE |
| Final / FinalCompliancePathDTO | final_path_id; recommendation/candidate/obligation/risk refs; selected_candidate_path_id:UUID|null; applicable obligations; ordered actions/steps with unmet conditions; LegalSupport; residual risk ref (no claimed reduction from unperformed controls); alternatives; review_status; unresolved codes; complete transitive pin/provenance chain | PROPOSED / CONDITIONAL_PROPOSAL / NO_VIABLE_PATH / NOT_APPLICABLE / UNDETERMINED |

All stage summaries are subordinate to CONFLICTED/INSUFFICIENT_EVIDENCE/REVIEW_REQUIRED precedence. APPROVED is never emitted by engine execution: a future explicit authorized review can reference the existing ReviewTask decision without altering computed truth or immutable results. Review approval cannot assert missing facts/actions were satisfied. Final LEGALLY_PROHIBITED is representable only with sufficient complete required-jurisdiction coverage and formal prohibition support; NO_VIABLE_PATH alone is not that assertion.

## Versioned policy payloads / service boundary

Four existing-metadata kinds: OBLIGATION_POLICY (applicability bindings, bounded typed predicates, legal-basis supported effects/requirements), COMPLIANCE_PATH_POLICY (template/mechanism/step stable entry IDs, prerequisites, obligation coverage, capability deps), RISK_POLICY (factor/dimension types, maps, coverage, aggregation, bands/rounding), RECOMMENDATION_POLICY (eligibility filters, ordered ranking, comparability, tie/escalation rules). Reuse effective dates, independent review, published ACTIVE versions, persisted policy examples/static validation and localization contract. Country/scenario profiles reference these versions through additive version-compatible metadata; conflicting scenario priorities require review and cannot override law.

Future reference-only requests contain project/snapshot/subject/jurisdiction/upstream result refs and idempotency key; clients cannot supply legal facts, scores, result status, policies or permissions. Existing trusted service preparation resolves authorized immutable inputs; pure calculators return typed results; the owning persistence boundary validates and saves atomically. Exact J read/execute scopes are additive operation permissions alongside project:{id}:comply, not production authentication redesign. Existing I/H/G operation permissions/owner checks are retained when consuming their results. No DB access inside pure engines.
