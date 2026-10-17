# KB01 operational migration plan

Release baseline remains0020 on main060cbb5. The feature's single head is0024_kb01_import_manifest_records. Frozen0001–0020 retain release bytes; committed-source seals also preserve approved0021–0024 bytes. No historical formal result or candidate authorization is rewritten.

0021 adds technical administration receipts, holds and exact governed document labels under existing Knowledge/Metadata owners.0022 adds versioned binary multipart sessions/parts, attachment receipts and durable import work.0023 preserves full source references in the existing Evidence owner with PostgreSQL-only bounded index DDL.0024 adds immutable optional catalogue manifests/rows and exact confirmed mapping lineage, plus auditable explicit KnowledgeBinding edits.

Fresh upgrade, exact predecessor upgrade, schema equivalence, allowed empty downgrade, retained-authority downgrade refusal, re-upgrade and frozen-history identity are tested. No cleanup/backfill invents actors, legal evidence, publication or confirmation. Large originals remain provider-versioned objects, not database BLOBs.

See [database design](database_design.md), [migration plan history](migration_plan.md), and the four tests/test_kb01*_migrations.py authorities. Final complete gate must rerun at the final PR SHA.
