"""Canonical admin API extensions; no client tenant/policy or raw credentials returned."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.exc import IntegrityError

from crossborder_compliance.domain.model_control import (
    ControlEnabled,
    ControlTransition,
    ModelDraft,
    ProviderDraft,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.model_control_composition import model_control
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataOptimisticConcurrencyError,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.model_schemas import (
    EnabledView,
    ModelListView,
    ModelTestRequest,
    ModelView,
    ProviderListView,
    ProviderTestResult,
    ProviderVersionView,
)
from crossborder_compliance.interfaces.api.routes.workflow import sessions


class WriteOnlySecretRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError:
                # FastAPI defaults may serialize validation input, including write-only secrets.
                raise HTTPException(422, "MODEL_CONTROL_REQUEST_INVALID") from None

        return handler


router = APIRouter(
    prefix="/api/v1/admin/model-providers", tags=["model-control"], route_class=WriteOnlySecretRoute
)
Context = Annotated[RepositoryContext, Depends(get_repository_context)]


def call(request, context, operation, *args, inspection=False):
    try:
        control, probe = model_control(request, sessions(request), context)
        return getattr(probe if inspection else control, operation)(*args)
    except (LookupError, PermissionError):
        raise HTTPException(404, "MODEL_CONTROL_NOT_AUTHORIZED") from None
    except (MetadataOptimisticConcurrencyError, IntegrityError):
        raise HTTPException(409, "MODEL_CONTROL_CONFLICT") from None
    except ValueError:
        raise HTTPException(422, "MODEL_CONTROL_CONFIGURATION_INVALID") from None


@router.get("", response_model=ProviderListView)
def providers(request: Request, context: Context):
    return {"providers": call(request, context, "providers")}


@router.post("", response_model=ProviderVersionView, status_code=201)
def save_provider(body: ProviderDraft, request: Request, context: Context):
    return call(request, context, "save_provider", body)


@router.post("/versions/{version_id}/transition", response_model=ProviderVersionView)
def provider_transition(
    version_id: UUID, body: ControlTransition, request: Request, context: Context
):
    return call(request, context, "transition", "PROVIDER", version_id, body)


@router.put("/{provider_id}/enabled", response_model=EnabledView)
def provider_enabled(provider_id: UUID, body: ControlEnabled, request: Request, context: Context):
    return call(request, context, "enabled", "PROVIDER", provider_id, body)


@router.post("/versions/{version_id}/test-connection", response_model=ProviderTestResult)
def test_connection(version_id: UUID, request: Request, context: Context):
    return call(request, context, "connection_test", version_id, inspection=True)


@router.post("/versions/{version_id}/discover-models", response_model=ProviderTestResult)
def discover_models(version_id: UUID, request: Request, context: Context):
    return call(request, context, "connection_test", version_id, inspection=True)


@router.get("/{provider_id}/models", response_model=ModelListView)
def models(provider_id: UUID, request: Request, context: Context):
    return {"models": call(request, context, "models", provider_id)}


@router.post("/{provider_id}/models", response_model=ModelView, status_code=201)
def save_model(provider_id: UUID, body: ModelDraft, request: Request, context: Context):
    return call(request, context, "save_model", provider_id, body)


@router.post("/models/deployments/{deployment_id}/transition", response_model=ModelView)
def model_transition(
    deployment_id: UUID, body: ControlTransition, request: Request, context: Context
):
    return call(request, context, "transition", "MODEL", deployment_id, body)


@router.put("/models/{model_id}/enabled", response_model=EnabledView)
def model_enabled(model_id: UUID, body: ControlEnabled, request: Request, context: Context):
    return call(request, context, "enabled", "MODEL", model_id, body)


@router.post("/models/deployments/{deployment_id}/test", response_model=ProviderTestResult)
def test_model(deployment_id: UUID, body: ModelTestRequest, request: Request, context: Context):
    return call(request, context, "model_test", deployment_id, body.operation, inspection=True)
