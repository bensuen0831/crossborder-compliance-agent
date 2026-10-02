"""Consume existing Phase 1G packs through its scope-revalidating read contract."""

from sqlalchemy import select

from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)


class ExistingClassificationEvidence:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context

    def references(self, project_id, snapshot_id, item_id):
        """Never run a new retrieval or expand scope; only the caller's exact-subject packs."""
        if item_id is None:
            return (), (), ()
        with self.sessions() as s:
            rows = s.scalars(
                select(g.RetrievalRunEntity).where(
                    g.RetrievalRunEntity.tenant_id == str(self.context.tenant_id),
                    g.RetrievalRunEntity.project_id == str(project_id),
                    g.RetrievalRunEntity.analysis_snapshot_id == str(snapshot_id),
                    g.RetrievalRunEntity.owner_actor_id == self.context.permission.actor_id,
                    g.RetrievalRunEntity.status == "COMPLETED",
                )
            ).all()
            identifiers = [
                row.retrieval_run_id
                for row in rows
                if row.query_json.get("subject_type") == "DATA_ITEM"
                and row.query_json.get("subject_id") == str(item_id)
            ]
        source = PostgresRetrievalRepository(self.sessions, self.context)
        evidence_ids, evidence_types, pack_ids = set(), set(), set()
        for ident in identifiers:
            response = source.scoped_saved_response(ident)
            rag = response.get("rag_context_pack")
            if not rag or not rag["evidence_pack"]["items"]:
                continue
            pack = rag["evidence_pack"]
            citation_ids = [item["citation_id"] for item in pack["items"]]
            with self.sessions() as s:
                refs = s.scalars(
                    select(b.EvidenceReferenceEntity)
                    .join(
                        b.CitationEntity,
                        b.CitationEntity.evidence_id == b.EvidenceReferenceEntity.evidence_id,
                    )
                    .where(
                        b.EvidenceReferenceEntity.tenant_id == str(self.context.tenant_id),
                        b.CitationEntity.tenant_id == str(self.context.tenant_id),
                        b.CitationEntity.citation_id.in_(citation_ids),
                        b.EvidenceReferenceEntity.validation_status.in_(["VALID", "VALIDATED"]),
                    )
                ).all()
                evidence_ids.update(ref.evidence_id for ref in refs)
                evidence_types.update(ref.evidence_type for ref in refs)
                if refs:
                    pack_ids.add(pack["evidence_pack_id"])
        return tuple(sorted(evidence_ids)), tuple(sorted(evidence_types)), tuple(sorted(pack_ids))
