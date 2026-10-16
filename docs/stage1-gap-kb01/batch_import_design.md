# Durable batch import and optional catalogue

BatchItem is operational work over existing versioned uploads and KnowledgeVersion, not another Document or Workflow authority. Real archive extraction retains exact member bytes, safe relative paths and immutable manifest identity. It refuses traversal, links, collision, encrypted/unsupported and bounded-resource violations. Each child must independently reach VERIFIED before explicit metadata mapping creates a canonical draft.

CSV/XLSX catalogue import persists immutable proposals and row provenance. Full relative paths, duplicates and missing files are reported. An imported row is never an uploaded, validated or published regulation. Explicit human mapping pins the exact row/canonical governed metadata versions and creates a normal Knowledge draft in the same transaction as original attachment. Missing/duplicate/unmatched rows cannot silently map.

Backend projections expose pending child transport even while batch state is PREVIEW. The UI polls the canonical state and disables unavailable mapping; server CAS/verified-original checks remain authority. Durable ingestion/cancel/retry/restart preserves original identities, completed runs and audit receipts.

See [Manifest contract](manifest_contract.md), [Manifest persistence decision](manifest_persistence_decision.md), and real PostgreSQL/S3 tests/test_kb01_manifest_imports_postgres.py, tests/test_kb01_batches_postgres.py and tests/test_kb01_batch_recovery_postgres.py.
