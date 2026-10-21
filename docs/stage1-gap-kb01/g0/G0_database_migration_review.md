# G0 database migration review

AI independent-pass / **second-pass review**, not a designated human or third-party approval. Review date 2026-10-21T03:27:46.611373+00:00. Product source `39c3581ca455df4e3ce9760ed2deab8905a5f588`; main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`; prior independently archived acceptance commit `bd30290c577e8ac16cbb88a20a0535553fb6bd00`. These are three different identities. No product source, test assertion, frozen migration or release tag was changed for this review. PR29 remains Draft. No merge or Stage2 is authorized.

Code references below resolve against [the reviewed product tree](https://github.com/bensuen0831/crossborder-compliance-agent/tree/39c3581ca455df4e3ce9760ed2deab8905a5f588); the original complete acceptance package is [separate evidence](https://github.com/bensuen0831/crossborder-compliance-agent/tree/bd30290c577e8ac16cbb88a20a0535553fb6bd00).

VERIFIED using real PostgreSQL.

- `0020_stage1_formal_decision_engine_compatibility` → `0021_kb01_taxonomy_operations`: Composite tenant FKs/labels, canonical operation receipts and hold guards; unsafe audit-loss downgrade refusal.
- `0021_kb01_taxonomy_operations` → `0022_kb01_binary_transport`: Operational multipart/attachment/batch/items, immutable receipts and exact version references; no legal result store.
- `0022_kb01_binary_transport` → `0023_kb01_evidence_source_reference`: Lossless existing source_ref Text widening with 32768-byte guard; non-unique md5 accelerator is not authority; unsafe >500-char downgrade refused.
- `0023_kb01_evidence_source_reference` → `0024_kb01_import_manifest_records`: Bounded immutable catalogue proposals, composite tenant/batch membership and immutable confirmed mapping; downgrade refuses evidence loss.

0001–0020 bytes match release main;0021–0024 bytes match the reviewed source and sealed source proof. Composite tenant/version/batch FKs and RESTRICT relationships protect membership. Append-only receipt/hold/attachment/manifest guards prevent evidence rewriting; expiry/lifecycle state uses record_version/CAS and row/advisory locks. Root-before-version and batch-before-item lock order was inspected. Safe downgrade/re-upgrade, exact predecessor upgrades, fresh/catalog equivalence, row preservation and unsafe refusal tests ran again. No0025 was introduced.

Caveat: historical0002 imports runtime ORM metadata. The existing tests reconstruct exact historical bootstrap metadata from committed Git blobs; current fresh schema is independently tested. Source-ref0023 uses md5 only as a non-unique lookup accelerator, never identity or provenance verification. Query growth finding001 concerns taxonomy read scalability, not schema corruption. Backup/restore and production deployment operations are NOT ACCEPTED here.
