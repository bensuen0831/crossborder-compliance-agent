# M2-E WIP ownership

Unfinished checkpoint; no closure or production-readiness claim.

- `alembic/env.py`
- `alembic/versions/0017_m2e_external_agent_api.py`
- `docs/m2e/M2E_D0_inventory.md`
- `docs/m2e/M2E_contract_blocker.md`
- `docs/m2e/M2E_files_created_modified.md`
- `docs/m2e/phase_progress_checkpoint.md`
- `evidence/m2e/blocked_checkpoint.json`
- `src/crossborder_compliance/application/external_channel.py`
- `src/crossborder_compliance/application/integrations.py`
- `src/crossborder_compliance/domain/integrations.py`
- `src/crossborder_compliance/infrastructure/external_composition.py`
- `src/crossborder_compliance/infrastructure/integration_worker.py`
- `src/crossborder_compliance/infrastructure/persistence/integration_models.py`
- `src/crossborder_compliance/infrastructure/persistence/integrations.py`
- `src/crossborder_compliance/infrastructure/persistence/webhooks.py`
- `src/crossborder_compliance/infrastructure/webhook_http.py`
- `src/crossborder_compliance/interfaces/api/external_schemas.py`
- `src/crossborder_compliance/interfaces/api/main.py`
- `src/crossborder_compliance/interfaces/api/routes/external.py`
- `src/crossborder_compliance/interfaces/api/routes/integrations.py`
- `src/crossborder_compliance/interfaces/api/workflow_app.py`
- `src/crossborder_compliance/workflows/langgraph_adapter.py`
- `tests/m2e_fixtures.py`
- `tests/test_m2e_http.py`
- `tests/test_m2e_identity_postgres.py`
- `tests/test_m2e_vertical_postgres.py`
- `tests/test_m2e_webhooks_postgres.py`

Frozen migrations0001–0016 and formal H/I/J owners unchanged. No frontend files changed. The canonical checkpointer setup concurrency guard is an owning runtime WIP fix, with regression verification pending.
