# Stage1 Full Business E2E — main integration and release closure

STAGE1 MAIN INTEGRATION = PASS
STAGE1 FULL BUSINESS E2E = PASS
STAGE1 RELEASE CLOSURE = PASS

Acceptance is **L1 SYNTHETIC_GOVERNED technical/business E2E only**.
PR #28 was authorized directly by the user and merged through normal GitHub
merge commit. Previous main: `df3a10923734495d728981f4f319b66afadf8c71`. Validated PR head: `25b2cb34be24578c74ea7ed4931f9534ff0289f3`.
Final tested merged main: `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`. Parents: `df3a10923734495d728981f4f319b66afadf8c71`, `25b2cb34be24578c74ea7ed4931f9534ff0289f3`.
Merge time (Asia/Shanghai): 2026-10-13T14:38:46+08:00 (UTC audit timestamp: 2026-10-13T06:38:46Z).
Main and PR tree identities are equal;
the independent PR evidence commit `26ea43f4f2408183085f1062b69597099d51bfcf` was not merged into main.

| Gate | Measured result |
|---|---|
| Backend | 1012 PASS; failed/errors/skipped/deselected = 0 |
| Architecture | 361/361 PASS across nine existing authorities |
| Runtime | 25/25 PASS; genuine PostgreSQL durable checkpoints and process restart |
| Frontend | 142 PASS; typecheck/lint/build/i18n PASS |
| Browser | 77/77 PASS; retained 65 plus 12 business/locale journeys; retries 0 |
| Four formal outcomes | 4/4 PASS |
| Three-locale matrix | 12/12 PASS; zh-CN, zh-HK, en-US |
| Main CI | 11/11 workflow_dispatch SUCCESS; 18/18 actual job checkout proofs |
| Historical original V2 | 15/15 reads; 12/12 original failures recovered; complete digests unchanged |
| Migration | 0020 sole head; fresh/exact0019 upgrade/equivalence/safe downgrade/re-upgrade/refusal PASS |
| Frozen migrations | 0001–0019 byte-identical |

All measurements were rerun on exact merged main. The saved original V2 rows
were read from their existing PostgreSQL database, without reseeding or rewriting.
New V2_1 executions preserve the authorized LegalSupport union; incompatible
version chains fail closed. Candidate preparation precedes explicit user consent;
confirmation does not generate unseen LLM candidates. Genuine DOCX contributes
traceable formal input; actual flow nodes/edges/item links remain persisted.
Governed local HTTP LLM and pinned RAG evidence are exercised without treating
model content as legal authority. All four Web/API normalized semantics match,
including actual Python/TypeScript SDK HTTP business smoke. Owning-stage review
resume and successor analysis preserve historical snapshots/results/pins.
RequiredDocument does not enable generation; Stage 2 remains NOT STARTED.

Full backend and browser test IDs exactly retain the PR closure IDs. The retained
supplementary non-runtime contract subset reports 535 PASS / 7 skipped / 470
deselected; it is explicitly not full PostgreSQL backend evidence. The complete
1012-test PostgreSQL suite has zero skips/deselections. Per-job counters and actual
checkout proofs are archived in `exact_main_ci_references.json`.

The first additional local browser execution used a historic database binding
in its synchronous normalizer while its HTTP backend used the new database.
It failed three DIRECT normalizations (nine unexecuted cases were recorded when
it was stopped). This environment error, actual rule-hit identity counterexample,
and corrected database preflight are retained in `local_environment_recovery.json`.
The full clean matrix was rerun on a fresh matching database with all assertions,
timeouts and browser retries=0 unchanged. It is separate from the mandatory
exact-main remote CI, which uses its own matched database bindings.

Annotated release tag: `v3.7-stage1-e2e-pass`. Tag object: `3144c1d2400cd228305348a6a315acedd5857cdb`;
dereferenced target: `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`. Source/test/fixture identities comprise 647 exact
committed Git-blob SHA256 entries. Closure files and sanitized measurements are
archived separately on `evidence/stage1-main-closure-060cbb5`, descending from
the tested main; that evidence commit is not the product release commit.
No production source changed after merge, and storing evidence did not advance main.

Paid Internet LLM = NOT EXECUTED.
Real Regulatory Knowledge acceptance = NOT EXECUTED.
Production Business UAT = NOT EXECUTED.
This release proves L1 synthetic platform acceptance, not actual national-law
accuracy or commercial readiness. Retained capability boundaries remain in force.
These include MULTI_SUBJECT_WORKFLOW_NOT_CONFIGURED,
HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED, unsupported correction targets,
legacy authority read-only, and no partial-rerun optimizer. They are retained scope
boundaries, not release blockers, and were not expanded during integration.
Only available specification text was reviewed; the baseline supplied Master/Phase0
copies contain historical truncation markers. No Stage 2 work was started.

Blockers: NONE. Main CI references:
- [Stage1 Full Business E2E Acceptance / 38358002892](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38358002892) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [Stage1 R1 Candidate Governance Recovery / 38357996775](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357996775) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [Phase1KB Multi-provider LLM Governance / 38357990932](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357990932) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [phase1a-runtime-smoke / 38357986507](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357986507) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2D Governed Human Review / 38357976869](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357976869) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2C Formal Result Workspace / 38357971959](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357971959) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2B Production Document Integration / 38357967430](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357967430) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2A Production Intake / 38357961602](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357961602) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M1 Intake Analysis Alpha / 38357956862](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357956862) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M0 Knowledge & Evidence Preview / 38357952092](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38357952092) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`
- [M2E External Agent API Gateway / 38380317555](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38380317555) — actual checkout `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`

## Timeout recovery selection

Path A completed one unchanged M2-E execution, run 38380317555, and revalidated the original ten same-main SUCCESS workflows. The original cancelled run 38357981677 and blocked evidence commit `e2d7c5f82930e6161b0bc2596d5e5d7b6ff2f3b9` remain immutable historical evidence. No CI-only PR or source/timeout change was needed. See `Stage1_E2E_main_timeout_recovery.md` and `timeout_recovery.json`.

## Independent archive identity

Immutable closure payload commit: `136f4577d46490e443046b4317bba7c61ca29f7b` (parent: tested main `060cbb5a20a9f8f70fa88dbefb8b5feb404c460d`). The subsequent evidence-only archival seal records that payload identity and digests; neither evidence commit is the product baseline.
