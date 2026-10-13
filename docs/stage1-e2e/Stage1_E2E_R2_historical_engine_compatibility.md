# Stage1-E2E-R2-R2 — Historical FormalDecision compatibility

STAGE1-E2E-R2 HISTORICAL FORMAL DECISION COMPATIBILITY = PASS.
Stage1 Full E2E PR/main closure remains PENDING.

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

Full-suite migration measurement: 2 PASS — fresh, exact 0019 upgrade, schema
equivalence, genuine old-source V2 preservation, empty/legacy-safe downgrade,
re-upgrade, V2_1-data refusal, frozen 0001–0019 and single head.

## Measured evidence and source identity

Final backend regression completed at `01e801803a0bf573ae232145d4cc10ef8fcead61`.
The finite committed-source owner proof points to
`21c4df5332de6d68aee22c8b8260e7e5a4ab2fba`; all authenticated source blobs match.
The original engine hash at both formal main and `4c79243...` is
`234d7194d2558b62882304d4c40fe1f575fa8572a69340d84fcb24c2e07e8a38`.
The corrected engine hash is
`a2085b4abcdae5b39a90e4a01a7a6dfdb248b355043900248eadb1e5104a7691`.

- Pure regression: 62 PASS.
- Version/historical/new pipeline probe: 6 PASS.
- Historical/new/four-outcome/negative probe: 13 PASS.
- Actual records saved before the repair: 15/15 recovered historical reads;
  previously failing cases 12/12 recovered, no reseed or rewrite.
- Final-head original persisted records: 15/15 read PASS, including all 12
  formerly failing records; every persisted column remains unchanged.
- Runtime: 25/25 PASS on the new head, using fresh PostgreSQL and a real durable
  LangGraph checkpoint across separate processes.
- Frontend: 141 PASS; typecheck/lint/build/i18n PASS.
- Existing browser regression: 65/65 PASS, zero retries: core 24, candidate
  consent 5, M0 36. All three locales remain covered.
- Updated finite owner regression: 18 PASS, retaining the original tampering
  negatives and requiring unchanged legal calculation bodies.
- Full PostgreSQL backend: **991 PASS**, 0 failed/errors/skipped/deselected,
  1,734.79 seconds. The previous 945 tests remain; 46 new tests are additive.
- Architecture: **339/339 PASS**, retaining the original 331 and adding 8.
- Pure merger: 22 PASS within the full suite, exercising every LegalSupport
  field with tuple/list/iterator/generator, empty/multiple inputs and deduplication.
- New four-outcome PostgreSQL/HTTP/DOCX cases: **4/4 PASS** — Direct,
  Conditional, Localization/Prohibition and Review Required. New saved J rows
  and their envelopes/provenance all use V2_1.
- Frozen migrations: **0001–0019 byte-identical**; sole Alembic head is 0020.
- Full existing R1, M2-A/B/C/D/E, Phase1K-B, Phase1J and historical replay
  regressions remain included, without skip/deselection.

Frontend/browser ran at `dfd2d5df16e1054a35e16b7295ebb9467ee3db54`.
The later change consists only of two retained ownership tests, their finite
path list and the committed-source proof. `git diff` confirms that `src/`,
`frontend/`, `alembic/` and `sdk/` are byte-identical between the two heads.
These measurements are not presented as tests checking out a different SHA.
The only cross-head difference above is test/ownership proof metadata; all
tested production inputs are byte-identical. Backend/runtime and historical
record reads use the stated final backend source SHA.

Machine-readable evidence is
[`historical_engine_compatibility.json`](../../evidence/stage1-full-e2e/r2/historical_engine_compatibility.json).
The measured archive is `evidence/stage1-full-e2e/r2/historical-compatibility-measured/`,
with 28 SHA-256 digests. JUnit is archived with test identity/timing/outcome only;
provider/document stdout and stderr are excluded. Original JUnit's digest is
retained. Browser summaries retain zero-retry results without raw HTTP payloads.

The original 12 failures remain in the historical escalation evidence. The final
read archive contains all 15 original result IDs, their complete original digest,
recovered read outcome and unchanged-row proof. Migration preservation cases
using isolated old-source owners are separately identified and do not replace
those original records.

Remote CI references in JSON are for the tested source SHA. CI completion is
tracked separately; they do not represent Full Stage1 E2E PR closure. A subsequent
evidence-only commit does not change tested production source.

## Retained interrupted-run evidence

The first full gate used a database that already had durable checkpoint tables
and was rejected by the required fresh-schema preflight. Subsequent fresh runs
exposed historical ownership assertions that banned any decision-engine
successor, despite the explicit compatibility authorization. Those incomplete
runs were stopped, retained as diagnostics and never counted as full PASS.
The last interrupted run had 228 passing tests and one ownership failure.

The owner tests now require the approved committed blob digest and unchanged
normalized AST of all five legal calculation bodies and all input classes.
The live-engine tampering negative remains present. No test is deleted,
deselected, skipped, marked xfail or changed to allow arbitrary engine edits.
The full gate is restarted from a new empty PostgreSQL database.

The business/knowledge fixtures are **SYNTHETIC_GOVERNED_TEST_DATA**. These checks
demonstrate engine compatibility and provenance preservation, not independent
Real Regulatory Knowledge Acceptance or Production Legal Accuracy.
Paid Internet LLM = NOT EXECUTED.

## Remaining scope

Full Stage1 E2E Web/API normalization, complete business browser matrix and other
unfinished R2 acceptance remain separate pending coverage. Existing 65-browser
regression coverage is retained. Recovery PASS does not imply PR/main closure.

Recovery blockers: NONE.

Legacy V2 Read = PASS.
Corrected V2_1 Execution = PASS.
Historical Digest Integrity = PASS.
LegalSupport Completeness = PASS.
Mixed-version Protection = PASS.
Relevant Regression = PASS.
Full Regression = PASS.

STAGE1 FULL E2E RESUME = ALLOWED, for a subsequent task.

STAGE1 FULL E2E PR CLOSURE = PENDING

STAGE1 FULL E2E MAIN INTEGRATION = PENDING

Stage 2 = NOT STARTED
