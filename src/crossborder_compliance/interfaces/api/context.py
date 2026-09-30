from __future__ import annotations

from fastapi import HTTPException, Request, status

from crossborder_compliance.domain.security import RepositoryContext


def repository_context_from_request(request: Request) -> RepositoryContext:
    """Auth boundary: context must be injected by trusted auth middleware/gateway.

    Client-supplied tenant_id is never used as the authorization scope.
    """
    context = getattr(request.state, "repository_context", None)
    if not isinstance(context, RepositoryContext):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="trusted repository context is required",
        )
    return context
