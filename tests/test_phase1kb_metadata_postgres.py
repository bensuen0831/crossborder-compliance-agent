from uuid import UUID, uuid4

import pytest
from test_phase1kb_control_postgres import control as control

from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)

pytestmark = pytest.mark.runtime_smoke


@pytest.mark.parametrize(
    "kind,payload",
    [
        (
            "LLM_INVOCATION_POLICY",
            {
                "allowed_triggers": {"STANDARD": ["DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED"]},
                "max_models": 3,
            },
        ),
        ("LLM_PROVIDER_PRESET", {"vendor_preset": "GENERIC_COMPATIBLE"}),
    ],
)
def test_typed_policies_use_existing_metadata_lifecycle(control, kind, payload):
    sf, tenant, repo, store, service = control
    metadata = PostgresAdminMetadataRepository(sf, repo.context)
    definition = metadata.create_definition(
        kind=kind, code=uuid4().hex, display_name="Governed configuration"
    )
    version = metadata.create_version(
        definition_id=UUID(definition["definition_id"]), payload=payload
    )
    assert version["lifecycle_status"] == "DRAFT"
    assert version["payload"] == payload


def test_usage_policy_cannot_allow_cross_tenant_or_unknown_models(control):
    sf, tenant, repo, store, service = control
    metadata = PostgresAdminMetadataRepository(sf, repo.context)
    definition = metadata.create_definition(
        kind="MODEL_USAGE_POLICY", code=uuid4().hex, display_name="Usage"
    )
    with pytest.raises(ValueError, match="USAGE_POLICY_MODEL_SCOPE_INVALID"):
        metadata.create_version(
            definition_id=UUID(definition["definition_id"]),
            payload={
                "scope_type": "TENANT",
                "allowed_model_ids": [str(uuid4())],
            },
        )
