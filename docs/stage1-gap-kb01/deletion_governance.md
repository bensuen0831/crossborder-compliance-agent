# Deletion and archival governance

Deletion eligibility is computed by the canonical management owner from lifecycle, references, retention policy and holds. Missing or ambiguous policy fails closed. Published or referenced versions require archive/deactivation rather than history deletion. Separate current delete/archive grants are mandatory; an administrative coarse grant does not replace them.

AdminChangeSet retains canonical operation authority. Immutable admin receipts and hold history record actor, time, reason, CAS and idempotency without storing secrets. SQL statistics reconcile the retained document/version/import universe rather than decrementing competing counters. Unsafe migration downgrade refuses evidence loss.

See [deletion/retention policy](deletion_retention_policy.md), [security](security_design.md) and PostgreSQL tests/test_kb01_document_management_postgres.py and tests/test_kb01_taxonomy_postgres.py. Final-head validation is recorded separately.
