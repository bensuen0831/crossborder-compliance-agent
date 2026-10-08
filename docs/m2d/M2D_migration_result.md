# Additive review migration

`0015_m2d_review_governance` is the only successor to `0014_m2c_formal_result_authority`. Existing review_tasks/review_decisions are reused. Structured descriptor/support/role fields and full immutable canonical decision audit are added; review_corrections stores typed foreign-key lineage and owning selections, not a generic formal-result store.

Frozen0001–0014 retain byte identity. Upgrade accounts for historical0002 live Base.metadata without rewriting it. PostgreSQL tests compare complete catalogs for empty fresh→15 and exact verified-main14→15. Empty downgrade/re-upgrade is supported. Persisted governed task/decision/correction authority causes transactional refusal requiring archive/export; no silent deletion. UPDATE/DELETE on canonical review history/lineage is refused.

Measured focused dual-path evidence: all5 migration policies PASS in artifacts/m2d/migration_dual_path.json. D6 reexecutes this test within the mandatory full suite; final exact-head evidence is retained separately.
