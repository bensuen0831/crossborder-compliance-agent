"""Trusted-context API consumes Phase 1F scope and never accepts a client scope."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request

from crossborder_compliance.application.external_evidence_services import (
    ExternalEvidenceAugmentationService,
)
from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
from crossborder_compliance.application.retrieval_services import KnowledgeRetrievalService
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.retrieval import (
    EvidencePack,
    KnowledgeRetrievalQuery,
    KnowledgeSufficiencyResult,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.retrieval_navigation import (
    PostgresRetrievalNavigationRepository,
)
from crossborder_compliance.infrastructure.retrieval_external import AuditedExternalDownloader
from crossborder_compliance.infrastructure.retrieval_search import (
    PgvectorRetrieverAdapter,
    PostgresFTSRetrieverAdapter,
)
from crossborder_compliance.infrastructure.retrieval_test_adapters import (
    DeterministicEvidenceGapQueryPlanner,
    DeterministicWikiGenerator,
    RegistrySourceDiscoveryAdapter,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.retrieval_schemas import (
    ExpectedDTO,
    GraphRequestDTO,
    NavigationResponseDTO,
    PolicyRequestDTO,
    PolicyResponseDTO,
    RetrievalRequestDTO,
    RetrievalResponseDTO,
    WikiRequestDTO,
)
from crossborder_compliance.interfaces.api.routes.knowledge import guarded

router = APIRouter(prefix="/api/v1", tags=["scope-first-retrieval"])
KINDS = {
    "knowledge-retrieval-policies": "retrieval",
    "knowledge-sufficiency-policies": "sufficiency",
    "trusted-source-policies": "trusted_source",
}
PolicyKind = Literal[
    "knowledge-retrieval-policies", "knowledge-sufficiency-policies", "trusted-source-policies"
]


def repo(request):
    context = get_repository_context(request)
    sessions = (
        getattr(request.app.state, "knowledge_session_factory", None)
        or build_session_factory(get_settings().database_url)[1]
    )
    return PostgresRetrievalNavigationRepository(sessions, context)


def service(request, r):
    external = ExternalEvidenceAugmentationService(
        r,
        r.context,
        DeterministicEvidenceGapQueryPlanner(),
        RegistrySourceDiscoveryAdapter(r),
        getattr(request.app.state, "external_downloader_factory", AuditedExternalDownloader),
    )
    return KnowledgeRetrievalService(
        r,
        r.context,
        PostgresFTSRetrieverAdapter(r.sessions, r.context),
        PgvectorRetrieverAdapter(r.sessions, r.context),
        embedding=getattr(request.app.state, "query_embedding_port", None),
        reranker=getattr(request.app.state, "reranker_port", None),
        external=external,
    )


@router.post("/projects/{project_id}/knowledge/retrieve", response_model=RetrievalResponseDTO)
@guarded
def retrieve(project_id: UUID, payload: RetrievalRequestDTO, request: Request):
    r = repo(request)
    query = KnowledgeRetrievalQuery.model_validate(
        dict(payload.model_dump(mode="json"), project_id=str(project_id))
    )
    return service(request, r).retrieve(query)


@router.get("/retrieval-runs/{id}", response_model=RetrievalResponseDTO)
@guarded
def retrieval_run(id: UUID, request: Request):
    return repo(request).scoped_saved_response(str(id))


@router.get("/evidence-packs/{id}", response_model=EvidencePack)
@guarded
def evidence_pack(id: UUID, request: Request):
    from crossborder_compliance.infrastructure.persistence import retrieval_models as g

    r = repo(request)
    with r.sessions() as s:
        pack = r.get(s, g.EvidencePackEntity, str(id))
        run_id = pack.retrieval_run_id
    return r.scoped_saved_response(run_id)["rag_context_pack"]["evidence_pack"]


@router.get("/knowledge-sufficiency/{id}", response_model=KnowledgeSufficiencyResult)
@guarded
def sufficiency(id: UUID, request: Request):
    from crossborder_compliance.infrastructure.persistence import retrieval_models as g

    r = repo(request)
    with r.sessions() as s:
        result = r.get(s, g.KnowledgeSufficiencyResultEntity, str(id))
        run_id = r.get(s, g.EvidencePackEntity, result.evidence_pack_id).retrieval_run_id
    return r.scoped_saved_response(run_id)["rag_context_pack"]["knowledge_sufficiency"]


def policy_dto(result):
    keys = ("policy_id", "policy_version_id", "version", "lifecycle", "record_version")
    return {
        **{k: result[k] for k in keys},
        "parameters": {k: v for k, v in result.items() if k not in keys},
    }


@router.post("/admin/{kind}", response_model=PolicyResponseDTO, status_code=201)
@guarded
def create_policy(kind: PolicyKind, payload: PolicyRequestDTO, request: Request):
    return policy_dto(
        repo(request).create_policy(
            KINDS[kind], payload.parameters, str(payload.policy_id) if payload.policy_id else None
        )
    )


@router.post("/admin/{kind}/versions/{id}/publish", response_model=PolicyResponseDTO)
@guarded
def publish_policy(kind: PolicyKind, id: UUID, payload: ExpectedDTO, request: Request):
    return policy_dto(
        repo(request).publish_policy(KINDS[kind], str(id), payload.expected_record_version)
    )


@router.get("/admin/{kind}/{id}", response_model=PolicyResponseDTO)
@guarded
def get_policy(kind: PolicyKind, id: UUID, request: Request):
    from crossborder_compliance.infrastructure.persistence import retrieval_models as g

    r = repo(request)
    r.admin()
    with r.sessions() as s:
        row = r.get(s, g.POLICY_MODELS[KINDS[kind]], str(id))
        return policy_dto(
            dict(row.payload_json, lifecycle=row.lifecycle, record_version=row.record_version)
        )


@router.post("/admin/wiki", response_model=NavigationResponseDTO, status_code=201)
@guarded
def generate_wiki(payload: WikiRequestDTO, request: Request):
    generator = getattr(request.app.state, "wiki_generation_port", DeterministicWikiGenerator())
    return {
        "result": repo(request).generate_wiki(
            payload.title, tuple(str(v) for v in payload.knowledge_version_ids), generator
        )
    }


@router.post("/admin/wiki/{id}/{action}", response_model=NavigationResponseDTO)
@guarded
def wiki_action(
    id: UUID,
    action: Literal["validate", "submit-review", "approve", "publish"],
    payload: ExpectedDTO,
    request: Request,
):
    return {"result": repo(request).wiki_action(str(id), action, payload.expected_record_version)}


@router.get("/projects/{project_id}/wiki/{page_id}", response_model=NavigationResponseDTO)
@guarded
def runtime_wiki(project_id: UUID, page_id: UUID, analysis_snapshot_id: UUID, request: Request):
    r = repo(request)
    scope = KnowledgeScopeResolver(r, r.context).resolve(
        str(project_id), snapshot_id=str(analysis_snapshot_id)
    )
    return {"result": r.runtime_wiki(scope, str(page_id))}


@router.post("/admin/knowledge-graph/{kind}", response_model=NavigationResponseDTO, status_code=201)
@guarded
def create_graph(kind: Literal["node", "edge"], payload: GraphRequestDTO, request: Request):
    return {"result": repo(request).create_graph(kind, payload.parameters)}


@router.post("/admin/knowledge-graph/{kind}/{id}/{action}", response_model=NavigationResponseDTO)
@guarded
def graph_action(
    kind: Literal["node", "edge"],
    id: UUID,
    action: Literal["submit-review", "approve"],
    payload: ExpectedDTO,
    request: Request,
):
    return {
        "result": repo(request).graph_action(kind, str(id), action, payload.expected_record_version)
    }
