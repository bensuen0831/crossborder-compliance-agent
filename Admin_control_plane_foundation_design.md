# Track D — Admin control plane foundation

Branch: `admin-control-plane-foundation`. Base: `f563e5067308e7eab6d3f89321b8b30da7c39044`.

The implementation is an isolated React/TypeScript feature at `frontend/admin`, mounted under `/admin`. There was no frontend or global AppShell in the base. `AdminFeature` is designed for Track C to mount inside its authenticated shell; the standalone entry renders a sign-in boundary until that host supplies a trusted session. It does not implement another identity system or governance backend.

`Resource` descriptors select the existing API family, resource name, fields and metadata source. A shared resource page handles draft creation/editing, lifecycle controls, version inspection/history/comparison and impact preview. `KnowledgeAdmin` adds source/document/version creation, canonical text import, scope bindings, ingestion and automatic publication observation. Product and country knowledge use the existing binding dimensions rather than separate CRUD systems. Rule editing remains a Phase 1H boundary.

`AdminClient` uses the current Phase 1C/1F/1G endpoints. Every mutation sends the observed optimistic `record_version`; errors preserve draft input and never reflect raw server configuration. Browser identity headers, database writes, migrations, manual sync and restart buttons are absent. The backend remains the authority for lifecycle and tenant access. A published `ACTIVE` version is displayed separately from runtime `READY`.

The host provides effective per-resource operations for the current role/tenant/organization/department/project context and an authenticated transport with its CSRF policy. The UI checks both those grants and existing backend scopes. A context change remounts the feature's data pages, clearing selected records and drafts. This is presentation policy, not a substitute for backend RBAC; current Knowledge RBAC is coarser than the requested operation model.

Theme variables fall back through `--color-background`, `--color-surface`, `--color-text`, `--color-primary` and `--color-border`. Styles are scoped to `.admin-feature`; no global shell styles are changed. Panels collapse to one column for mobile layouts. Navigation and controls have accessible labels, keyboard focus states, status announcements and error regions.

Foundation implementation and automated checks are complete. A production browser demo is blocked by the missing authenticated host/session integration and provisioned ingestion storage/worker. See `admin_backend_gap_report.md`; these limitations are not represented as passing product functionality.

No backend source or Alembic migration was changed. Existing prior delivery inventory is retained in `files_created_modified.md`.
