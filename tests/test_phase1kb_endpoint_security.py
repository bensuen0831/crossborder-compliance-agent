from datetime import date

import pytest
from pydantic import ValidationError

from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.domain.metadata import validate_endpoint_config
from crossborder_compliance.domain.model_control import ProviderDraft
from crossborder_compliance.infrastructure.llm_gateway_http import check_endpoint


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://[fe80::1]/v1",
        "http://[::ffff:169.254.169.254]/v1",
        "http://metadata.google.internal/v1",
        "http://instance-data.ec2.internal/v1",
        "http://0.0.0.0/v1",
    ],
)
def test_private_deployment_does_not_authorize_metadata_service(url):
    with pytest.raises(GatewayDenied, match="MODEL_ENDPOINT_INVALID"):
        check_endpoint(url, False)


@pytest.mark.parametrize(
    "config",
    [
        {"api_key": "ci-test-value"},
        {"headers": {"Authorization": "ci-test-value"}},
        {"headers": {"X-Api-Key": "ci-test-value"}},
        {"url": "https://provider.example/v1?api_key=ci-test-value"},
    ],
)
def test_legacy_generic_metadata_cannot_store_plaintext_credentials(config):
    with pytest.raises(ValueError):
        validate_endpoint_config(config)


@pytest.mark.parametrize(
    "path", ["//other.example/secret", "/../metadata", "/%2e%2e/metadata", "/chat?token=x"]
)
def test_generic_operation_path_cannot_change_origin_or_inject_query(path):
    with pytest.raises(ValidationError, match="MODEL_OPERATION_PATH_INVALID"):
        ProviderDraft(
            code="safe",
            display_name="Safe",
            trust_level="APPROVED",
            data_boundary="TENANT",
            base_url="http://127.0.0.1:9000",
            effective_from=date.today(),
            operation_paths={"chat": path},
        )
