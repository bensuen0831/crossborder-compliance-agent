"""Exact preparation references into the existing versioned registries."""

from uuid import uuid4

from sqlalchemy import select

from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.infrastructure.persistence.candidate_governance_models import (
    CandidatePreparationEntity,
    CandidatePreparationRegistryPinEntity,
)


class PostgresCandidatePreparationPins:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context

    def list_pins(self, candidate_preparation_id):
        with self.sessions() as s:
            rows = s.scalars(
                select(CandidatePreparationRegistryPinEntity)
                .where(
                    CandidatePreparationRegistryPinEntity.tenant_id == str(self.context.tenant_id),
                    CandidatePreparationRegistryPinEntity.candidate_preparation_id
                    == str(candidate_preparation_id),
                )
                .order_by(
                    CandidatePreparationRegistryPinEntity.pin_type,
                    CandidatePreparationRegistryPinEntity.logical_key,
                )
            ).all()
            return [
                {
                    k: getattr(r, k)
                    for k in ("pin_type", "logical_key", "object_id", "version_id", "version_no")
                }
                for r in rows
            ]

    def add_pin(
        self, *, candidate_preparation_id, pin_type, logical_key, object_id, version_id, version_no
    ):
        key = str(logical_key)
        tenant = str(self.context.tenant_id)
        with self.sessions() as s, s.begin():
            preparation = s.get(CandidatePreparationEntity, str(candidate_preparation_id))
            if (
                preparation is None
                or preparation.tenant_id != tenant
                or preparation.status != "PREPARING"
            ):
                raise GatewayDenied("CANDIDATE_PREPARATION_PIN_NOT_WRITABLE")
            prior = s.scalar(
                select(CandidatePreparationRegistryPinEntity).where(
                    CandidatePreparationRegistryPinEntity.tenant_id == tenant,
                    CandidatePreparationRegistryPinEntity.candidate_preparation_id
                    == str(candidate_preparation_id),
                    CandidatePreparationRegistryPinEntity.pin_type == pin_type,
                    CandidatePreparationRegistryPinEntity.logical_key == key,
                )
            )
            value = (str(object_id), str(version_id), version_no)
            if prior:
                if (prior.object_id, prior.version_id, prior.version_no) != value:
                    raise GatewayDenied("CANDIDATE_PREPARATION_PIN_IMMUTABLE")
                return
            s.add(
                CandidatePreparationRegistryPinEntity(
                    preparation_registry_pin_id=str(uuid4()),
                    tenant_id=tenant,
                    candidate_preparation_id=str(candidate_preparation_id),
                    pin_type=pin_type,
                    logical_key=key,
                    object_id=value[0],
                    version_id=value[1],
                    version_no=value[2],
                )
            )
