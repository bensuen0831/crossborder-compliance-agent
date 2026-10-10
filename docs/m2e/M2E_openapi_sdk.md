# Public OpenAPI and SDKs

Generate: `PYTHONPATH=src:. python frontend/scripts/m2e/export_contracts.py`; generate TypeScript through existing openapi-typescript from `sdk/openapi/external-v1.json`. Exporter also creates canonical Admin DTOs and packages the exact public spec for Python runtime validation. Public OAuth/Bearer security schemes, strict schemas, stable error responses, API/schema versions and WS event extension are checked.

Python package: `pip install ./sdk/python`; AgentClient supports auth/service bearer, create/read/update intake, multipart upload, parse, eligible models, confirm, async start, status/result, bounded polling, SSE and webhook subscribe. It holds bearer only in memory; close releases owned HTTP transport. Public JSON Schema validates typed inputs/events.

TypeScript: `frontend/node_modules/.bin/tsc -p sdk/typescript/tsconfig.json`; import AgentClient from built package. Same minimum operations, generated DTOs, multipart, bounded polling and SSE helpers. Callers supply their transport/runtime and credential securely. No legal/classification/risk/path code in either SDK. Protocol test servers test transport only; real gateway acceptance is separately PostgreSQL/HTTP.

Admin integration remains in existing generated frontend transport/Ajv/QueryClient/session/i18n host. SDKs do not expose internal Admin APIs or provider credentials.

Both SDKs expose create_successor/createSuccessor for the canonical confirmed-intake successor operation. Read/update/confirm the resulting new draft, then invoke existing START; never modify an old Snapshot. The additional v1 endpoint is non-breaking and uses existing strict expected-version DTOs.
