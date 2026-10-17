"""Optional CSV/XLSX catalogue adaptation; knowledge publication stays explicit."""

import tempfile
from pathlib import Path
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Query, Request

from crossborder_compliance.application.knowledge_manifest_imports import (
    KnowledgeManifestImportService,
)
from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.domain.knowledge_manifest_governance import PrepareKnowledgeManifest
from crossborder_compliance.infrastructure.persistence.knowledge_manifest_imports import (
    PostgresKnowledgeManifestImports,
)
from crossborder_compliance.interfaces.api.knowledge_manifest_schemas import (
    KnowledgeManifestDetail,
    KnowledgeManifestMissingFiles,
    KnowledgeManifestPage,
    KnowledgeManifestView,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import Context, invoke
from crossborder_compliance.interfaces.api.routes.knowledge_uploads import service as upload_service
from crossborder_compliance.interfaces.api.routes.workflow import sessions

router = APIRouter(prefix="/api/v1/admin/knowledge-management", tags=["knowledge-management"])


def service(request, context, *, with_storage=False):
    factory = getattr(request.app.state, "knowledge_session_factory", None) or sessions(request)
    storage = upload_service(request, context).storage if with_storage else None
    working_root = getattr(request.app.state, "knowledge_manifest_working_root", None)
    if working_root is None:
        working_root = Path(tempfile.gettempdir()) / "crossborder-knowledge-manifests"
    return KnowledgeManifestImportService(
        PostgresKnowledgeManifestImports(
            factory,
            context,
            storage=storage,
            working_root=working_root,
        ),
        context,
    )


@router.post(
    "/import-batches/{batch_id}/manifests", status_code=201, response_model=KnowledgeManifestView
)
def prepare(batch_id: UUID, body: PrepareKnowledgeManifest, request: Request, context: Context):
    def execute():
        for grant in ("batch:manifest-import", "batch:read", "upload:read"):
            require_management_permission(context, grant)
        return service(request, context, with_storage=True).prepare(batch_id, body)

    try:
        return invoke(execute)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, {"code": "KNOWLEDGE_BINARY_STORAGE_UNAVAILABLE"}) from exc


@router.get("/import-batches/{batch_id}/manifests", response_model=KnowledgeManifestPage)
def list_manifests(
    batch_id: UUID,
    request: Request,
    context: Context,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return invoke(service(request, context).list, batch_id, page=page, page_size=page_size)


@router.get(
    "/import-batches/{batch_id}/manifests/{manifest_id}", response_model=KnowledgeManifestDetail
)
def detail(
    batch_id: UUID,
    manifest_id: UUID,
    request: Request,
    context: Context,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return invoke(
        service(request, context).detail, batch_id, manifest_id, page=page, page_size=page_size
    )


@router.get(
    "/import-batches/{batch_id}/manifests/{manifest_id}/missing-files",
    response_model=KnowledgeManifestMissingFiles,
)
def missing_files(
    batch_id: UUID,
    manifest_id: UUID,
    request: Request,
    context: Context,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
):
    return invoke(
        service(request, context).missing_files,
        batch_id,
        manifest_id,
        page=page,
        page_size=page_size,
    )
