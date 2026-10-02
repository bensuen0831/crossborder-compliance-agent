from functools import wraps
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from crossborder_compliance.application.knowledge_services import (
    KnowledgeIngestionService,
    KnowledgeScopeResolver,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.knowledge import (
    KnowledgeBinding,
    KnowledgeQualityResult,
    KnowledgeScope,
    KnowledgeSource,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.knowledge_schemas import (
    ChunkDTO,
    DocumentDTO,
    DocumentRequestDTO,
    ExpectedVersionDTO,
    IngestionRequestDTO,
    RunDTO,
    ScopeRequestDTO,
    SourceRequestDTO,
    SourceUpdateDTO,
    StructureDTO,
    VersionDTO,
    VersionRequestDTO,
)

router = APIRouter(prefix="/api/v1", tags=["knowledge-foundation"])


def guarded(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PermissionError as exc:
            raise HTTPException(403, "knowledge permission required") from exc
        except LookupError as exc:
            raise HTTPException(404, "object not found") from exc
        except OptimisticConcurrencyError as exc:
            raise HTTPException(409, "stale record version") from exc
        except ValueError as exc:
            raise HTTPException(422, "invalid knowledge request or lifecycle") from exc

    return inner


def repo(request):
    context = get_repository_context(request)
    sf = (
        getattr(request.app.state, "knowledge_session_factory", None)
        or build_session_factory(get_settings().database_url)[1]
    )
    return PostgresKnowledgeRepository(sf, context)


@router.post("/admin/knowledge-sources", response_model=KnowledgeSource, status_code=201)
@guarded
def create_source(payload: SourceRequestDTO, request: Request):
    return repo(request).create_source(payload.model_dump(mode="json"))


@router.get("/admin/knowledge-sources/{source_id}", response_model=KnowledgeSource)
@guarded
def get_source(source_id: UUID, request: Request):
    return repo(request).get_source(str(source_id))


@router.patch("/admin/knowledge-sources/{source_id}", response_model=KnowledgeSource)
@guarded
def update_source(source_id: UUID, payload: SourceUpdateDTO, request: Request):
    return repo(request).update_source(
        str(source_id),
        payload.model_dump(exclude={"expected_record_version"}, exclude_none=True),
        payload.expected_record_version,
    )


@router.post("/admin/knowledge-documents", response_model=DocumentDTO, status_code=201)
@guarded
def create_document(payload: DocumentRequestDTO, request: Request):
    return repo(request).create_document(payload.model_dump(mode="json"))


@router.post("/admin/knowledge-documents/{id}/versions", response_model=VersionDTO, status_code=201)
@guarded
def create_version(id: UUID, payload: VersionRequestDTO, request: Request):
    return repo(request).create_version(str(id), payload.model_dump(mode="json"))


@router.get("/admin/knowledge-versions/{id}", response_model=VersionDTO)
@guarded
def get_version(id: UUID, request: Request):
    return repo(request).get_version(str(id))


@router.post("/admin/knowledge-versions/{id}/ingest", response_model=RunDTO, status_code=202)
@guarded
def ingest(id: UUID, payload: IngestionRequestDTO, request: Request):
    r = repo(request)
    q = getattr(request.app.state, "knowledge_queue", None)
    run = KnowledgeIngestionService(r, queue=q).ingest(str(id), payload.model_dump(mode="json"))
    return r.get_run(run["ingestion_run_id"])


def transition(action):
    @guarded
    def endpoint(id: UUID, payload: ExpectedVersionDTO, request: Request):
        return repo(request).governance(str(id), action, payload.expected_record_version)

    return endpoint


for action in ("validate", "submit-review", "approve", "publish", "supersede", "expire", "archive"):
    router.add_api_route(
        "/admin/knowledge-versions/{id}/" + action,
        transition(action),
        methods=["POST"],
        response_model=VersionDTO,
        name="knowledge_" + action,
    )


@router.get("/admin/knowledge-ingestion-runs/{id}", response_model=RunDTO)
@guarded
def get_run(id: UUID, request: Request):
    return repo(request).get_run(str(id))


def component(name):
    @guarded
    def endpoint(id: UUID, request: Request):
        return repo(request).list_component(str(id), name)

    return endpoint


for name, dto in (
    ("structure", StructureDTO),
    ("chunks", ChunkDTO),
    ("bindings", KnowledgeBinding),
    ("quality", KnowledgeQualityResult),
):
    router.add_api_route(
        "/admin/knowledge-versions/{id}/" + name,
        component(name),
        methods=["GET"],
        response_model=list[dto],
        name="knowledge_" + name,
    )


@router.post("/projects/{project_id}/knowledge-scope/resolve", response_model=KnowledgeScope)
@guarded
def resolve(project_id: UUID, payload: ScopeRequestDTO, request: Request):
    r = repo(request)
    return KnowledgeScopeResolver(r, r.context).resolve(
        str(project_id),
        snapshot_id=str(payload.analysis_snapshot_id) if payload.analysis_snapshot_id else None,
        as_of=payload.effective_as_of,
        languages=tuple(payload.languages),
    )


@router.get("/projects/{project_id}/knowledge-scope", response_model=KnowledgeScope)
@guarded
def project_scope(project_id: UUID, request: Request, analysis_snapshot_id: UUID | None = None):
    return resolve(project_id, ScopeRequestDTO(analysis_snapshot_id=analysis_snapshot_id), request)


def subject_scope(kind):
    @guarded
    def endpoint(subject_id: UUID, request: Request, analysis_snapshot_id: UUID | None = None):
        r = repo(request)
        ident = str(subject_id)
        return KnowledgeScopeResolver(r, r.context).resolve(
            r.subject_project(kind, ident),
            subject_type=kind,
            subject_id=ident,
            snapshot_id=str(analysis_snapshot_id) if analysis_snapshot_id else None,
        )

    return endpoint


router.add_api_route(
    "/data-items/{subject_id}/knowledge-scope",
    subject_scope("DATA_ITEM"),
    methods=["GET"],
    response_model=KnowledgeScope,
    name="data_item_knowledge_scope",
)
router.add_api_route(
    "/data-flows/{subject_id}/knowledge-scope",
    subject_scope("DATA_FLOW"),
    methods=["GET"],
    response_model=KnowledgeScope,
    name="data_flow_knowledge_scope",
)
