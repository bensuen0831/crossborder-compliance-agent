from __future__ import annotations

from fastapi import HTTPException, Request, status

from crossborder_compliance.domain.security import RepositoryContext


def get_repository_context(request: Request) -> RepositoryContext:
    context = getattr(request.state, "repository_context", None)
    if not isinstance(context, RepositoryContext):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="trusted repository context is required",
        )
    return context
