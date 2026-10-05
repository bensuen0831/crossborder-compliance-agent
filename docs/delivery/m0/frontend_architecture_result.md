# Frontend architecture result

`frontend/` is an independent React/TypeScript/Vite workspace with a committed npm lockfile.
Backend dependencies, tests and architecture rules are unchanged. Core controls are Ant Design
Select, Form, Table, Tabs, Drawer, Card, Alert and pagination. Guidance uses Ant Design Listy.

Layers: `api/client.ts` → `features/knowledge/queries.ts` → presentation mappers → reusable
components → AppShell/routes. Components contain no ad-hoc business API URLs. Same-origin
credentials are used; no tenant header, permission scope or frontend secret is sent. Fetches carry
AbortSignal. Metadata responses and the separate presentation-session contract are validated;
frozen result contracts use Ajv against exact backend OpenAPI schemas.

`scripts/m0_preview/export_contracts.py` exports only consumed existing endpoints and their
transitive schemas. `npm run generate:types` generates TypeScript. CI regenerates and requires
zero diff, catching contract drift without modifying backend declarations.

`theme.ts` centralizes Midnight component colors and density. CSS concerns layout, wrapping and
responsive grids. i18next has Traditional Chinese/English resources and fallback for unknown
backend codes. Status labels are textual as well as colored. Forms, selectors and search have
accessible names; source actions and drawer are keyboard usable. Browser tests exercise Escape
to close the drawer and a narrower viewport.

Server state is keyed by identity and project/snapshot/request. Identity changes hide the old
workspace, cancel in-flight work, clear QueryClient and remount the workspace. Evidence is not
stored in localStorage, persisted caches or debug logs. Errors hide prior results and show only
safe messages and trace_id where available. Unsafe source link schemes/userinfo are rejected.

Production build excludes demo buttons by default. `VITE_M0_DEMO=true` and
`VITE_SESSION_PATH=/m0-demo/session` are explicit non-secret local UAT settings. Deployment uses
same-origin routing/BFF, not permissive credentialed CORS. Initial enterprise-library bundle is
roughly 335 KB gzip; additional route-level optimization is a later frontend performance task.
