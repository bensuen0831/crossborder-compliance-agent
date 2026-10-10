# M2-E-R1.1 owning-contract recovery

Recovery gate: **PASS**. M2-E closure remains paused.

## Identity and migration

The approved Phase1H formal identity is tenant × project × snapshot × subject × jurisdiction × scheme version. Migration `0018_phase1h_multijurisdiction_classification_identity` follows unchanged `0017_m2e_external_agent_api`, locks `classification_results`, and replaces only `uq_formal_classification_snapshot`. The predicate remains `formal_provenance_json IS NOT NULL`. No result row, ID, provenance or jurisdiction is rewritten. The index remains migration-owned; ORM metadata does not create a duplicate index.

Downgrade checks legacy-key collisions under the same exclusive lock before index mutation. Multi-jurisdiction collisions cause explicit transactional refusal. Safe data restores the legacy index and permits re-upgrade. Real PostgreSQL migration evidence proves fresh/exact0017/schema-equivalence paths, preserved legacy payload/digest, A/B insertion, A2 rejection and refusal preserving schema/data/revision.

## Preserved authority

One ACTIVE Classification Scheme is retained. Governed jurisdiction bindings resolve atomically to complete immutable snapshot binding/scheme/rule pins. Each execution receives one explicit jurisdiction. Applicability consumes only same-jurisdiction classification/rule-hit references. Historical execution reads exact pins; scenario mode does not fabricate classification. Rule scope ⊆ scheme scope, permanent architecture rules, frozen0001–0016 and the saved0017 bytes are unchanged. No frontend or formal decision engine changes.

Legacy RuleHit serialization omits an absent jurisdiction field, preserving historical downstream input digests. New results and hits remain explicitly jurisdiction scoped. Historical owner manifests are preserved; successor exceptions require finite committed source hashes, ancestry and live-byte validation. The M2-D guard independently authenticates R1 and runtime-owner proofs. The K-B migration test uses the existing actual Alembic lineage helper, preserving its downgrade/refusal assertions.

## Empirical evidence

- Preserved original counterexample: one failed same-snapshot/subject/scheme A/B persistence execution before0018; see `evidence/m2e/r11_before_fix.json`.
- Focused migration/owning/isolation:15 PASS; original real HTTP/DOCX data-aware workflow/result and review cases:2 PASS.
- Final historical ownership/migration compatibility:15 PASS.
- Architecture:151 existing +118 existing additive +11 recovery =280 PASS.
- Final full backend: 893 PASS, 0 failures/errors/skips/deselected; runtime25/25 PASS. Earlier891 PASS/2 FAILED attempt is retained as failed evidence, never used as closure.

Final machine-readable measurements, SHA identities, suite counts and artifact digests are recorded in `evidence/m2e/r11_recovery_measured.json`. Paid Internet LLM endpoints and M2-E exact-head CI/browser/SDK/Admin closure are not recovery acceptance claims.

## Stop boundary

This delivery completes only owning-contract recovery. M2-E can resume only after R1 PASS. No merge/tag, M2-E completion, Full Stage1 E2E or Stage2 work is performed.

Validated checkout: `3fc7465c51f23683ab466b485f6e40afb93a709e`. Executable owning source: `6655b6cbe7711b68979ee7862aa70416f432d850`. Later delivery commits contain recovery documents/evidence only.

**M2-E-R1 OWNING-CONTRACT RECOVERY = PASS**

**M2-E RESUME = ALLOWED**

**STAGE1 FULL E2E ENTRY = BLOCKED**

**Stage2 = NOT STARTED**
