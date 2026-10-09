# M2-E-R1 owning-contract recovery — schema escalation

HIGH_REASONING_ESCALATION_REQUIRED. M2-E-R1 = BLOCKED. M2-E RESUME = BLOCKED.

## Proven blocker

The original real PostgreSQL/HTTP counterexample was reproduced before the correction: confirmation returned422 INVALID_INPUT (1 failed in4.80s). R1 WIP now creates explicit governed A/B binding pins and the exact Rule union in one transaction, while retaining a single ACTIVE Scheme and the Rule/Scheme scope validation. The first owning PostgreSQL test successfully resolves/pins both jurisdictions and classifies A, then fails while persisting B.

PostgreSQL raises `UniqueViolation` for `uq_formal_classification_snapshot`:

```text
same tenant + project + snapshot + DataItem + Scheme Version
jurisdiction A result persisted
jurisdiction B result rejected
```

The actual existing database index is:

```sql
CREATE UNIQUE INDEX uq_formal_classification_snapshot
ON public.classification_results
USING btree (tenant_id, project_id, analysis_snapshot_id, subject_id, scheme_version_id)
WHERE (formal_provenance_json IS NOT NULL);
```

Frozen migration `0008_phase1h_rule_classification.py:92` defines this index. `ClassificationResultEntity.jurisdiction_id` is already present and non-null, but the unique execution identity excludes it. Application-side duplicate lookup now includes jurisdiction, exposing the persistence mismatch instead of returning A's result as B's result.

This proves that existing schema cannot persist the approved identity `(tenant, project, snapshot, data_item, jurisdiction, scheme_version)` for two jurisdiction executions of the same item and Scheme. No second registry/store or new table is needed, but an owning **additive index migration** is required.

## Minimum compliant option requiring architecture approval

Approve a separate owning migration after existing WIP0017, for example `0018_m2e_r1_classification_identity`, parent `0017_m2e_external_agent_api`. Replace the partial unique index with the same predicate and columns plus `jurisdiction_id`; retain canonical table/result identities and historical rows. Do not modify frozen0001–0016 or append this unrelated owner change to M2-E infrastructure0017.

Upgrade does not require rewriting historical results: old uniqueness already implies uniqueness under the expanded key. Reads/idempotency must use the full jurisdiction-scoped execution identity. Downgrade must explicitly refuse when multiple A/B results share the old key, because reinstating the former index would collide. Require fresh/upgrade/equivalence/downgrade-refusal/re-upgrade evidence before claiming recovery.

Keeping the schema unchanged leaves recovery BLOCKED. Different synthetic Scheme identities, subject IDs or snapshot IDs per jurisdiction would misrepresent the approved execution identity and are not proposed.

## Historical compatibility impact

Legacy plans retain the single-jurisdiction execution path; new plans carry exact `classification_bindings`. Historical execution must read exact pins, never active bindings/rules. Historical results remain immutable. R1 WIP adds jurisdiction provenance to new RuleHits and scopes classification/applicability reads; old RuleHit deserialization and historical digest compatibility still need the required regression gate. These are not claimed PASS.

## Measured executions / work retained

- Before fix: original counterexample1 FAILED in4.80s.
- Initial focused Phase1H PostgreSQL + Phase1L-B contract execution:41 PASS, with vertical slice1 FAILED later at obligation WARNING. This was an intermediate WIP execution, not final regression evidence.
- New owning execution identity test:1 FAILED in2.54s, specifically the PostgreSQL unique-index collision above. It is retained unchanged and not skipped or deselected.
- The extended genuine A/B fixture publishes destination knowledge, applicability and ordinary owning-policy versions through existing review/publish services. Its subsequent vertical run timed out; investigate only after schema approval. Confirmation had progressed past the original classification error, but completed workflow acceptance is **not established**.
- Complete Phase1H/I/J/L-B, M1/M2-A/B/C/D, Phase1K-B regressions, new architecture checks and temporal/review recovery gates: pending, not claimed PASS.
- No new migration or schema mutation was applied for R1. Existing0017 remains M2-E infrastructure only. Frozen migration bytes and Rule governance remain unchanged.
- PR27 identities/OAuth/service credentials/project binding/façade/SSE/WS/webhooks WIP preserved. No Admin UI/SDK/OpenAPI/browser/exact-head closure, merge, tag, Stage1 Full E2E or Stage2 work started.

Stop under the user's R1 section26: if existing schema is insufficient, report HIGH_REASONING_ESCALATION_REQUIRED before creating a migration.
