"""Northbound host model preferences cannot configure southbound providers."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from crossborder_compliance.application.llm_model_catalog import (
    EligibleModelCatalog,
    ModelCatalogQuery,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_model_catalog_composition import model_catalog
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/projects", tags=["eligible-models"])


@router.get("/{project_id}/eligible-models", response_model=EligibleModelCatalog)
def eligible_models(
    project_id: UUID,
    request: Request,
    context: Annotated[RepositoryContext, Depends(get_repository_context)],
):
    try:
        return model_catalog(sessions(request), context).read(
            ModelCatalogQuery(project_id=project_id)
        )
    except (PermissionError, LookupError):
        raise HTTPException(404, "MODEL_CATALOG_NOT_AUTHORIZED") from None
