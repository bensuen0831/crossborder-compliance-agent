# Stage1 Full Business E2E — D0 blocked result

**HIGH_REASONING_ESCALATION_REQUIRED — STAGE1 FULL E2E = BLOCKED**

Reason: `PRECONFIRMATION_CANDIDATE_AUTHORIZATION_CONTRACT_MISSING`.
Branch: `milestone-stage1-full-e2e`.
Source examined: `df3a10923734495d728981f4f319b66afadf8c71`.
Start gate: PASS. Annotated `v3.7-m2e-pass` still dereferences this source.
Alembic: `0018_phase1h_multijurisdiction_classification_identity`, single head.
No product source, assertions, migrations, architecture rules or workflow was
changed. No Draft PR was created: the escalation occurred at D0, before initial
acceptance implementation. Main integration remains PENDING.

## Exact counterexample

The diagnostic used a genuinely blank, newly created project, PostgreSQL
17.11, real TCP FastAPI HTTP, genuine binary DOCX, and a protocol-realistic
loopback HTTP provider. Provider, model, usage policy, invocation policy,
candidate fact type and purpose-bound prompt went through the existing
publication owners with independent approval. The request actor was a canonical
user context with `system=False`. The test reused existing foundation helpers
for tenant configuration; their historical project/results were not used as
this project's business input or result. This is a D0 diagnostic, not completed
least-privilege business acceptance.

| Step | Measured behavior |
| --- | --- |
| Create blank project | HTTP 201; DRAFT, no Snapshot, zero formal BusinessFacts |
| Enter structured facts | Real HTTP update; distinct source/destination jurisdictions |
| Upload genuine DOCX | HTTP 201; unique project marker in actual DOCX paragraph |
| Parse draft document | HTTP 200; quality PASS; semantic HTTP invocations: 0 |
| Authorize an unpinned draft invocation | Existing configuration owner denies RESOURCE_NOT_FOUND |
| Confirm input | HTTP 200; request contains only expected_version; user confirmation precedes extraction |
| Semantic extraction inside confirmation | Actual governed local HTTP invocation: 1; DERIVED_CANDIDATE source-addressed output |
| Formalization in the same confirmation | Candidate resolution ACCEPTED by POLICY; BusinessFact VALIDATED |
| Candidate preview/confirmation after output | None; no intervening user action exists |

Concrete recorded identities:

- Project: `712fac00-b101-48e7-8b88-14db9e686cea`
- Snapshot: `5ff0a34b-04a2-5722-af24-d2ddb55d9af6`
- Workflow run: `7b10264a-df54-5d36-9664-15b1e2da50b4`
- Document version: `11b26c5d-752a-4177-a440-7e84dd28fb59`
- Native ParseRun: `e30969b8-3e8d-47a6-b0ab-b64836cbe700`
- Semantic ParseRun: `04b7a03f-9c81-405d-9ec0-04d794482e36`
- Candidate: `c58c33e7-7103-41f3-b659-76a8be4703ef`
- Formal BusinessFact: `b8146e35-23b1-4599-8a9c-1cd7531c505b`
- SourceTrace: `c90c8350-7b64-4141-9e40-a26174fac5ee`

The persisted SourceTrace's document version and semantic ParseRun were
independently reread and matched the formal fact's canonical candidate
resolution. Its resolution is POLICY, not a recorded human confirmation.
The DOCX is therefore not merely an attachment, but the *new* explicit
candidate-confirmation acceptance requirement is not satisfied.

This counterexample does not establish an LLM-owned legal result, a migration
defect, or an M2-E baseline regression. It establishes that the existing
confirmation-time enhancement contract does not provide the newly requested
`LLM output → Candidate → user confirmation → Formal Input` order.

## Affected owners and frozen invariants

1. `infrastructure/intake_composition.py:69`: freeze model configuration,
   produce document candidates, pin documents, then run context resolution
   inside the same confirmation operation.
