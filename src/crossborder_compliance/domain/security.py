from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


class TenantAccessDenied(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: str
    organization_id: UUID | None = None
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class PermissionContext:
    actor_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    system: bool = False
    admin_tenant_ids: frozenset[UUID] = field(default_factory=frozenset)

    def can_access(self, tenant_id: UUID, *, tenant_context: TenantContext) -> bool:
        if self.system:
            return True
        return tenant_id == tenant_context.tenant_id or tenant_id in self.admin_tenant_ids


@dataclass(frozen=True, slots=True)
class RepositoryContext:
    tenant: TenantContext
    user: UserContext
    permission: PermissionContext

    @classmethod
    def user(cls, tenant_id: UUID, actor_id: str, scopes: set[str] | None = None) -> "RepositoryContext":
        return cls(
            tenant=TenantContext(tenant_id),
            user=UserContext(user_id=actor_id),
            permission=PermissionContext(actor_id=actor_id, scopes=frozenset(scopes or set())),
        )

    @classmethod
    def system(cls, tenant_id: UUID, actor_id: str = "system") -> "RepositoryContext":
        return cls(
            tenant=TenantContext(tenant_id),
            user=UserContext(user_id=actor_id),
            permission=PermissionContext(actor_id=actor_id, scopes=frozenset({"system"}), system=True),
        )

    def assert_tenant(self, tenant_id: UUID) -> None:
        if not self.permission.can_access(tenant_id, tenant_context=self.tenant):
            raise TenantAccessDenied(f"tenant access denied: {tenant_id}")

    @property
    def tenant_id(self) -> UUID:
        return self.tenant.tenant_id
