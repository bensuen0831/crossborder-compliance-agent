# M2-C main integration closure

**M2-C MAIN INTEGRATION = PASS**
**M2-D ENTRY = ALLOWED**
**M2-D IMPLEMENTATION = NOT STARTED**
**Stage 2 = NOT STARTED**

Baseline main: `42571c7148456f41adb64d2528c169a357214a25` / `v3.6-m2b-pass`.
Source: PR #24, branch `milestone-m2c-stage1-results`, tested head `2c3dc003c70829c02e24f4fc56402c306273baa0`.
Normal merge / final tested main: `0dc005e583465a4604a5d40a369cb5fc2f0ccbef`.
Parents: `42571c7148456f41adb64d2528c169a357214a25`, `2c3dc003c70829c02e24f4fc56402c306273baa0`. Source head is in main ancestry and source trees are identical. No squash, rebase, force push or post-merge source changes.

Annotated tag: `v3.6-m2c-pass`; object `fa5c4223fbd230787526d7921cc088b5c7ced042`; target `0dc005e583465a4604a5d40a369cb5fc2f0ccbef`. Remote object type and dereference verified after all gates passed.
Single Alembic head: `0014_m2c_formal_result_authority`, down-revision `0013_m2b_context_temporal_contract`. Frozen migration 0001–0013 Git blobs match the verified baseline.

## Independent exact-main results

Backend **727 PASS**, zero failures/errors/skips/deselections, independently both local PostgreSQL gate and remote full-runtime gate. All 40 M2-C cases executed on main. Nine Phase B–J schema checks PASS. Architecture **221 PASS** =151+13+27+15+15; owning formal-result and projection boundaries preserved. Mandatory PostgreSQL/LangGraph runtime **25/25 PASS**, including durable restart/resume/idempotency/review uniqueness and snapshot/tenant identity.

Frontend **108 PASS**, typecheck/lint/build/i18n PASS; three locales,494 keys per locale,0 missing keys,0 hard-coded UI strings. Real PostgreSQL/backend/Chromium browser matrix: M2-C3,M2-B3,M2-A3,M1 3,M0 36, all PASS,0 retries. M2-C's main workflow also executes B/A/M1 regressions. A separate main-only three-locale browser run additionally opens the original source-evidence drawer, verifies the workspace areas, chooses completion, confirms no API writes/Stage2 execution and re-reads unchanged formal results.

Fresh DB→0014, exact frozen0013→0014, schema equivalence, empty downgrade/re-upgrade, retained governed-authority transactional refusal all PASS. In addition to the governed-policy fixture, a populated real UAT database with3 Cross-border Assessments,3 Document Requirements and352 snapshot registry pins was empirically refused downgrade. Alembic head, row counts and content digests remained unchanged. No claim of destructive rollback support.

Formal cross-border/document owners remain backend authorities. CONDITIONAL_PROPOSAL is not CONDITIONAL_TRANSFER_ALLOWED; transfer/risk/path dimensions remain separate. Document requirement levels remain independent of generation availability. Exact snapshot/context/document/parse/policy reads and S1/S2 isolation are covered by the full PostgreSQL regression suite; no latest fallback introduced by integration.

## Main CI identities

All six runs are newly dispatched on actual main, not PR evidence or ephemeral merge refs. Every job's checkout log was parsed and matched to the exact main. The runtime artifact's tested/runner identities match the same SHA; browser notices/reports are independently verified.

| Workflow | Run | Conclusion | Tested main / runner checkout |
| --- | --- | --- | --- |
| phase1a-runtime-smoke | [37720181111](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37720181111) | SUCCESS | `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` |
| M2C Formal Result Workspace | [37720184257](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37720184257) | SUCCESS | `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` |
| M2B Production Document Integration | [37720186713](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37720186713) | SUCCESS | `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` |
| M2A Production Intake | [37720189198](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37720189198) | SUCCESS | `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` |
| M1 Intake Analysis Alpha | [37720192348](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37720192348) | SUCCESS | `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` |
| M0 Knowledge & Evidence Preview | [37720194701](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37720194701) | SUCCESS | `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` |

## Selection disclosure

The separate static-contract job deliberately selects a subset. Its skips/deselections are disclosed here; they are not full-backend counts. The full local and remote gates execute all727 with0 skips/deselections and no expected-failure exclusions.

```text
contract-tests	Contract/static test subset	2026-10-08T02:56:27.4765291Z 427 passed, 7 skipped, 293 deselected, 2 warnings in 63.62s (0:01:03)
```

## Retained scope and stop

Known scoped capabilities: MULTI_SUBJECT_WORKFLOW_NOT_CONFIGURED and HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED. These remain explicit, tested boundaries and are not cleared or concealed. Blockers: NONE.

No M2-D branch/code/PR, Stage2 generation, Phase1K-B/provider/security redesign, new runtime/checkpointer/registry, unrelated fixes or V3.7 specification rewrite. Existing untracked Phase1H closure file was preserved.

Closure evidence branch `integration/m2c-main-closure-evidence` descends from the tested main and is not merged into main. Main remains `0dc005e583465a4604a5d40a369cb5fc2f0ccbef`; the evidence commit is not the product baseline. Machine-readable record: `evidence/m2c/main_integration_validation.json`; measured artifacts/logs/JUnit/checkout records: `evidence/m2c/main_closure/`.

Local runtime uses the prepared cloud PostgreSQL17 environment; remote workflows use fresh pgvector PostgreSQL16 services. Both execute the same frozen source. Synthetic authorized UAT personas and explicitly no-scan test policy are scoped test configuration, not claims of production security/provider readiness.

Raw logs/reports that contain original trailing whitespace are archived as gzip, with original-byte SHA256 digests and verified round trips in `evidence/m2c/main_closure/raw_artifact_manifest.json`. No evidence bytes were normalized.
