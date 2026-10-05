# Track D integration handoff

## Mounting in Track C

Use the existing shell and shared authenticated client. Route `/admin/*` to `AdminFeature` from `frontend/admin/src/AdminFeature.tsx`; import its scoped stylesheet. Do not create a second AppShell. The Vite standalone build is an integration harness with no implicit admin identity.

```tsx
<AdminFeature host={{
  session: effectiveSessionFromAuthenticatedHost,
  transport: authenticatedFetchWithCsrf,
  onLogin: beginExistingLogin,
}} />
```

`AdminHost` and `AdminSession` are in `contracts.ts`. Supply effective per-resource operation grants for the actor's tenant/organization/department/project context and the backend scopes verified by your server. Do not derive grants merely from a role label or accept them from browser storage. Refresh the React props on login/logout/context/grant changes; a context change remounts the data pages.

`AdminClient` is the typed fetch boundary. It uses `/api/v1`, same-origin credentials and existing optimistic concurrency. The host transport must retain that API path and provide required CSRF/session semantics. Production routing must serve the static frontend under `/admin/` and forward `/api` to the existing backend; development Vite has an internal local proxy.

Theme token compatibility: `--color-background`, `--color-surface`, `--color-text`, `--color-primary`, `--color-border`. No global CSS/AppShell was modified. Optional `host.resources` supplies descriptors for known contracts; adding an unsupported descriptor does not create an API.

## Backend boundaries

No backend implementation, migration, source-of-truth table or registry/outbox was added. Knowledge normal publish observes the existing automatic worker; Rule authoring is deferred to Phase 1H. Product/country Knowledge are binding dimensions. Download/export/reindex have no exposed endpoint and therefore no active controls.

The current API lacks auth/session middleware, complete Admin listing/history payloads and fine-grained Knowledge operation authorization. Production ingestion also needs the existing per-tenant worker/storage integration. See the exact contracts/owners in `admin_backend_gap_report.md` before claiming product-wide RBAC or a production end-to-end demo.

## Verification and delivery state

Branch `admin-control-plane-foundation`, base `f563e5067308e7eab6d3f89321b8b30da7c39044`. Changes are local, available for review; no push, merge or deployment was performed. Build/type/lint, 24 frontend tests, 202 Python tests and the baseline runtime gate passed. See `frontend_test_result.md` for adapter limitations.

Reusable environment setup is maintained in the cloud configuration's `install_script` / `start_skill`, with retained dependencies under `/workspace/.onboarding`. These instructions need publication through the environment product for future task snapshots; live API/frontend/database processes must restart. The browser preview is not published by onboarding.

Status: **ADMIN CONTROL PLANE FOUNDATION IMPLEMENTED AND VALIDATED**. Production browser demo and full operation-specific backend RBAC remain blocked by the reported contracts. This is not a claim that the complete Admin product is finished. Stop at Track D; do not implement Phase 1H Rules or another governance platform.