2. `infrastructure/llm_document_inputs.py:99`: PinnedDocumentInput requires
   CONFIRMED/SUPERSEDED ProjectVersion plus exact AnalysisSnapshot/ParseRun pins.
   Eligible-model draft catalog mode is a projection, not a substitute
   invocation/pin authority.
3. `application/context_services.py:123`: eligible non-conflicting document
   facts are accepted by POLICY during normalization. There is no earlier
   user-selected candidate-confirmation transition in this path.
4. `infrastructure/persistence/project_intake.py:256`: the existing formal
   Snapshot is constructed during confirmation. It must not be fabricated
   earlier merely to satisfy the gateway's reference checks.

Preserve Candidate != Formal Input until explicit user confirmation; exact
governed model/policy/prompt/input pins; immutable historical Snapshot; single
canonical ReviewTask/ReviewDecision authority; single runtime/checkpointer.
Changing a fixture's confidence, directly inserting candidates/formal facts,
using draft catalog mode for an unpinned invocation, or inventing a temporary
confirmed Snapshot would not close this acceptance gap compliantly.

## Minimum compliant options for an explicit contract decision

- Extend the **existing canonical draft/input owners** with a durable,
  version-addressed preview authorization/configuration context. First prove
  whether existing ProjectVersion/candidate identities and schema can carry
  exact model/prompt/policy/document pins, CAS and user accept/reject history.
  Seal final formal input and the analysis Snapshot only after candidate
  confirmation. Keep the existing LLM gateway and formal result authorities.
- If that closure cannot be represented in 0018, document the precise missing
  identity and historical impact and seek separate approval for its minimum
  schema change. Do not create 0019 under this task's default authorization.

These are design options, not implemented changes or an assertion that a new
database migration is necessarily required. The current contract needs a
pre-confirmation identity/authorization decision before acceptance coding can
continue; D0 cannot replace that decision with test orchestration.

The inventory separately found omitted typed DataFlow persistence: Web draft
flow rows are not submitted by `draftFacts`, and intake confirmation does not
provide the existing resolver's item/edge bindings. This is not proof of a new
DataFlow table requirement. It needs canonical input wiring, not fixture
inserts or a second flow store. The diagnostic's document did not request
flow extraction; its zero flow counts must not be misreported as a failing
submitted-flow test.

## Scope and evidence limits

Full backend, architecture, runtime, frontend, existing browser, new 4x3
browser matrix, normalized Web/API business parity and dedicated exact-head
CI were **NOT EXECUTED** in this D0 stop. The 910/307/25/135/60 baseline counts
remain historical baseline evidence only. No new PR tested SHA exists. No
browser retry measurement is claimed. Paid Internet LLM: **NOT EXECUTED**.

The diagnostic script required dependency installation and local PostgreSQL/
Redis startup. Its development corrected two diagnostic-only errors (health
probe response handling and SourceTrace location on CandidateResolution rather
than BusinessFact). The final successful diagnostic is one fresh, unique
project execution. Those edits did not alter product assertions, provider
policies, browser retry behavior or existing tests, and are not assertion
retries of an acceptance suite.

Reproduction in this configured cloud checkout:

```bash
source /workspace/compliance-tools/runtime.sh
export PYTHONPATH="$PWD/src:$PWD:$PWD/tests"
python evidence/stage1-full-e2e/candidate_boundary_probe.py
```

The diagnostic intentionally refuses to run on a source SHA different from
the verified baseline. It provisions isolated tenant/project fixtures and
writes sanitized output under `/workspace/stage1-e2e-control`. No secret-store
key, credential, token, or raw provider payload is in the archived evidence.

Archive:

- `evidence/stage1-full-e2e/start_gate.json`
- `evidence/stage1-full-e2e/candidate_confirmation_counterexample.json`
- `evidence/stage1-full-e2e/candidate_boundary_probe.py`
- `evidence/stage1-full-e2e/final_pr_validation.json` with source/evidence hashes

**STAGE1 FULL E2E PR CLOSURE = BLOCKED**

**STAGE1 FULL E2E MAIN INTEGRATION = PENDING**

Stage 2 = NOT STARTED. No merge, tag, next milestone or Stage 2 work was done.
