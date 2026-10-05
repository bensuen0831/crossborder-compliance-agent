# Phase1I — generic typed skills

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

RegulationApplicabilitySkill, LegalBasisSkill, EvidenceValidationSkill, DataClassificationSkill, JurisdictionAnalysisBoundary and KnowledgeScopeValidationBoundary are pure typed domain operations. SQLAlchemy, network/provider SDKs, scope selection and persistence stay in infrastructure adapters. The Country facade composes ports; profiles/configurations supply jurisdiction/scenario differences.

LegalBasisSkill validates the canonical knowledge version/node/basis/evidence projection. EvidenceValidationSkill consumes formal Phase1G sufficiency and cannot promote partial or conflicted evidence. DataClassificationSkill consumes scoped H classifications, never classifies narrative. Jurisdiction/scope boundaries verify existing formal/pinned identities.

The explicit scenario RuleHit adapter closes a documented gap: it delegates validated business facts, already pinned H rules and same-snapshot scoped G PROJECT evidence to the existing SafeRuleEngine with data_item_id=None. It stores canonical SCENARIO RuleHits without writing a ClassificationResult. Actual no-data PostgreSQL tests prove this path and data-specific capability NOT_APPLICABLE behavior.
