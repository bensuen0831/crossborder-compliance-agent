# Review security boundary

Every list/read/decision/correction/recovery validates current tenant, project access, workflow:read and current write permissions. Current workflow:review plus task.required_role is required for any write; successor construction also requires project:update/confirm and workflow:execute. No client actor/tenant/role/thread/policy/decision-result authority is accepted. Cross-tenant/wrong-project/missing-role failures are indistinguishable404.

Decision mutation is atomic with row-lock CAS, append-only ReviewDecision and AuditEvent. Actor-bound idempotency checks payload digest; changed replay fails closed. Correction uses repeatable-read, source-universe validation and existing owner transactions, with immutable relational lineage. No silent cross-source overwrite. Current permissions are revalidated after durable checkpoint load; snapshot and checkpoint never authorize.

Tests cover spoof injection, stale/two-reviewer conflict, immutable history, read-only roles, direct runtime required-role enforcement, approval delivery failure, successor delivery recovery, duplicate/restart and S1 preservation. Production IAM/SSO/CSRF redesign remains out of scope.
