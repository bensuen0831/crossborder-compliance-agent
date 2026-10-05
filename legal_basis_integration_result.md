# Phase1I — canonical legal authority

Phase1I Track: `phase1i-applicability-country-scenario`; verified base `700951ebb9ebdf33e399158fd3fb53bb4a6c87e7` / `v3.6-phase1h-pass`. Frozen implementation SHA: `131d101cdd02999aa478c1a730f492c1729caf30`. DRAFT PR: [#18](https://github.com/bensuen0831/crossborder-compliance-agent/pull/18), target main; no merge. Final validation evidence is recorded in [test_result.md](test_result.md) and `evidence/phase1i`. Earlier-phase sections, where present, remain historical evidence.

REUSE decision: canonical KnowledgeDocument/KnowledgeDocumentVersion identifies the reviewed regulation version. KnowledgeStructureNode extends existing RegulatoryStructureNode; ingestion's regulation_version_ref is the same knowledge version ID. Canonical LegalBasisItem references the node with official source and locator. No Regulation, RegulationVersion, Article, Section or LegalBasis table was added.

The adapter verifies knowledge/node/basis tenant, jurisdiction, version, effective dates and official source/locator agreement; the article citation must appear in the authorized jurisdiction-specific T1/T2 G evidence pack and reference active validated canonical evidence. Missing/expired/revoked provenance fails conservatively. Canonical Wiki/Graph or unverified external text cannot substitute for the required legal chain.

Existing LegalBasisRuleHitLink and LegalBasisEvidenceLink M:N tables are reused. Links are created only for RuleHits explicitly declaring that basis and the corresponding canonical article evidence; arbitrary pack evidence is not associated with every legal basis. Formal results retain other authorized evidence as provenance without claiming those extra citations prove the article.

Tests cover real canonical chain, missing/wrong locator, current evidence revocation, idempotent associations and unchanged official authority across zh-CN/zh-HK/en-US presentation.
