from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from phase1kb_http_servers import local_provider
from test_phase1kb_control_postgres import control as control

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.model_providers import router

pytestmark = pytest.mark.runtime_smoke


def client_for(control, context=None):
    sf, tenant, repo, store, service = control
    app = FastAPI()
    app.include_router(router)
    app.state.knowledge_session_factory = sf
    app.state.llm_secret_store_factory = lambda ctx: store
    app.dependency_overrides[get_repository_context] = lambda: context or repo.context
    return TestClient(app)


def test_typed_provider_api_write_only_secret_real_http(control, caplog):
    client = client_for(control)
    with local_provider() as (url, calls):
        command = dict(
            code=uuid4().hex,
            display_name="API endpoint",
            base_url=url,
            trust_level="APPROVED",
            data_boundary="TENANT",
            deployment_class="PRIVATE_CLOUD",
            credential="ci-local-credential",
            effective_from=date.today().isoformat(),
        )
        response = client.post("/api/v1/admin/model-providers", json=command)
        assert response.status_code == 201, response.json()
        provider = response.json()
        assert provider["secret_configured"]
        assert "ci-local-credential" not in response.text
        assert "secret_ref" not in response.text
        listing = client.get("/api/v1/admin/model-providers")
        assert listing.status_code == 200
        assert "ci-local-credential" not in listing.text
        for operation in ("test-connection", "discover-models"):
            result = client.post(
                f"/api/v1/admin/model-providers/versions/{provider['provider_version_id']}/{operation}"
            )
            assert result.json() == {"status": "HEALTHY", "candidate_models": ["A1", "A2"]}
        assert len(calls) == 2
    assert "ci-local-credential" not in caplog.text


def test_validation_does_not_echo_secret_or_client_authority(control):
    client = client_for(control)
    credential = "validation-credential-must-never-echo"
    response = client.post(
        "/api/v1/admin/model-providers", json={"credential": credential, "tenant_id": str(uuid4())}
    )
    assert response.status_code == 422
    assert credential not in response.text
    assert response.json()["detail"] == "MODEL_CONTROL_REQUEST_INVALID"


def test_ordinary_user_cannot_manage_providers(control):
    tenant = control[1]
    response = client_for(control, RepositoryContext.user(tenant, "ordinary")).get(
        "/api/v1/admin/model-providers"
    )
    assert response.status_code == 404
