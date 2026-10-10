# Integration client ownership

Canonical `integration_clients`, `integration_credentials`, `integration_project_bindings` are northbound identities, not web-user impersonation or LLM-provider accounts. Status ACTIVE/DISABLED/REVOKED; record_version and tenant-scoped Admin mutations use CAS/idempotency.

Canonical Admin host exposes System Settings → Integrations/API Clients: list/create, centrally supplied scopes/type choices, scope edits, enable/disable/revoke/rotate, last-used metadata, explicit project grant/revoke. One-time credential dialog is component memory only; closing/unmount/reload erases it. GET DTOs reject unknown secret fields, and QueryClient caches metadata only.

Webhook controls share this page: callback, governed deployment class, event selection, enable/disable, rotation, test and delivery history. No standalone Admin app. zh-CN/zh-HK/en-US keys are owned and checked.
