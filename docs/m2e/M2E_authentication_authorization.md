# Authentication and authorization

OAuth2 client_credentials is form POST `/api/v1/external/oauth/token`. Short-lived opaque bearer tokens are hashed at rest and bound to client, credential generation, tenant and granted scopes. Service accounts use separately prefixed, expiring, revocable credentials; both map to the same RepositoryContext/PermissionContext.

Every operation/stream poll revalidates live client ACTIVE state, active credential/generation/expiry, live reduced scopes, tenant and project binding. Ordinary integrations never use system=True. Actor `integration:<client_id>` is auditable. Admin management requires canonical `integration:manage` and current tenant context; normal users cannot configure clients/providers.

Client credentials use salted scrypt, never plaintext DB persistence. Create/rotate exposes the value once; idempotent replay returns the same credential identity with value absent. Credential rotation revokes prior credentials/tokens; disable/revoke fails closed. Do not log request forms or Authorization headers at deployment ingress.

Scopes come from IntegrationScope/CANONICAL_SCOPE_MAP; project:create/read, intake:write, document:upload, compliance:analyze/read, model:select, webhook:manage. OAuth requested scope may only reduce current permissions. Created projects bind CREATED_BY_CLIENT; Admin can explicitly grant/revoke a tenant-owned project. No blanket tenant project access.
