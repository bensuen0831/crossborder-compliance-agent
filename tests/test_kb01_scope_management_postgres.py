"""Managed scope uses the existing KnowledgeBinding and independent publication owners."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from test_kb01_taxonomy_postgres import mutation
from test_phase1f_postgres import draft, ingest, inputs
from test_phase1f_postgres import fixture as fixture

from crossborder_compliance.application.knowledge_document_management import (
    KnowledgeDocumentManagementService,
)
from crossborder_compliance.domain.knowledge_management import CreateManagedKnowledgeBinding
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.knowledge_document_management import (
    PostgresKnowledgeDocumentManagement,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)

pytestmark = pytest.mark.runtime_smoke
GRANTS = {
    "knowledge:document:" + action
    for action in ("read", "bind", "validate", "submit-review", "approve", "publish")
}


def service(f, actor="scope-contributor", scopes=None, tenant=None):
    context = RepositoryContext.user(
        UUID(tenant or f["tenant"]), actor, GRANTS if scopes is None else scopes
    )
    return KnowledgeDocumentManagementService(
        PostgresKnowledgeDocumentManagement(f["sf"], context), context
    )


def command(f, version, **values):
    return CreateManagedKnowledgeBinding(
        **mutation(version["record_version"]).model_dump(),
        scope_type="GLOBAL",
        dimensions={"jurisdiction": (UUID(f["juri"]),)},
        **values,
    )


def test_scope_binding_unblocks_quality_but_still_requires_independent_human_publication(fixture):
    f = fixture
    version = draft(f)
    ingest(f, version, inputs(f, bindings=[]))
    identity = UUID(version["knowledge_version_id"])
    current = f["repo"].get_version(str(identity))
    blocked = service(f).mutate("VALIDATE", identity, mutation(current["record_version"]))
    assert blocked["lifecycle"] == "INGESTED"
    before = service(f).scope_bindings(identity)
    assert before["bindings"] == []
    result = service(f).bind(identity, command(f, current))
    assert result["binding"]["provenance"]["submitted_by"] == "scope-contributor"
    assert result["binding"]["review_status"] == "PENDING"
    validated = service(f).mutate("VALIDATE", identity, mutation(result["record_version"]))
    assert validated["lifecycle"] == "VALIDATED"
    pending = service(f, "submitter").mutate(
        "SUBMIT_REVIEW", identity, mutation(validated["record_version"])
    )
    with pytest.raises(ValueError, match="independent human reviewer"):
        service(f).mutate("APPROVE", identity, mutation(pending["record_version"]))
    approved = service(f, "independent-reviewer").mutate(
        "APPROVE", identity, mutation(pending["record_version"])
    )
    published = service(f, "publisher").mutate(
        "PUBLISH", identity, mutation(approved["record_version"])
    )
    assert published["lifecycle"] == "ACTIVE"
    assert service(f).scope_bindings(identity)["bindings"][0]["review_status"] == "APPROVED"
    current = f["repo"].get_version(str(identity))
    with pytest.raises(KnowledgeManagementConflict, match="REVIEWED_KNOWLEDGE_BINDING_IMMUTABLE"):
        service(f).bind(identity, command(f, current))


def test_scope_binding_idempotency_cas_and_server_actor_are_not_caller_owned(fixture):
    f = fixture
    version = draft(f)
    identity = UUID(version["knowledge_version_id"])
    request = command(f, version)
    first = service(f).bind(identity, request)
    assert service(f).bind(identity, request) == first
    with pytest.raises(KnowledgeManagementConflict, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        service(f).bind(identity, request.model_copy(update={"reason": "different payload"}))
    with pytest.raises(KnowledgeManagementConflict, match="VERSION_CONFLICT"):
        service(f).bind(identity, request.model_copy(update={"idempotency_key": str(uuid4())}))
    with pytest.raises(ValidationError):
        CreateManagedKnowledgeBinding.model_validate(
            {**request.model_dump(), "provenance": {"submitted_by": "forged"}}
        )
    with pytest.raises(ValidationError):
        CreateManagedKnowledgeBinding.model_validate(
            {**request.model_dump(), "dimensions": {"country_hardcode": [str(uuid4())]}}
        )


def test_scope_options_are_paged_canonical_and_tenant_scoped(fixture):
    f = fixture
    options = service(f).scope_options(dimension="jurisdiction", page_size=1)
    assert options["total"] >= 1
    assert options["items"][0]["object_id"] == f["juri"]
    assert service(f, tenant=str(uuid4())).scope_options(dimension="jurisdiction")["total"] == 0
    with pytest.raises(PermissionError):
        service(f, scopes={"knowledge:admin"}).scope_options(dimension="jurisdiction")
    version = draft(f)
    with pytest.raises(LookupError):
        service(f, tenant=str(uuid4())).scope_bindings(UUID(version["knowledge_version_id"]))


def test_scope_http_channel_does_not_accept_actor_or_skip_canonical_binding_owner(fixture):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.routes.knowledge_document_management import router

    f = fixture
    version = draft(f)
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)

    @app.middleware("http")
    async def host(request, call_next):
        request.state.repository_context = service(f).context
        return await call_next(request)

    prefix = "/api/v1/admin/knowledge-management"
    with TestClient(app) as client:
        assert client.get(prefix + "/scope-options?dimension=jurisdiction").status_code == 200
        url = prefix + f"/documents/versions/{version['knowledge_version_id']}/scope-bindings"
        payload = command(f, version).model_dump(mode="json")
        assert client.post(url, json={**payload, "actor_id": "spoof"}).status_code == 422
        created = client.post(url, json=payload)
        assert created.status_code == 201, created.text
        assert created.json()["binding"]["provenance"]["submitted_by"] == "scope-contributor"
        assert len(client.get(url).json()["bindings"]) == 1
