# Stage1 E2E R2 — formal support propagation escalation

**HIGH_REASONING_ESCALATION_REQUIRED — STAGE1-E2E-R2 = BLOCKED**.

R2 §17 requires stopping if implementation needs to modify a formal legal owner:
“如發現必須新增 0020 或修改法律正式 owner……提供實證、受影響 owner、最小方案後停止。”
The counterexample below meets that condition. No formal legal owner has been
modified, no 0020 has been created, and no commit/push/merge/tag/main update has
been performed in this R2 continuation.

## Source identity and evidence limits

- Formal main/tag: `df3a10923734495d728981f4f319b66afadf8c71` / `v3.7-m2e-pass`.
- Existing branch/Draft PR: `milestone-stage1-full-e2e` / #28.
- Committed local/PR head: `4c79243bbfa22108f1005c8e92265e2137012d4d`.
- Alembic: `0019_stage1_candidate_governance`; 0001–0018 unchanged.
- R2 edits are uncommitted prototypes. Their local business measurements are
  diagnostic evidence, **not exact-head PR closure evidence**.
- Historical R1 remote verification: ten successful workflows, fifteen actual
  runner checkout proofs at `4c79243…`; these do not validate the new R2 edits.

## Exact affected owner and defect

`src/crossborder_compliance/domain/decision_engine.py:173`, `merge_support()`, is
part of the canonical FormalDecision engine. It iterates `supports` once for
each `LegalSupport` field without materializing a single-pass iterable first.

Existing candidate-path, recommendation and final-path callers supply generator
expressions. Reading the first field, `applicability_result_ids`, exhausts the
generator. The remaining eleven fields become empty: rule hits/versions,
LegalBasis, Evidence, packs, retrieval runs, knowledge versions, structure nodes,
citations/locators and fact references.

The defect exists in the unchanged formal baseline and committed PR head. Their
owner file hashes equal the current file hash, as recorded in the JSON evidence.
This is a stronger-acceptance finding, not a new LLM result or legal capability.

## Measured counterexample

Real PostgreSQL + TCP HTTP + genuine DOCX + canonical Workflow Runtime + governed
synthetic rules/knowledge/publication were used. Direct also invoked an actual
local HTTP LLM provider, prepared candidates before confirmation, explicitly
accepted them, and confirmed with zero additional LLM requests.

| Case | Formal CrossBorderAssessment | Full-chain gate |
| --- | --- | --- |
| A | DIRECT_TRANSFER_ALLOWED | BLOCKED |
| B | CONDITIONAL_TRANSFER_ALLOWED | BLOCKED |
| C | TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED | BLOCKED |

Each blank project produced a Snapshot, two jurisdiction-scoped classifications,
two applicability results, a genuine linked source/destination flow and governed
RAG evidence. Obligation items retained rule hits, LegalBasis and Evidence.
CandidatePath retained applicability references but lost all other support fields.
Risk, Recommendation and FinalPath carried the same incomplete support.
RequiredDocument and aggregate workspace LegalBasis can still show evidence from
other parents, masking the missing per-stage provenance.

The four-case focused full-chain run measured **3 failed / 1 passed**: A/B/C failed
the strict per-stage support assertion; D remained REVIEW_REQUIRED. No assertion
was removed, skipped or marked xfail.

A separate pure owner regression supplies identical support as either a tuple
or a generator: tuple preserves all twelve fields; generator preserves only the
first. `tests/test_stage1_support_merge.py` must pass after an approved repair.

Machine-readable facts, concrete project/Snapshot/Run identities, field counts,
unchanged owner hashes and private result digests are recorded in
`evidence/stage1-full-e2e/r2/formal_support_blocker.json`. Synthetic fixture PASS
does not constitute live official-law acceptance. Paid Internet LLM was not run.

## Minimum compliant options

1. **Recommended; requires separate formal-owner authorization:** materialize
   the bounded upstream iterable once inside the existing helper:

   ```diff
    def merge_support(supports):
   +    supports = tuple(supports)
        return LegalSupport(
   ```

   Preserve all deterministic unions/order, legal status logic, metadata,
   policies, formal schemas and owners. Retain generator/tuple regressions and
   PostgreSQL complete-chain support assertions. Then rerun focused H/I/J and
   formal-result tests, four business cases, Web/API parity, historical
   immutability and every R2 local/exact-head CI gate. Any ownership approval
   proof must use committed Git blobs; do not weaken frozen-owner checks.

2. Keep the owner frozen and leave R2 BLOCKED. Do not substitute aggregate
   workspace evidence, omit per-stage support, fabricate fixture results or add
   channel-specific legal logic to obtain PASS.

**Migration required: NO.** This is iterable handling within the existing owner;
no new schema identity or 0020 is proposed. Existing historical results must not
be rewritten; the proposed fix only affects future computations.

## Retained work and stop boundary

The branch retains reviewable, uncommitted typed-flow input, Context Resolution,
exact flow-subject selection, same-owner item/flow RAG orchestration, UI/generated
contract updates and additive test prototypes. These have not received full
regression or exact-head CI validation. The browser prototype's first smoke
stopped at a fixture control-plane response expectation (200 versus 201), before
its business journey. No 12-case browser PASS or new regression floor is claimed.
The local R2 UAT host was stopped.

Full E2E PR closure = BLOCKED. Main integration = PENDING.
Paid Internet LLM = NOT EXECUTED. Stage 2 = NOT STARTED.
