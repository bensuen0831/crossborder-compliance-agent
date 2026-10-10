# M2-E main integration closure

M2-E MAIN INTEGRATION = PASS. Blockers: NONE. STAGE1 FULL E2E ENTRY = ALLOWED. Stage 2 = NOT STARTED.

- Previous verified main: `0f5a40c5ca3a8771624fb38e9380856d79e67342`
- PR #27 tested head: `291d52fef7d94fe2462942a910c594dff09c98b0`
- Normal merge / final tested main: `df3a10923734495d728981f4f319b66afadf8c71`
- Merge parents: `0f5a40c5ca3a8771624fb38e9380856d79e67342`, `291d52fef7d94fe2462942a910c594dff09c98b0`
- Annotated tag: `v3.7-m2e-pass`; tag object `c92daef5b47136fb14e2782c737927176d45086a`; local and remote dereference `df3a10923734495d728981f4f319b66afadf8c71`
- Evidence branch: `evidence/m2e-main-closure-df3a109` (evidence commit descends directly from tested main and does not advance product main).

| Exact-main gate | Measured result |
|---|---|
| Full PostgreSQL backend | 910 PASS; 0 failed/errors/skipped/deselected |
| Architecture | 307/307 PASS |
| PostgreSQL/LangGraph runtime | 25/25 PASS |
| Frontend | 135 PASS |
| typecheck / lint / build / i18n | PASS |
| Browser | 60/60 PASS; 0 retries |
| Browser matrix | Phase1KB 6; M2-E/D/C/B/A/M1 three each; M0 36 |
| Locales | zh-CN / zh-HK / en-US PASS |
| Alembic | `0018_phase1h_multijurisdiction_classification_identity`; unique head |
| Migration | fresh→0018; exact previous-main0016→0017→0018; schema equivalence; legacy rows/digest; safe downgrade/re-upgrade; unsafe multi-jurisdiction transactional refusal PASS |

## Exact-main CI

| Workflow | Actual main run | Runner checkout |
|---|---|---|
| M2E External Agent API Gateway | [38040012494](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040012494) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| Phase1KB Multi-provider LLM Governance | [38040015931](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040015931) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| phase1a-runtime-smoke | [38040019858](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040019858) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| M2D Governed Human Review | [38040023168](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040023168) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| M2C Formal Result Workspace | [38040026447](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040026447) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| M2B Production Document Integration | [38040030358](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040030358) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| M2A Production Intake | [38040033976](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040033976) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| M1 Intake Analysis Alpha | [38040036974](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040036974) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |
| M0 Knowledge & Evidence Preview | [38040040447](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/38040040447) SUCCESS | `df3a10923734495d728981f4f319b66afadf8c71` |

All nine runs are actual `workflow_dispatch` on main. All 13 jobs have checkout-log proof for the final tested main SHA. Native M2E and Phase1KB measurements independently assert expected SHA == checkout SHA == final SHA. Full JUnit cases and zero-skip summaries were independently verified. PR evidence is historical only.

## Formal contracts and regressions

Authentication, scopes/project binding, external HTTP API, async delivery, SSE/WebSocket parity and reconnect, governed webhook delivery and bounded failure, cross-tenant/client refusal, actor authority, CAS/idempotency, rate/quota/audit, external-only OpenAPI, Python SDK and TypeScript SDK PASS. SDK generation is reproducible and does not modify committed contracts; Python wheel build and TypeScript compilation/tests PASS. UI/API formal parity compares all owning fields through Stage1ResultService using canonical intake/document/context/snapshot inputs.

R1 frozen classification identity remains tenant × project × snapshot × subject × jurisdiction × scheme version. Single ACTIVE Scheme, governed jurisdiction bindings, atomic A/B rule/binding pin closure, explicit jurisdiction execution, same-jurisdiction applicability isolation, historical exact-pin replay and 0018 uniqueness/refusal PASS. Frozen0001–0016 bytes and original0017 bytes are independently verified.

Canonical ReviewTask and append-only ReviewDecision remain authoritative. Same-Snapshot approval resumes through the owning stage; REQUEST_CHANGES does not advance workflow. Input corrections produce successor Snapshot/WorkflowRun, preserving old Snapshot/result/document/parse pins. Durable restart, CAS, idempotency and actor/current-role authorization PASS. M2-B stable identity, versioned immutable formal state and version-scoped provenance PASS. Phase1KB local protocol multi-provider, secret-boundary, model/prompt pinning and formal-owner separation regressions PASS. Detailed test identities and native real-HTTP measurements are retained in JSON and hashed raw evidence.

## Retained boundaries

- MULTI_SUBJECT_WORKFLOW_NOT_CONFIGURED
- HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED
- unsupported correction targets
- legacy authority read-only
- partial-rerun optimizer not implemented

## Evidence limitations

- Native strict measurement and actual job logs; M2E workflow does not upload raw Playwright matrix files; legacy workflows supply independent raw matrices for their scopes.
- Independent local migration supplement: 3 PASS on PostgreSQL17.11 using temporary databases; required exact-main GitHub Actions uses fresh PostgreSQL16 services.
- Paid Internet LLM = NOT EXECUTED; provider protocol tests use local HTTP fixtures.
- Supplemental contract/static subset: 488 PASS, 7 skipped, 415 deselected, disclosed separately; complete PostgreSQL suite has zero skipped/deselected.
- Exact-main validation executed in fresh isolated GitHub Actions PostgreSQL/Redis runners; no PR-head or ephemeral merge-ref evidence substitutes for main.
- Pre-existing untracked Phase1H closure document was temporarily preserved outside the strict source audit with verified digest and is restored after publication; it is excluded from product and closure evidence commits.
- No Stage1 Full E2E coding or Stage2 implementation started.

No production source was modified during main closure. Product main remains the tested merge SHA; closure documentation is stored on the independent evidence branch. Next Stage1 Full E2E task must start from this exact SHA + annotated tag and requires its own prompt. This task stops without starting that code or Stage2.
