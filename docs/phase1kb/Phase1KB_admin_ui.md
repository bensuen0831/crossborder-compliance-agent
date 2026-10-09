# Canonical Admin control plane

The existing Admin models entry renders provider/model controls in the canonical host. Same session, transport, QueryClient, i18next and theme apply. Runtime-validated generated views contain configured/masked credential state only. Credentials are write-only, cleared after save/cancel, and absent from browser storage. Backend authorization is revalidated for every command.

Provider configuration creates reviewed/published immutable versions; model configuration binds an exact published provider version. Independent review is required. Discovery returns candidate names only, without publishing models. Connection and model tests use the canonical HTTP adapters with safe fixed test input. Enabled state and observed model health remain current revocation controls.

Focused measured checks: API/configuration15 PASS, control9 PASS, generic metadata3 PASS, UI6 PASS (three locales included), typecheck/lint/i18n PASS. Real Admin/User three-locale browser smoke6/6 PASS, zero retries/console errors/uncaught errors. Admin exercises actual create, masked secret, connection/discovery, independent approval/publish, model creation/test and reload. Provider health and relative operation paths are backend-owned typed controls. Final full/exact-head closure remains pending.
