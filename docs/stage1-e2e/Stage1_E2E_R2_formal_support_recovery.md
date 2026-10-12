# Stage1 E2E R2-R1 — Formal LegalSupport recovery

**HIGH_REASONING_ESCALATION_REQUIRED — FORMAL SUPPORT RECOVERY = BLOCKED**.

The approved one-line repair works for new computations. However, the required
historical replay gate fails. Recovery authorization §10 requires stopping when
the repair exposes a need to change the formal owner contract. No historical
reader, DTO, policy, selection algorithm, engine-version contract or migration
has been changed to bypass that failure.

## Identity and retained work

- Formal main: `df3a10923734495d728981f4f319b66afadf8c71`.
- Tag: `v3.7-m2e-pass`.
- Branch / Draft PR: `milestone-stage1-full-e2e` / #28.
- Original failing source / current committed head:
  `4c79243bbfa22108f1005c8e92265e2137012d4d`.
- Fixed commit SHA: **not created**. The authorized repair remains an uncommitted
  one-line patch. Original and fixed file SHA256 values are in the JSON evidence.
- Branch Alembic head: `0019_stage1_candidate_governance`.
- 0001–0018 byte identity: PASS; no migration changes or new migration.

The pre-existing R2 prototypes, fixtures, blocker evidence and user-owned Phase1H
closure file were preserved. Before changing the helper, tracked changes and all
untracked files were backed up outside the checkout. No reset, clean, bulk checkout,
commit, push, merge, tag or main modification occurred during this recovery.

## Exact approved correction

```diff
 def merge_support(supports):
+    supports = tuple(supports)
     return LegalSupport(
```

The current owner file equals the original Git blob with exactly that insertion.
The LegalSupport schema, unique sorting/deduplication, rules, Risk Policy,
Recommendation Policy and FinalPath selection algorithm are unchanged.

## Measured focused results

| Gate | Measured result |
| --- | --- |
| Original tuple / generator | PASS / FAIL, retained prior evidence |
| Updated tuple/list/iterator/generator | PASS |
| Complete actual union of all 12 fields | PASS |
| Two/three sources, overlap, empty and sparse inputs | PASS |
| Determinism, deduplication, no invented refs, immutable inputs | PASS |
| Focused unit + Phase1J + M2C + four business cases | 132 PASS |
| Additional exact-support PostgreSQL pipeline tests | 2 PASS |
| Portable prior-source historical replay regression | **1 FAIL** |

The 132-test run includes 22 dedicated merge-support unit tests. There were no
skips, deselections or xfail. The additional PostgreSQL tests check every support
field against the actual canonical upstream union, exact Snapshot/Subject/pins
and repeated persisted reads. Legitimately absent sources stay absent: a
scenario without matched rule hits is not required to fabricate RuleHit refs.

All four original blank-project business cases now pass their focused assertions:

- DIRECT_TRANSFER_ALLOWED
- CONDITIONAL_TRANSFER_ALLOWED
- TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED
- REVIEW_REQUIRED, with canonical ReviewTask and no fabricated downstream result.

The three terminal cases retain LegalBasis, Evidence, RuleHit, knowledge-version,
citation and fact provenance along Obligation → CandidatePath → Risk →
Recommendation → FinalPath. Exact parent relationships, current context version,
real flow and jurisdiction isolation remain checked.

These cases use **SYNTHETIC_GOVERNED_TEST_DATA** with real PostgreSQL, HTTP, DOCX,
runtime and governed publication. Their PASS proves source propagation in that
fixture universe. It does not independently prove Real Regulatory Knowledge
Acceptance or Production Legal Accuracy. Paid Internet LLM = NOT EXECUTED.

## New historical counterexample

The canonical reader, `decision_repository.read()`, reconstructs authorized
inputs and parents, calls the **current** `calculate()` implementation and requires
`result_digest(saved) == result_digest(current)`.

Both historical and corrected results declare the same
`engine_version = FORMAL_DECISION_V2`. The current DTO literal and PostgreSQL
check constraint require that value. There is no separately recorded merge-support
computation/verification revision to select the original semantics on replay.

The earlier R2 diagnostic produced genuine persisted results before this repair.
Using exactly the same rows, actor, tenant/project authorization and pinned inputs:

| Read algorithm | Result |
| --- | --- |
| Authenticated original Git helper at `4c79243…` | **15/15 PASS** |
| Corrected current helper | **3 PASS / 12 FAIL** |

Obligation reads pass. CandidatePath, Risk, Recommendation and FinalPath reads
fail for each of the three historical terminal cases with:

```text
ValueError: saved decision no longer revalidates
```

All fifteen stored result JSON digests remain unchanged. The comparison only
read persisted data; it did not rewrite history or backfill missing support.
The old Git helper was loaded in an isolated diagnostic process solely to prove
the prior algorithm still validates the same authorized rows. It is not a
production fallback.

A portable regression in `tests/test_stage1_support_historical.py` reproduces the
same failure without depending on those private database IDs. It creates history
through the real canonical PostgreSQL owners executing the authenticated prior
Git helper, restores the current helper, and requires the saved result to remain
readable. The ordinary assertion fails; no skip or xfail conceals it.

Detailed identities and read results are recorded in
`evidence/stage1-full-e2e/r2/formal_support_historical_replay_blocker.json`.

## Minimum compliant architecture decision

An additional bounded historical verification strategy is required. It must
preserve immutable old results, current tenant/project/evidence/pin authorization
and complete digest verification; it cannot simply accept stored JSON or omit
the digest check.

Possible bounded options for separate approval:

1. Define an explicit auditable computation/verification revision contract.
   Historical authority selects the authenticated original revision; newly
   confirmed analysis selects the corrected revision. First determine whether
   existing canonical pins/provenance can express the identity without a new
   schema or mutation of historical Snapshots.
2. Authorize a strict historical verifier in the existing owning reader with
   an explicit, auditable eligibility rule and full original-algorithm digest
   comparison. Current computations continue using the corrected helper. A
   blanket fallback, unconditional stored-result acceptance or weakened checks
   is not an acceptable compatibility policy.

Neither option is included in the current one-line authorization. No reader
repair or schema proposal is implemented here. Whether the chosen compatibility
contract requires a migration is **NOT YET PROVEN**. If it does, 0020 requires
separate architecture approval; 0019 remains the sole head meanwhile.

## Remaining gates and decision

The full Backend/Architecture/Runtime/Frontend/Browser/migration matrix and new
exact-head CI were not run after the historical stop gate. The earlier R1.1
945/331/25/141/65 floors and 10/10 remote CI remain historical evidence and are
not reused as validation of this patch. No fixed commit SHA or recovery PASS is
claimed.

STAGE1-E2E-R2 FORMAL SUPPORT RECOVERY = BLOCKED

STAGE1 FULL E2E RESUME = BLOCKED

STAGE1 FULL E2E PR CLOSURE = PENDING

STAGE1 FULL E2E MAIN INTEGRATION = PENDING

Stage 2 = NOT STARTED
