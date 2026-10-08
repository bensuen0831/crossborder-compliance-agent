from datetime import date
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from test_phase1c_model_registry import _ctx, _seed_tenant, _sf

from crossborder_compliance.application.model_control_services import ModelControlService
from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.domain.model_control import ControlTransition, ModelDraft, ProviderDraft
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_gateway_http import check_endpoint
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataOptimisticConcurrencyError,
)
from crossborder_compliance.infrastructure.persistence.model_control import (
    PostgresModelControlRepository,
)

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def control(tmp_path):
    sf, tenant = _sf(), uuid4()
    _seed_tenant(sf, tenant)
    ctx = _ctx(tenant)
    repo = PostgresModelControlRepository(sf, ctx)
    store = EncryptedFileSecretStore(tmp_path / "secrets", Fernet.generate_key(), tenant)
    service = ModelControlService(repo, ctx, store, check_endpoint)
    return sf, tenant, repo, store, service


def provider_request(**values):
    return ProviderDraft(
        code=uuid4().hex,
        display_name="Private protocol endpoint",
        base_url="http://127.0.0.1:19999/v1",
        deployment_class="PRIVATE_CLOUD",
        trust_level="APPROVED",
        data_boundary="TENANT",
        effective_from=date.today(),
        **values,
    )


def publish(sf, tenant, kind, result):
    key = "provider_version_id" if kind == "PROVIDER" else "deployment_id"
    for status, actor in (
        ("PENDING_REVIEW", "submitter"),
        ("APPROVED", "independent-reviewer"),
        ("ACTIVE", "publisher"),
    ):
        ctx = RepositoryContext.user(
            tenant, actor, {"metadata:admin", "metadata:review", "metadata:publish"}
        )
        result = PostgresModelControlRepository(sf, ctx).transition(
            kind,
            UUID(result[key]),
            ControlTransition(
                target_status=status, expected_record_version=result["record_version"]
            ),
        )
    return result


def configured_model(sf, tenant, repo, provider, remote="shared-name"):
    return repo.save_model(
        UUID(provider["provider_id"]),
        ModelDraft(
            provider_version_id=provider["provider_version_id"],
            remote_model_name=remote,
            display_name="Governed model",
            capabilities=("TEXT", "STRUCTURED_OUTPUT", "EMBEDDING"),
            operations=("chat", "structured_output", "embedding", "health_check"),
            max_output_tokens=4096,
            embedding_dimension=3,
            effective_from=date.today(),
        ),
    )


def test_multiple_provider_instances_multiple_models_same_remote_name(control):
    sf, tenant, repo, store, service = control
    providers = [
        publish(
            sf,
            tenant,
            "PROVIDER",
            service.save_provider(provider_request(credential="private-test-secret")),
        )
        for _ in range(2)
    ]
    for provider in providers:
        for name in ("shared-name", "second-name"):
            publish(sf, tenant, "MODEL", configured_model(sf, tenant, repo, provider, name))
        assert len(repo.list_models(UUID(provider["provider_id"]))) == 2
    assert len(service.providers()) == 2
    with sf() as s:
        versions = s.scalars(
            select(m.ModelProviderVersionEntity).where(
                m.ModelProviderVersionEntity.tenant_id == str(tenant)
            )
        ).all()
        assert len({v.secret_ref for v in versions}) == 2
        assert all(store.resolve(v.secret_ref) == "private-test-secret" for v in versions)
        assert all("private-test-secret" not in str(v.endpoint_config_json) for v in versions)
    assert "secret_ref" not in str(service.providers())
    assert "private-test-secret" not in str(service.providers())


