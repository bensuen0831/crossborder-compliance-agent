# Stage1-E2E-R2-R2 — Historical FormalDecision compatibility

Validation in progress. Recovery PASS and Full Stage1 E2E closure are not yet claimed.

Formal main remains `df3a10923734495d728981f4f319b66afadf8c71` / `v3.7-m2e-pass`.
Work continues on `milestone-stage1-full-e2e`, Draft PR #28. No merge, release tag
or main update is authorized. Earlier R2 prototypes and blocker evidence remain
preserved. The existing Phase1H user file remains untouched.

## Frozen version contract

`FORMAL_DECISION_V2` faithfully reproduces the original support-merging semantics
at source `4c79243bbfa22108f1005c8e92265e2137012d4d`. It is available only to the
historical verifier. `FORMAL_DECISION_V2_1` materializes supports once and is the
sole version for new Execute/Save. Contract version remains 2.0 and generated
read schemas accept both engine labels.

The calculation owner is shared. Its five original legal calculation bodies and
input classes are preserved, checked by normalized AST comparison. The only
legacy-specific calculation is the frozen support merger. Immutable typed
strategies are explicitly passed; there is no global mutation, monkeypatch,
environment switch, duplicated legal rule engine or caller-selected version.

## Verification and chain protection

The owning reader authorizes the tenant/project/actor/Snapshot, checks agreement
among the persisted row, result JSON, JSON provenance and persisted provenance,
resolves exact authorized historical inputs/pins, dispatches by the saved version,
and compares the complete original `result_digest`. Unknown versions, tampering
and mixed-version parents are rejected. There is no fallback after failed digest
verification, status-only comparison, support omission or stored-result rewrite.

New execution always selects V2_1. The Snapshot-level legacy check runs in prepare
and again inside the existing serialized save transaction. Different request keys
or result IDs cannot create a competing new chain on a Snapshot with legacy
authority. Existing idempotency/uniqueness and immutable authority remain intact.

## Migration

`0020_stage1_formal_decision_engine_compatibility` has parent
`0019_stage1_candidate_governance`. It changes only engine-version CHECK constraints
on the five existing decision tables, allowing exactly V2 and V2_1 with contract
2.0. It does not alter rows, JSON, pins, IDs or input digests. Downgrade checks all
tables first and refuses if any V2_1 authority exists.

Focused migration measurement: 2 PASS — fresh, exact 0019 upgrade, schema
equivalence, genuine old-source V2 preservation, empty/legacy-safe downgrade,
re-upgrade, V2_1-data refusal, frozen 0001–0019 and single head.

## Preliminary measured evidence

- Pure regression: 62 PASS.
- Version/historical/new pipeline probe: 6 PASS.
- Historical/new/four-outcome/negative probe: 13 PASS.
- Actual records saved before the repair: 15/15 recovered historical reads;
  previously failing cases 12/12 recovered, no reseed or rewrite.
- Frontend preliminary: 141 PASS; typecheck/lint/build PASS.

These runs are preliminary working-tree measurements, not final exact-head
closure evidence. Full regression, runtime and browser measurements will be
recorded after source and finite Git-blob ownership evidence are sealed.

The business/knowledge fixtures are **SYNTHETIC_GOVERNED_TEST_DATA**. These checks
demonstrate engine compatibility and provenance preservation, not independent
Real Regulatory Knowledge Acceptance or Production Legal Accuracy.
Paid Internet LLM = NOT EXECUTED.

## Remaining scope

Full Stage1 E2E Web/API normalization, complete business browser matrix and other
unfinished R2 acceptance remain separate pending coverage. Existing 65-browser
regression coverage is retained. Recovery PASS does not imply PR/main closure.

STAGE1 FULL E2E PR CLOSURE = PENDING

STAGE1 FULL E2E MAIN INTEGRATION = PENDING

Stage 2 = NOT STARTED
