# Phase1J test result

Local mandatory closure gate: PASS on executable HEAD `9ad6335e1f4969044c886bdd0ee22a3585e058c2`. Final Phase1J-B certification also requires exact-head remote CI, recorded in Draft PR19 checks and the final branch evidence. Earlier J-A CI is not reused.

Focused evidence available:

- Contracts/engines:40 PASS (`artifacts/phase1j-domain-final.log`).
- Consolidated actual PostgreSQL/API:30 PASS; contracts/engines + PostgreSQL total70 PASS in197.31s (`artifacts/phase1j-consolidated.log`). Including migration1 and ownership8,79 focused J cases PASS.
- Actual J migration dual-path/downgrade:1 PASS after final immutable-policy DDL. Historical H/I migration focused regression:3 PASS including J.
- Ownership:8 J tests plus retained1K-A boundary test PASS; boundary20/20; Stage1 integrity14/14.
- J schema:36/36 PASS. Architecture:151/151 PASS (135 retained +16 new); Rules1–155.

The initial closure gate and one permitted closure-blocker repeat ran on a newly created empty dedicated PostgreSQL database through `bash smoke/run_gate.sh`, including all historical schema checks, checkpointer process restart/resume/retry, full pytest with zero required skips/deselections, J schema and architecture checks. Logs and JUnit evidence: `artifacts/phase1j-b-closure-fix/`.

Measured result:566 PASS;0 failed/errors/skipped/deselected. Phase1B–1I schema gates PASS; J schema36/36; architecture151/151; runtime25/25. All79 J cases ran in the full suite. Initial exact-head CI contract collection failed because the new ownership test relied on a repository-root PYTHONPATH. A test-only runpy loader fix matches the retained1K-A pattern; bare CI-equivalent subset363 PASS/203 deliberately deselected runtime cases. After that closure blocker, one fresh-DB full gate repeat passed566/566 with zero skips/deselections. Backend/migration code was unchanged.

Final branch remains Draft PR19 targeting main; no merge or J-C continuation. The final documentation/evidence commit changes no executable code. PR19 records the final exact-head CI URL/SHA after the corrected final push; local evidence is summarized in `evidence/phase1j/Phase1J_gate_summary.json`.
