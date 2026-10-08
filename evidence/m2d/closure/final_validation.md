# M2-D exact-head closure

**M2-D = PASS**. Draft PR [25](https://github.com/bensuen0831/crossborder-compliance-agent/pull/25), target main; not merged.

Baseline: `0dc005e583465a4604a5d40a369cb5fc2f0ccbef` / `v3.6-m2c-pass`.
Tested source branch: `milestone-m2d-human-review-resume`.
Final source SHA: `d3f3db430e72fb54e2be4f2c946fa62c0276a08c`. This record-only evidence branch does not advance the tested code branch.
Single Alembic head: `0015_m2d_review_governance`; frozen0001–0014 byte identity retained.

| Gate | Measured result |
|---|---|
| Full mandatory PostgreSQL backend | 763 PASS;0 failed/errors/skipped/deselected |
| New M2-D focused | 36 PASS |
| Architecture | 151+13+27+15+15+21 =242/242 |
| Runtime | 25/25 |
| Frontend | 121 PASS; typecheck/lint/build/i18n PASS |
| Browser | M2-D/C/B/A/M1 each3; M0 36; zero retry |
| Migration | Fresh, exact0014 upgrade, schema equivalence, empty downgrade/re-upgrade, retained-authority refusal PASS |
| Exact-head CI | Seven groups SUCCESS; all job checkout SHAs equal the final source SHA |

| Workflow | Result | Checkout SHA |
|---|---|---|
| phase1a-runtime-smoke | [SUCCESS](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37770169474) | `d3f3db430e72fb54e2be4f2c946fa62c0276a08c` |
| M2C Formal Result Workspace | [SUCCESS](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37770169437) | `d3f3db430e72fb54e2be4f2c946fa62c0276a08c` |
| M2A Production Intake | [SUCCESS](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37770169399) | `d3f3db430e72fb54e2be4f2c946fa62c0276a08c` |
| M2B Production Document Integration | [SUCCESS](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37770169403) | `d3f3db430e72fb54e2be4f2c946fa62c0276a08c` |
| M0 Knowledge & Evidence Preview | [SUCCESS](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37770169500) | `d3f3db430e72fb54e2be4f2c946fa62c0276a08c` |
| M1 Intake Analysis Alpha | [SUCCESS](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37770169526) | `d3f3db430e72fb54e2be4f2c946fa62c0276a08c` |
| M2D Governed Human Review | [SUCCESS](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37770169397) | `d3f3db430e72fb54e2be4f2c946fa62c0276a08c` |

Canonical ReviewTask/Decision and genuine provenance remain authoritative. Same-snapshot approval reexecutes the owning requirement stage; input corrections create a successor ProjectVersion/context/Snapshot/run and fully rerun the canonical pipeline. Source S1 semantic results and document/parse pins remain unchanged. Persisted approval/successor delivery recovery, current-role authorization, CAS/idempotency and cross-tenant refusal are empirically covered.

Unsupported correction targets and legacy authority remain explicit read-only capability gaps. No generic legal-result editor, historical retrofit, partial-rerun optimizer or multi-subject implementation. Stage2, provider onboarding and production auth redesign remain out of scope.

Earlier failed/superseded attempts are retained in the task workspace and are excluded from these final counts. Closure fixes corrected canonical Snapshot audit identity and set a bounded15-second unit-component deadline without changing assertions or adding retries. Final source assertions and seven measured CI artifacts supersede earlier-head evidence.

Machine-readable result: [final_validation.json](final_validation.json). Per-run proof records include runner checkout commands/output, immutable log hashes and artifact archive hashes; raw compressed logs and measured JSON/XML are retained below `ci/`.

POST-M2-D ENTRY = ALLOWED. Stage2 = NOT STARTED. No next milestone was started.
