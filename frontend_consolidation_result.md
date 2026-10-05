# Frontend consolidation result

One production H5 host, inherited from Track C:

```text
frontend/
  package.json
  package-lock.json
  index.html
  vite.config.ts
  src/
    main.tsx              # one React root, BrowserRouter and QueryClientProvider
    App.tsx               # canonical AppShell + Knowledge/Runtime/Admin routes
    api/                  # canonical typed contracts and shared HTTP/session transport
    theme.ts
    i18n.ts
    routes/AdminRoute.tsx
    features/admin/
      AdminFeature.tsx
      KnowledgeAdmin.tsx
      ResourceAdmin.tsx
      RuleAdmin.tsx
      RuntimeStatus.tsx
      client.ts           # typed endpoint wrappers delegate to api/client.request
      contracts.ts
      presentation.ts
      resources.ts
      admin.css
      admin.test.tsx
    components/           # existing M0 Knowledge/Evidence/Citation/Sufficiency UI
  e2e/knowledge.spec.ts
```

The canonical shell retains the selected authorized project/snapshot/policy context. Identity changes clear the Query cache and remount the workspace; Admin resource state is keyed by the trusted tenant/actor/context. An absent admin_context closes /admin access; grants must also intersect backend scopes. Browser labels and hiding provide presentation only; API authorization remains authoritative.

No independent production package, lockfile, React root, Vite app, global router, session storage or HTTP implementation remains under frontend/admin. All original D modules/tests are retained in Git ancestry. C theme tokens are passed to Admin CSS; unsupported resources stay boundary screens, persisted editors lacking payload stay disabled, and unavailable ingestion remains disabled.

Typecheck, stricter canonical lint, unit tests and one production build pass. Known pre-existing >500 KB enterprise bundle warning remains; no unrelated bundle/dependency redesign was introduced.
