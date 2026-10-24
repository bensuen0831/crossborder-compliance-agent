# KB01 additive migrations

Formal main remains 060cbb5 / 0020. The working branch adds 0021_kb01_taxonomy_operations, directly parented by 0020_stage1_formal_decision_engine_compatibility. Frozen 0001–0020 are byte-identical.

0021 adds canonical AdminChangeSet operation receipts, retention holds, and exact classification-label components of KnowledgeDocumentVersion. Composite tenant/version/definition FKs prevent cross-tenant and mismatched registry pins. It adds only compatible unique keys to existing canonical tables. No historical result, source, candidate, snapshot or actor is fabricated or rewritten.

Receipt and released-hold history are immutable. Classification labels cannot be rewritten after draft ingestion. Downgrade to 0020 is allowed only with no new receipts, holds or label data; otherwise KB01_TAXONOMY_DOWNGRADE_REFUSED preserves administration evidence. Fresh/exact-release upgrade, complete schema/trigger/function equivalence, representative old-row digests, safe downgrade/re-upgrade and unsafe refusal are tested in test_kb01_taxonomy_migrations.py.

B/C operational upload/batch/parser additions remain proposed. Additional migrations may be added within the user's V2 compatible scope after their own design and safety tests; 0021 will remain frozen once package A is sealed. Irreversible or destructive cross-owner changes require a concrete decision, not a blanket implementation pause.
