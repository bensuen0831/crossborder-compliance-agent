# Admin demo runbook

## Production integration prerequisites

Track C must mount `AdminFeature` under `/admin` inside its authenticated application shell. The host must supply an actual login action, server-derived scoped session/grants, and authenticated transport with CSRF protection. The base API has no login/session route; the standalone frontend therefore displays the sign-in boundary. Do not populate `window.crossborderAdminHost` by hand as an authentication bypass.

Deploy the existing tenant-bound ingestion worker with an S3-compatible artifact store, approved downloader destinations and Redis. The API's existing lifespan starts the publication worker. For vector-enabled policies, supply the deployment's embedding adapter; this branch does not manufacture model credentials. Have an active Knowledge Collection version, accessible metadata, project analysis snapshot and retrieval policy. Missing list APIs mean their existing IDs must be obtained from the owning integration.

These prerequisites currently block a production browser demo in the isolated checkout. The frontend foundation is built and its API flow was exercised with explicitly isolated test adapters below.

## Normal administrator flow after integration

1. Sign in through the host as an author with Knowledge VIEW/EDIT/REVIEW grants. Open **Knowledge operations**.
2. Create or open an allowed source. Supply its collection, provenance and supported source metadata. Perform source validation through its existing source-update form; the quality gate requires `validation_status=VALIDATED` and enabled source. Do not mark an unverified source validated.
3. Create/open a document, then create a version under an active collection version with language and provenance.
4. Import supported UTF-8 text, pasted canonical text, or a controlled HTTPS source. Choose scope from the metadata options; use a product-bound type for product knowledge and jurisdiction binding for country knowledge. Required permission scopes are explicit metadata. Unsupported sensitivity/retention properties are not guessed.
5. Wait for automatic ingestion completion. Inspect persisted scope bindings, run **validate**, and inspect quality evidence. Resolve quality failures through supported metadata operations.
6. **submit-review**. Sign in through the host as a different human reviewer with APPROVE permission and approve. Same-author approval is rejected by the backend.
7. Sign in as an authorized publisher and **publish**. Observe the automatic runtime panel through PENDING/BUILDING to READY, inspecting registry/FTS/vector/graph/cache evidence. FAILED states retain reason codes while the outbox retries; normal publication has no manual synchronization step.
8. With an authorized project in the host context, use **Verify runtime content**. Supply the existing analysis snapshot, policy and a unique idempotency key in the retrieval request metadata. Query text is supplied by its separate field. Verify returned evidence refers to the published version.

Normal operators do not edit source, modify the database, execute a shell sync, or restart services. Platform deployment/setup is distinct from the daily Admin workflow.

## Reproducible development validation

From the existing checkout (no extra worktree):

```bash
source /workspace/.onboarding/crossborder-env.sh
bash /workspace/.onboarding/crossborder-services.sh
cd /workspace/crossborder-compliance-agent
pytest -q tests/test_admin_control_plane_api.py
cd frontend/admin
npm run build
npm run lint
npm test
```

The new API test constructs an isolated FastAPI test application, injects trusted test identities, starts the existing ingestion/publication workers in the background, and runs source→import→independent approval→publish→READY→runtime query using real PostgreSQL/Redis. Artifact storage and embedding use explicit test adapters. It also proves 401/403/cross-tenant denial. This is reproducible automated API evidence, not a production login/S3 demo.
