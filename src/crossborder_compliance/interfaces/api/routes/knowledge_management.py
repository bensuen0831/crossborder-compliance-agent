"""Authenticated management channel over canonical Knowledge/Metadata use cases."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from crossborder_compliance.application.knowledge_taxonomy import KnowledgeTaxonomyService
from crossborder_compliance.domain.knowledge_management import (
    CreateKnowledgeHold,
    CreateTaxonomy,
    EditTaxonomy,
    MergeTaxonomy,
    MutateTaxonomy,
    TaxonomyKind,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementCapabilityError,
    KnowledgeManagementConflict,
    PostgresKnowledgeTaxonomyRepository,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.knowledge_management_schemas import (
    KnowledgeAuditPage,
    KnowledgeHoldMutation,
    KnowledgeHoldView,
    TaxonomyAliases,
    TaxonomyDetail,
    TaxonomyImpact,
    TaxonomyMutationResult,
    TaxonomyPage,
)
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])
Context = Annotated[RepositoryContext, Depends(get_repository_context)]


@router.get("/audit/{resource_id}", response_model=KnowledgeAuditPage)
def audit_history(
    resource_id: UUID,
    request: Request,
    context: Context,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return invoke(
        service(request, context).audit_history, resource_id, page=page, page_size=page_size
    )


@router.post("/holds", status_code=201, response_model=KnowledgeHoldMutation)
def create_hold(body: CreateKnowledgeHold, request: Request, context: Context):
    return invoke(service(request, context).create_hold, body)


@router.get("/holds/{resource_type}/{resource_id}", response_model=list[KnowledgeHoldView])
def list_holds(
    resource_type: Literal["TAXONOMY", "KNOWLEDGE_DOCUMENT"],
    resource_id: UUID,
    request: Request,
    context: Context,
):
    return invoke(service(request, context).list_holds, resource_type, resource_id)


@router.post("/holds/{hold_id}/release", response_model=KnowledgeHoldMutation)
def release_hold(hold_id: UUID, body: MutateTaxonomy, request: Request, context: Context):
    return invoke(service(request, context).release_hold, hold_id, body)


def service(request, context):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    return KnowledgeTaxonomyService(PostgresKnowledgeTaxonomyRepository(factory, context), context)


def invoke(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PermissionError as exc:
        raise HTTPException(403, {"code": "KNOWLEDGE_OPERATION_NOT_AUTHORIZED"}) from exc
    except LookupError as exc:
        raise HTTPException(404, {"code": "KNOWLEDGE_RESOURCE_NOT_FOUND"}) from exc
    except KnowledgeManagementCapabilityError as exc:
        raise HTTPException(503, {"code": str(exc)}) from exc
    except KnowledgeManagementConflict as exc:
        raise HTTPException(409, {"code": str(exc)}) from exc
    except OptimisticConcurrencyError as exc:
        raise HTTPException(409, {"code": "KNOWLEDGE_VERSION_CONFLICT"}) from exc
    except IntegrityError as exc:
        raise HTTPException(409, {"code": "KNOWLEDGE_IDENTITY_OR_REFERENCE_CONFLICT"}) from exc
    except ValueError as exc:
        raise HTTPException(422, {"code": "INVALID_KNOWLEDGE_MANAGEMENT_REQUEST"}) from exc


@router.get("/taxonomy", response_model=TaxonomyPage)
def taxonomy_list(
    request: Request,
    context: Context,
    kind: TaxonomyKind | None = None,
    query: str = Query(default="", max_length=250),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    locale: Literal["zh-CN", "zh-HK", "en-US"] = "en-US",
    enabled: bool | None = None,
):
    return invoke(
        service(request, context).list,
        kind=kind,
        query=query,
        page=page,
        page_size=page_size,
        locale=locale,
        enabled=enabled,
    )


@router.post("/taxonomy", status_code=201, response_model=TaxonomyMutationResult)
def taxonomy_create(body: CreateTaxonomy, request: Request, context: Context):
    return invoke(service(request, context).mutate, "CREATE", None, body)


@router.get("/taxonomy/{definition_id}", response_model=TaxonomyDetail)
def taxonomy_detail(definition_id: UUID, request: Request, context: Context):
    return invoke(service(request, context).detail, definition_id)


@router.get("/taxonomy/{definition_id}/impact", response_model=TaxonomyImpact)
def taxonomy_impact(definition_id: UUID, request: Request, context: Context):
    return invoke(service(request, context).impact, definition_id)


@router.get("/taxonomy/{definition_id}/aliases", response_model=TaxonomyAliases)
def taxonomy_aliases(definition_id: UUID, request: Request, context: Context):
    return invoke(service(request, context).aliases, definition_id)


@router.patch("/taxonomy/versions/{version_id}", response_model=TaxonomyMutationResult)
def taxonomy_edit(version_id: UUID, body: EditTaxonomy, request: Request, context: Context):
    return invoke(service(request, context).mutate, "EDIT_DRAFT", version_id, body)


@router.post(
    "/taxonomy/{definition_id}/versions", status_code=201, response_model=TaxonomyMutationResult
)
def taxonomy_version(definition_id: UUID, body: EditTaxonomy, request: Request, context: Context):
    return invoke(service(request, context).mutate, "NEW_VERSION", definition_id, body)


@router.post(
    "/taxonomy/{definition_id}/merge", status_code=201, response_model=TaxonomyMutationResult
)
def taxonomy_merge(definition_id: UUID, body: MergeTaxonomy, request: Request, context: Context):
    return invoke(service(request, context).mutate, "MERGE_PROPOSAL", definition_id, body)


@router.delete("/taxonomy/{definition_id}", response_model=TaxonomyMutationResult)
def taxonomy_delete(definition_id: UUID, body: MutateTaxonomy, request: Request, context: Context):
    return invoke(service(request, context).mutate, "DELETE_DRAFT", definition_id, body)


def lifecycle_endpoint(operation):
    def endpoint(version_id: UUID, body: MutateTaxonomy, request: Request, context: Context):
        return invoke(service(request, context).mutate, operation, version_id, body)

    return endpoint


for path, operation in {
    "submit-review": "SUBMIT_REVIEW",
    "approve": "APPROVE",
    "reject": "REJECT",
    "publish": "PUBLISH",
    "archive": "ARCHIVE",
}.items():
    router.add_api_route(
        "/taxonomy/versions/{version_id}/" + path,
        lifecycle_endpoint(operation),
        methods=["POST"],
        name="kb_taxonomy_" + path,
        response_model=TaxonomyMutationResult,
    )


def availability_endpoint(operation):
    def endpoint(definition_id: UUID, body: MutateTaxonomy, request: Request, context: Context):
        return invoke(service(request, context).mutate, operation, definition_id, body)

    return endpoint


for path, operation in {"deactivate": "DEACTIVATE", "reactivate": "REACTIVATE"}.items():
    router.add_api_route(
        "/taxonomy/{definition_id}/" + path,
        availability_endpoint(operation),
        methods=["POST"],
        name="kb_taxonomy_" + path,
        response_model=TaxonomyMutationResult,
    )
