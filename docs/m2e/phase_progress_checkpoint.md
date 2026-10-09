# M2-E-R1 progress checkpoint

- Baseline SHA: `0f5a40c5ca3a8771624fb38e9380856d79e67342`; previous blocked preservation SHA: `c7d546b37a7dab2a098cda1e649010edac443798`.
- Current SHA: the next normal R1 preservation commit; obtain via `git rev-parse HEAD`. This is WIP, not closure evidence.
- Branch/worktree: `milestone-m2e-external-agent-api` / `/workspace/milestone-m2e-external-agent-api`; existing Draft PR27 retained.
- Completed checkpoint: reproduced original blocker; implemented WIP governed Binding publication, atomic A/B pin union, explicit jurisdiction execution/plan, same-jurisdiction applicability and result lookup.
- Next exact action: obtain owning additive unique-index migration decision; see `M2E_R1_schema_escalation.md`. Do not implement a migration without that decision.
- Changed files: classification/rule-hit Domain contracts, Classification/Application/FormalWorkflow owner services, existing classification governance/repository, canonical intake preparation, applicability scoping, classification API and R1 real-PG tests/fixture. M2-E WIP retained.
- Migrations: existing0017 only; no R1 migration. Frozen0001–0016 and WIP0017 unchanged.
- Tests: before fix1 FAILED at original422; intermediate H/L-B41 PASS; new owning1 FAILED at unique index collision. Later vertical slice timed out; no completed workflow claim.
- Blocker: existing partial unique index omits jurisdiction and rejects the second formal A/B classification result. Requires owning schema approval under R1 section26.
- Pending: full requested recovery regressions, temporal/digest compatibility, review regressions, architecture checks, complete HTTP vertical slice; M2-E closure remains paused.
- Do not reread: frozen V3.7/architecture/handoffs; localized blockers and owner interfaces already inspected.
- M2-E-R1 recovery BLOCKED; M2-E RESUME BLOCKED. No merge/tag/Full Stage1 E2E/Stage2.
