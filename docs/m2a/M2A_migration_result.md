# M2-A migration

Baseline `83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1`; preserved WIP `325b4a6c0ca3a6f4f0d58552634bcc7dcadca24b`. Implementation source is pinned in `evidence/m2a/approved_owner_overlay.json`. Full closure/exact-head CI are required before an overall PASS.

Single linear revision0011_m2a_intake, predecessor0010_phase1j. Frozen migrations0001–0010 unchanged. One JSON column structured_provenance_json on existing business_facts; provenance validation/immutability trigger and function. No new table/source of truth. Historical0002 live Base.metadata is accommodated without modifying it.

Actual PostgreSQL dual path PASS: fresh→head; archived exact83d79c baseline→0010 then current→0011; full columns/constraints/indexes/functions/triggers catalog equivalence; empty0011→0010→0011 roundtrip; retained structured authority downgrade refusal before DDL and Alembic revision mutation. Refusal requires explicit archive/export; no silent provenance loss. Machine evidence: m2a_migration_dual_path.json in closure artifacts/CI runtime artifact.

Historical J migration regression now captures the actual pre-refusal Alembic head, preserving transactional/schema assertions and valid descendant behavior. No arbitrary future revision/head acceptance.
