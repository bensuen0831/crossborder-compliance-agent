# M2-A final main validation

M2-A MAIN INTEGRATION = PASS

- Main/tested/runner checkout SHA: `da2d420602d9c71991bcae4ffd3d33c9b3497d25`.
- PR22 original source: `7105c40e7e9ccbf943ceb1a810c29ca58fb09108`; normal merge commit preserves both original parents; merged tree equals tested PR tree.
- Annotated tag: `v3.6-m2a-pass`; object `77c3dd5a89f4c866703be3f05a26144033fc54cd`; peeled target `da2d420602d9c71991bcae4ffd3d33c9b3497d25`.
- Alembic: single `0011_m2a_intake`; frozen0001–0010 byte identity unchanged.
- Backend:653 PASS,33 M2-A;0 failed/errors/skipped/deselected; B–J coverage PASS.
- Architecture:151+13 PASS; Runtime:25/25 PASS; owner/K boundary/Stage1 integrity PASS.
- Frontend:92 PASS; typecheck/lint/build/i18n PASS.
- Browser:M2-A3/3,M1 3/3,M0 36/36; every case retry0.
- Migration:fresh/exact0010→0011/schema equivalence/empty downgrade-reupgrade/authoritative-data refusal PASS.
- Blockers:NONE. No duplicate Project/Intake/BusinessFact/Snapshot/Graph/Runtime/Checkpointer/Metadata SoT; formal H/I/J decision authority unchanged.

- [phase1a-runtime-smoke](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37557203610): SUCCESS; head `da2d420602d9c71991bcae4ffd3d33c9b3497d25`; artifact `11455569435`.
- [M2A Production Intake](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37557205479): SUCCESS; head `da2d420602d9c71991bcae4ffd3d33c9b3497d25`; artifact `11455167646`.
- [M1 Intake Analysis Alpha](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37557208612): SUCCESS; head `da2d420602d9c71991bcae4ffd3d33c9b3497d25`; artifact `11454819494`.
- [M0 Knowledge & Evidence Preview](https://github.com/bensuen0831/crossborder-compliance-agent/actions/runs/37557211634): SUCCESS; head `da2d420602d9c71991bcae4ffd3d33c9b3497d25`; artifact `11455303816`.

Machine results and SHA256 manifest are in `evidence/integration/m2a-main`; full artifact/log digests are in `final_main_validation.json`. Evidence-only branch preserves verified main; M2-B must start from this main/tag.
