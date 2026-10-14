# Migration review plan

No migration created. Head remains0020; frozen0001–0020 verified byte-identical against tagged baseline. Proposed first revision:0021_kb01_ingestion_operations, parent0020_stage1_formal_decision_engine_compatibility, after source-owner design approval. Scope: additive operational upload/batch/manifest relations and canonical Knowledge binary/metadata/provenance fields. No legal-result engine/version or old result changes.

Upgrade: deterministic defaults only for technical fields; no fabricated file uploads, reviews or actor consent. Do not rewrite historical Knowledge/Snapshot/SourceTrace rows. Any shared-owner generalization has a separate exact schema/compatibility review before SQL is written. Downgrade allowed only with no retained new authority/provenance records; refuse data loss. Verify fresh, exact0020 upgrade, schema equivalence, old rows and pins unchanged, safe downgrade/re-upgrade, unsafe refusal, frozen bytes, single head.
