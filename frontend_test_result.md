# Track D validation

Validated on 2026-10-02. Selected base: `f563e5067308e7eab6d3f89321b8b30da7c39044`; changes are in the local `admin-control-plane-foundation` branch.

| Check | Measured result |
|---|---|
| Original `bash smoke/run_gate.sh` | PASS: migrations, schema checks, multi-process LangGraph resume/retry, architecture gate; 200 tests passed, zero skipped |
| Final full Python suite | 202 passed, zero skipped/failed; one existing Starlette 422 constant deprecation warning |
| New Track D PostgreSQL/Redis API integration checks | 2 passed: metadata draft/edit/history/review/publish and Knowledge import/review/publish→automatic READY→runtime retrieval; unauthorized and cross-tenant requests rejected |
| `npm run build` | PASS: TypeScript strict check and Vite production bundle |
| `npm run lint` | PASS |
| `npm test` | 24 passed, zero skipped/failed |
| Setup repeatability | Install refresh with frozen `npm ci`, migration refresh, and service stop/restart readiness checks passed |
| Live FastAPI | `/health/live` returns ok; dependency endpoint confirms LangGraph/psycopg/Redis modules |

Frontend tests exercise all common lifecycle states, permission-filtered controls, create/edit draft flow, review/approve/publish revisions, HTTP 401/403/409/422 handling, conflict preservation, version inspection/history/projection comparison, payload-less edit protection, canonical jurisdiction identity, unknown model history numbers, metadata-derived scope options, host login, Rule boundary, context reset, runtime READY and FAILED rendering.

Runtime dependencies: Python 3.12.14; PostgreSQL 17.11 with pgvector 0.8.0; Redis 8.0.2; Node 24.19.0. CI uses PostgreSQL 16 and Redis 7 images; Docker Hub's pull limit prevented using those images here. Official signed Debian packages were used with TLS/signature verification preserved. The current machine passed the repository's actual runtime gate with these newer service versions.

Frontend component tests use mocked HTTP/typed clients. The Python integration test uses real PostgreSQL, Redis, APIs and automatic existing workers, with trusted test identity injection and a test artifact store/FakeEmbedding adapter. It verifies actual backend behavior, not a production authentication provider or S3 service. No authenticated real-browser end-to-end run was claimed. No zero-test run, unexpected skip, disabled assertion or invented recovery endpoint was used.

Evidence is retained outside the checkout under `/workspace/.onboarding`: `gate.log`, `evidence/pytest_full_summary.json`, `pytest-final.log`, `admin-api-tests.log`, `install-repeat.log`, and frontend command output. No publication/snapshot restoration in a fresh task has been verified.
