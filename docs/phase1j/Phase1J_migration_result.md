# Phase1J migration result

Migration: `0010_phase1j`; parent `0009_phase1i`; exactly one Alembic head. Migrations0001–0009 are unchanged. DDL is explicit and independent of live Base.metadata, while CREATE IF NOT EXISTS accommodates historical0002's live metadata behavior on a fresh install.

Five authoritative stage tables: compliance_obligation_results, candidate_compliance_path_results, risk_assessment_results, compliance_recommendation_results, final_compliance_path_results. Composite parent FKs enforce tenant/project/snapshot/project-version/context/subject identity. Canonical snapshot/project/policy FKs, input uniqueness, ownership, typed versions, provenance and immutable update/delete triggers are present. Obligation applicability links are scoped references. decision_request_keys stores only immutable request aliases/fingerprints/result references, with a scoped typed target trigger; it is not another result authority. The inherited workflow idempotency ledger requires a workflow-run identity and is not fabricated for this independent API.

Actual PostgreSQL acceptance PASS:

- Empty database → current head.
- Exact Git archive `594be84cfc471af4c12f28600b22cffb66f830f7` → verified0009 with no J tables → current0010.
- Full domain table/column/constraint/index/trigger/function catalogs equivalent.
- Both empty paths downgrade to0009 and re-upgrade equivalently.
- Independently retained published J policy, J pin and J result each refuse downgrade transactionally; head/schema remain unchanged until explicit archive/export.
- Historical H/I migration regression tests retain all original assertions and accept actual graph descendants through the existing lineage helper.

Focused evidence: `artifacts/phase1j-migration-immutable-focused.log`, `artifacts/phase1j-migrations-final-focused.log`, `artifacts/phase1j-migrations/phase1j_migration_dual_path.json`. J schema gate:36/36 PASS. Closure evidence was generated in `artifacts/phase1j-b-closure/`; final remote evidence is uploaded by the existing mandatory runtime CI job.
