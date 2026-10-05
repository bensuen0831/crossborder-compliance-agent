# M0 demo runbook

Use the existing dedicated Track C checkout. Do not reset shared work or create a competing
migration. Preserve the verified Phase 1G base and other tasks' files.

## Prerequisites and synthetic fixture preparation

Python 3.12, Node >=22.12, PostgreSQL with pgvector and Redis are needed. Use a new empty,
disposable database: never point this seed/run_gate workflow at a shared production database.
Migrations are the existing unchanged 0001–0007. Local onboarding services are available at
5432/6379; CI uses pgvector/pgvector:pg16 and redis:7-alpine.

```bash
cd /workspace/crossborder-m0-h5-preview
UV_CACHE_DIR=/workspace/.uv-cache uv venv /workspace/.m0-preview-venv --python 3.12
UV_CACHE_DIR=/workspace/.uv-cache uv pip install --python /workspace/.m0-preview-venv/bin/python -e '.[dev]'
source /workspace/.m0-preview-venv/bin/activate
export APP_ENV=LOCAL_SERVER PYTHONDONTWRITEBYTECODE=1
export DATABASE_URL=postgresql+psycopg://compliance:compliance@127.0.0.1:5432/m0_preview_uat
export LANGGRAPH_DATABASE_URI='postgresql://compliance:compliance@127.0.0.1:5432/m0_preview_uat?sslmode=disable'
export REDIS_URL=redis://127.0.0.1:6379/0
alembic upgrade head
python scripts/m0_preview/seed.py --output /workspace/m0-preview-state/personas.json
```

Create the database first with your PostgreSQL administrator. The URL above contains only
public disposable development credentials used by repository CI. If personas.json already exists,
reuse it; seed refuses to overwrite it or reset existing data. A new seed requires a new manifest
path and adds synthetic isolated tenants through existing fixture/service capabilities. Missing
manifest after a partially failed seed does not authorize deleting other data.

## Fresh backend and frontend start

Backend shell, using the environment above:

```bash
export M0_LOCAL_UAT=1
python scripts/m0_preview/server.py --manifest /workspace/m0-preview-state/personas.json --port 8010
```

Frontend shell:

```bash
cd /workspace/crossborder-m0-h5-preview/frontend
npm ci --cache /workspace/.npm-cache --no-audit --no-fund
VITE_M0_DEMO=true VITE_SESSION_PATH=/m0-demo/session npm run dev
```

The Vite terminal reports port 5173; backend is loopback port 8010. Check /health/live using a
local request. Stop only the processes you started. Restarting the backend intentionally invalidates
UAT cookies; sign in again. Existing database pins and knowledge versions persist.

In the app: sign in as A → choose Generic Project UAT A → inspect pinned Product/Scenario/
Jurisdiction → enter Generic → Search → two real FTS evidence rows → open Source & Citation →
inspect citation, excerpt, hash and version → review INSUFFICIENT and evidence-acquisition actions →
Runtime status READY (Vector NOT_CONFIGURED). Query zzznomatchtokenzzz to exercise empty/fallback.
Switch to B: A results disappear; B receives only B's knowledge. Browser E2E additionally attempts
A's saved run from B and verifies backend 404. No real sensitive content or legal answers are seeded.

```bash
M0_CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e
```

Omit M0_CHROMIUM_PATH where Playwright's Chromium is installed. CI installs it with
`npx playwright install --with-deps chromium`.

## Production integration boundary

Build with `npm run build` without VITE_M0_DEMO. Deploy dist/ with SPA route fallback and a
same-origin trusted session/BFF plus backend API routing. Implement the presentation-only session
and logout integration contract; do not send tenant IDs from client controls. Do not run the local
UAT server or ship fixture personas as authentication. Session-context grants are server-provided;
backend scope remains authoritative. Normal Publish is handled by the existing worker/outbox,
not manual synchronization. Track D Admin integration uses existing /api/v1/admin route boundaries.
