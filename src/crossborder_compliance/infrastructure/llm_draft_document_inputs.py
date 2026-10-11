"""Authorized real parse inputs in an exact DRAFT preparation, never a Snapshot."""

import json
from uuid import UUID, uuid4

from sqlalchemy import select

from crossborder_compliance.domain.llm_gateway import AuthorizedInput, GatewayDenied, InputReference
from crossborder_compliance.infrastructure.persistence.candidate_governance_models import (
    CandidatePreparationDocumentPinEntity,
    CandidatePreparationEntity,
)
from crossborder_compliance.infrastructure.persistence.document_models import (
    ProjectVersionDocumentLinkEntity,
)
from crossborder_compliance.infrastructure.persistence.models import ProjectVersionEntity


class DraftDocumentInput:
    def __init__(self, configuration, repository, preparation_id, fact_types=()):
        self.configuration, self.repository = configuration, repository
        self.preparation_id, self.fact_types = preparation_id, tuple(fact_types)
        self.bound = None

    def bind(self, run_id, nodes):
        run = self.repository.get_parse_run(run_id)
        if run is None:
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        version_id = UUID(run["document_version_id"])
        with self.configuration.sessions() as s, s.begin():
            preparation = s.get(CandidatePreparationEntity, str(self.preparation_id))
            if (
                not preparation
                or preparation.tenant_id != self.configuration.tenant
                or preparation.status != "PREPARING"
            ):
                raise GatewayDenied("CANDIDATE_PREPARATION_STALE")
            existing = s.scalar(
                select(CandidatePreparationDocumentPinEntity).where(
                    CandidatePreparationDocumentPinEntity.tenant_id == self.configuration.tenant,
                    CandidatePreparationDocumentPinEntity.candidate_preparation_id
                    == str(self.preparation_id),
                    CandidatePreparationDocumentPinEntity.document_version_id == str(version_id),
                )
            )
            if existing and existing.parse_run_id != str(run_id):
                raise GatewayDenied("CANDIDATE_PREPARATION_PIN_IMMUTABLE")
            if not existing:
                s.add(
                    CandidatePreparationDocumentPinEntity(
                        preparation_document_pin_id=str(uuid4()),
                        tenant_id=self.configuration.tenant,
                        candidate_preparation_id=str(self.preparation_id),
                        document_version_id=str(version_id),
                        parse_run_id=str(run_id),
                    )
                )
        self.bound = InputReference(
            resource_type="DOCUMENT_PARSE_RUN", resource_id=run_id, version_id=version_id
        )
        return self.bound

    def load(self, context, project_id, refs):
        if refs != (self.bound,) or context.tenant_id != self.configuration.context.tenant_id:
            raise LookupError("document input not found")
        with self.configuration.sessions() as s:
            preparation = s.get(CandidatePreparationEntity, str(self.preparation_id))
            version = (
                s.get(ProjectVersionEntity, preparation.project_version_id) if preparation else None
            )
            if (
                not preparation
                or not version
                or preparation.tenant_id != str(context.tenant_id)
                or version.tenant_id != str(context.tenant_id)
                or version.project_id != str(project_id)
                or version.status != "DRAFT"
            ):
                raise LookupError("document input not found")
            pin = s.scalar(
                select(CandidatePreparationDocumentPinEntity).where(
                    CandidatePreparationDocumentPinEntity.tenant_id == str(context.tenant_id),
                    CandidatePreparationDocumentPinEntity.candidate_preparation_id
                    == str(self.preparation_id),
                    CandidatePreparationDocumentPinEntity.document_version_id
                    == str(self.bound.version_id),
                    CandidatePreparationDocumentPinEntity.parse_run_id
                    == str(self.bound.resource_id),
                )
            )
            link = s.scalar(
                select(ProjectVersionDocumentLinkEntity.link_id).where(
                    ProjectVersionDocumentLinkEntity.tenant_id == str(context.tenant_id),
                    ProjectVersionDocumentLinkEntity.project_version_id
                    == version.project_version_id,
                    ProjectVersionDocumentLinkEntity.document_version_id
                    == str(self.bound.version_id),
                )
            )
            if not pin or not link:
                raise LookupError("document input not found")
        nodes = self.repository.list_structure(self.bound.resource_id)
        if sum(len(n.get("original_text") or "") for n in nodes) > 200_000:
            raise GatewayDenied("DOCUMENT_SEMANTIC_INPUT_TOO_LARGE")
        return (
            AuthorizedInput(
                ref=self.bound,
                tenant_id=context.tenant_id,
                project_id=project_id,
                required_scopes=("document:read",),
                texts=(
                    json.dumps(
                        {
                            "allowed_fact_types": self.fact_types,
                            "source_nodes": [
                                {
                                    "source_node_id": n["structure_node_id"],
                                    "text": n.get("original_text") or n.get("normalized_text"),
                                }
                                for n in nodes
                                if n.get("original_text") or n.get("normalized_text")
                            ],
                        }
                    ),
                ),
            ),
        )
