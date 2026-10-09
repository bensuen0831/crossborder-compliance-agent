from uuid import UUID

import pytest
from phase1kb_http_servers import local_provider
from test_phase1kb_control_postgres import configured_model, provider_request, publish
from test_phase1kb_control_postgres import control as control

from crossborder_compliance.infrastructure.llm_provider_inspection import ProviderInspection

pytestmark = pytest.mark.runtime_smoke


@pytest.mark.parametrize(
    "preset", ["OPENAI_GPT", "DEEPSEEK", "QWEN", "GLM", "OTHER_OPENAI_COMPATIBLE"]
)
def test_presets_real_http_same_protocol_no_business_branch(control, preset):
    sf, tenant, repo, store, service = control
    with local_provider(("shared-name", "second-name")) as (url, calls):
        request = provider_request(
            credential="ci-local-credential", vendor_preset=preset
        ).model_copy(update={"base_url": url})
        provider = publish(sf, tenant, "PROVIDER", service.save_provider(request))
        inspector = ProviderInspection(repo, store)
        found = inspector.connection_test(UUID(provider["provider_version_id"]))
        assert found == {"status": "HEALTHY", "candidate_models": ("shared-name", "second-name")}
        assert repo.list_models(UUID(provider["provider_id"])) == []  # discovery never publishes
        model = publish(sf, tenant, "MODEL", configured_model(sf, tenant, repo, provider))
        for operation in ("chat", "structured_output", "embedding"):
            assert (
                inspector.model_test(UUID(model["deployment_id"]), operation)["status"] == "HEALTHY"
            )
        assert {call[1] for call in calls} == {
            "health_check",
            "chat",
            "structured_output",
            "embedding",
        }
        assert repo.list_models(UUID(provider["provider_id"]))[0]["health_status"] == "HEALTHY"


def test_real_http_bad_credential_sanitized(control):
    sf, tenant, repo, store, service = control
    with local_provider() as (url, calls):
        provider = service.save_provider(
            provider_request(credential="incorrect-private-credential").model_copy(
                update={"base_url": url}
            )
        )
        result = ProviderInspection(repo, store).connection_test(
            UUID(provider["provider_version_id"])
        )
        assert result["status"] == "AUTHENTICATION_FAILED"
        assert "incorrect-private-credential" not in str(result)
        assert calls == []


def test_real_http_timeout_unavailable_and_unsupported(control):
    sf, tenant, repo, store, service = control
    with local_provider(("shared-name",), delay=0.1) as (url, calls):
        provider = publish(
            sf,
            tenant,
            "PROVIDER",
            service.save_provider(
                provider_request(credential="ci-local-credential").model_copy(
                    update={"base_url": url, "timeout_seconds": 0.01}
                )
            ),
        )
        model = publish(sf, tenant, "MODEL", configured_model(sf, tenant, repo, provider))
        inspection = ProviderInspection(repo, store)
        assert inspection.model_test(UUID(model["deployment_id"]), "chat")["status"] == "TIMEOUT"
        assert (
            inspection.model_test(UUID(model["deployment_id"]), "rerank")["status"]
            == "CAPABILITY_UNSUPPORTED"
        )
    assert (
        inspection.connection_test(UUID(provider["provider_version_id"]))["status"]
        == "ENDPOINT_UNREACHABLE"
    )


def test_missing_secret_capability_is_not_fake_health(control):
    sf, tenant, repo, store, service = control
    with local_provider() as (url, calls):
        provider = service.save_provider(
            provider_request(credential="ci-local-credential").model_copy(update={"base_url": url})
        )
        result = ProviderInspection(repo, None).connection_test(
            UUID(provider["provider_version_id"])
        )
        assert result["status"] == "SECRET_UNAVAILABLE"
        assert not calls
