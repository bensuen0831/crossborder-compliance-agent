# M2-C0 gate

M2-C0 = PASS. M2-C1 ENTRY = ALLOWED.

Tested SHA `415ec7d82da17605a5ae5691eb0f63d0adf781a1`; original verified baseline `42571c7148456f41adb64d2528c169a357214a25`.

- PostgreSQL/contracts/migration focused:26 PASS,0 failed/errors/skipped/deselected.
- J/L-B/M2-B focused regressions:145 PASS,0 failed/errors/skipped/deselected.
- Architecture:151/151 + M2-A13/13 + M2-B27/27 + C0 15/15.
- Migration:single0014; fresh/exact0013 catalog equivalence, empty downgrade/re-upgrade, transactional data-retention refusal PASS. Frozen0001–0013 byte identity preserved.
- S1 rereads preserve exact results after S2 real binary/parse, new published policy/template/legal knowledge. Current authorization is revalidated.
- Conditional local implementation remains legally blocked; template availability does not supply a legal requirement trigger. No frontend changes.

Measured evidence: `evidence/m2c/C0_gate_result.json`, original JUnit results. Earlier interrupted checkpointer setup run is excluded; existing canonical saver initialized before the successful regression run.

C1 must use these owners and exact refs, extend the single canonical graph, and keep Stage2 generation outside scope. M2-C overall closure and exact-head CI remain pending.