def test_secret_rotation_append_version_preserves_old_reference(control):
    sf, tenant, repo, store, service = control
    first = publish(
        sf, tenant, "PROVIDER", service.save_provider(provider_request(credential="first-key"))
    )
    provider = repo.require_provider(UUID(first["provider_id"]))
    new = service.save_provider(
        provider_request(
            provider_id=provider.provider_id,
            expected_record_version=provider.record_version,
            credential="second-key",
        )
    )
    assert new["provider_version"] == 2
    with sf() as s:
        old = s.get(m.ModelProviderVersionEntity, first["provider_version_id"])
        newer = s.get(m.ModelProviderVersionEntity, new["provider_version_id"])
        assert old.secret_ref != newer.secret_ref
        assert store.resolve(old.secret_ref) == "first-key"
        assert store.resolve(newer.secret_ref) == "second-key"


def test_editing_unpublished_provider_retains_write_only_secret(control):
    sf, tenant, repo, store, service = control
    first = service.save_provider(provider_request(credential="draft-only-key"))
    provider = repo.require_provider(UUID(first["provider_id"]))
    second = service.save_provider(
        provider_request(
            provider_id=provider.provider_id, expected_record_version=provider.record_version
        )
    )
    assert second["secret_configured"]
    with sf() as s:
        row = s.get(m.ModelProviderVersionEntity, second["provider_version_id"])
        assert store.resolve(row.secret_ref) == "draft-only-key"


def test_current_authorization_and_cross_tenant_fail_closed(control):
    sf, tenant, repo, store, service = control
    provider = service.save_provider(provider_request())
    other = uuid4()
    outsider = PostgresModelControlRepository(sf, _ctx(other))
    with pytest.raises(GatewayDenied):
        outsider.list_models(UUID(provider["provider_id"]))
    ordinary = ModelControlService(
        repo, RepositoryContext.user(tenant, "user"), store, check_endpoint
    )
    with pytest.raises(PermissionError):
        ordinary.save_provider(provider_request(credential="never-written"))
    assert not list(store.root.iterdir())


def test_external_private_endpoint_rejected_before_secret_write(control):
    sf, tenant, repo, store, service = control
    request = provider_request(credential="never-written").model_copy(
        update={"base_url": "https://127.0.0.1/v1", "deployment_class": "EXTERNAL"}
    )
    with pytest.raises(GatewayDenied, match="MODEL_ENDPOINT_INVALID"):
        service.save_provider(request)
    assert not list(store.root.iterdir())


def test_optimistic_configuration_conflict(control):
    sf, tenant, repo, store, service = control
    provider = service.save_provider(provider_request())
    with pytest.raises(MetadataOptimisticConcurrencyError):
        service.save_provider(
            provider_request(provider_id=provider["provider_id"], expected_record_version=999)
        )


def test_published_model_configuration_is_immutable(control):
    sf, tenant, repo, store, service = control
    provider = publish(sf, tenant, "PROVIDER", service.save_provider(provider_request()))
    model = publish(sf, tenant, "MODEL", configured_model(sf, tenant, repo, provider))
    with pytest.raises(Exception, match="immutable"):
        with sf() as s, s.begin():
            deployment = s.get(m.ModelDeploymentEntity, model["deployment_id"])
            deployment.configuration_json = {"remote_model_name": "unexpected-latest"}


def test_independent_review_is_required(control):
    sf, tenant, repo, store, service = control
    first = service.save_provider(provider_request())
    pending = repo.transition(
        "PROVIDER",
        UUID(first["provider_version_id"]),
        ControlTransition(target_status="PENDING_REVIEW", expected_record_version=1),
    )
    with pytest.raises(GatewayDenied, match="INDEPENDENT_REVIEW_REQUIRED"):
        repo.transition(
            "PROVIDER",
            UUID(first["provider_version_id"]),
            ControlTransition(
                target_status="APPROVED", expected_record_version=pending["record_version"]
            ),
        )


def test_disable_is_current_revocation_and_requires_matching_version(control):
    sf, tenant, repo, store, service = control
    provider = service.save_provider(provider_request())
    result = repo.set_enabled("PROVIDER", UUID(provider["provider_id"]), False, 1)
    assert not result["enabled"]
    with pytest.raises(MetadataOptimisticConcurrencyError):
        repo.set_enabled("PROVIDER", UUID(provider["provider_id"]), True, 1)
