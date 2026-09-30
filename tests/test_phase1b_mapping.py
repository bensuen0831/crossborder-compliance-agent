from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from crossborder_compliance.application.dtos import ProjectDTO
from crossborder_compliance.domain.contracts import DataItemDTO
from crossborder_compliance.infrastructure.persistence.mappers import DataItemMapper, ProjectMapper
from crossborder_compliance.infrastructure.persistence.models import DataItemEntity, ProjectEntity


def test_project_mapping_orm_to_domain_to_application_dto() -> None:
    now = datetime.now(timezone.utc)
    row = ProjectEntity(
        project_id=str(uuid4()),
        tenant_id=str(uuid4()),
        name="Mapping Project",
        record_version=2,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    domain = ProjectMapper.to_domain(row)
    dto = ProjectMapper.to_application(row)
    assert domain.project_id == dto.project_id
    assert isinstance(dto, ProjectDTO)
    assert dto.record_version == 2
    assert not isinstance(dto, ProjectEntity)


def test_data_item_mapping_outputs_typed_contract_not_orm() -> None:
    now = datetime.now(timezone.utc)
    row = DataItemEntity(
        data_item_id=str(uuid4()),
        tenant_id=str(uuid4()),
        project_id=str(uuid4()),
        name="Email",
        canonical_type_ref="contact.email",
        record_version=1,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    dto = DataItemMapper.to_contract(row)
    assert isinstance(dto, DataItemDTO)
    assert dto.name == "Email"
    assert not isinstance(dto, DataItemEntity)
