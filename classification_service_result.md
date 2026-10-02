# Phase 1H application and reference API

ClassificationService receives only project, snapshot, data-item and scheme-version references. The repository checks trusted operation/project scopes; actual snapshot project-version and Phase 1E context pins; exact validated data-item/context versions; one resolved scheme jurisdiction; durable scheme/rule publication; and explicit configuration pins. Formal BusinessFact values, source references, quality, resolved scenario/product and formal industry/data-category codes build RuleFactContext.

Document evidence is joined through exact item source traces to same-tenant/project ACTIVE documents and VALID references. Existing saved Phase 1G retrieval responses are revalidated through their canonical repository and owner/subject permission; no new retrieval is started. Hits persist even for an evaluated insufficient outcome; no-data/missing-fact preconditions return typed outcomes without fabricated results. Snapshot locking and a partial unique index make formal-result retries return the persisted result.

## Added routes

| Method | Path | Behavior |
|---|---|---|
| POST | `/api/v1/admin/rules/{definition_id}/versions` | New draft version |
| POST | `/api/v1/admin/rules/{version_id}/validate` or `/test` | Persisted contract/test validation |
| GET | `/api/v1/admin/rules/{version_id}` | Authorized version/test detail |
| POST | `/api/v1/admin/classification-schemes/{scheme_id}/versions` | New scheme draft |
| GET | `/api/v1/admin/classification-schemes/{version_id}` | Authorized scheme detail |
| POST | `/api/v1/projects/{project_id}/snapshots/{snapshot_id}/classification-pins` | Explicit initialization |
| POST | `/api/v1/projects/{project_id}/classifications` | Execute against authorized references |
| GET | `/api/v1/classifications/{result_id}` | Scoped, evidence-revalidated read |

Existing generic draft/review/publish endpoints remain the governance entry points. The classification router precedes the generic knowledge admin router so `/admin/rules/{version}` cannot be shadowed. Execution DTO forbids caller-provided facts, results, evidence, jurisdiction or narrative. Tests execute actual FastAPI requests and real persistence, including rejected fields, 401/403/404/422 and replay.

## Measured implementation evidence

Source: `1de60800efa7dc2e9f7092842e0044899eb74690`, based on verified Phase 1G `f563e5067308e7eab6d3f89321b8b30da7c39044`.
Local full PostgreSQL gate: **284 passed / 0 skipped / 0 deselected / 0 failed / 0 errors**; Phase 1H **84 tests** (66 unit/lineage, 18 PostgreSQL/API/migration). Architecture **118/118**, Phase 1H schema **20/20**, existing runtime **25/25**.

[Full local log](evidence/phase1h/local-implementation/ci_complete.log), [test summary](evidence/phase1h/local-implementation/pytest_full_summary.json), [migration evidence](evidence/phase1h/local-implementation/phase1h_migration_dual_path.json), [hash manifest](evidence/phase1h/local-implementation/manifest.json).

Remote implementation and documentation-closure evidence is recorded separately in [Phase1H_delivery_handoff.md](Phase1H_delivery_handoff.md). Overall Phase 1H closure requires that final remote branch CI pass. PR [#13](https://github.com/bensuen0831/crossborder-compliance-agent/pull/13) remains **DRAFT; do not merge**. No Phase 1I implementation is authorized here.
