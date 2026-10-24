"""Typed clause lineage in canonical KnowledgeTranslationEntity, without another store."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
    hash_value,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)

ALIGNMENT_SCHEMA = "KB01_CLAUSE_TRANSLATION_ALIGNMENT_V1"


def text_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PostgresKnowledgeTranslationAlignment:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant_id = str(context.tenant_id)
        self.owner = PostgresKnowledgeRepository(sessions, context)

    def _version(self, session, identity, expected=None):
        row = self.owner.get(session, k.KnowledgeDocumentVersionEntity, identity, True)
        if expected is not None and row.record_version != expected:
            raise KnowledgeManagementConflict("KNOWLEDGE_VERSION_CONFLICT")
        if not row.content_hash or row.lifecycle in {"DRAFT", "ARCHIVED"}:
            raise ValueError("TRANSLATION_REQUIRES_INGESTED_CONTENT")
        return row

    def _pair(self, session, pair, source, target):
        nodes = []
        for identity, version in [(pair.source_node_id, source), (pair.target_node_id, target)]:
            node = self.owner.get(session, k.KnowledgeStructureNodeEntity, identity)
            if node.knowledge_version_id != version.knowledge_version_id:
                raise ValueError("TRANSLATION_NODE_VERSION_MISMATCH")
            citation = self.owner.get(session, b.CitationEntity, node.citation_id)
            evidence = self.owner.get(session, b.EvidenceReferenceEntity, citation.evidence_id)
            provenance = json.loads(evidence.source_ref)
            if (
                provenance.get("knowledge_version_id") != version.knowledge_version_id
                or provenance.get("structure_node_id") != node.structure_node_id
                or citation.locator != node.canonical_locator
                or citation.quote_hash != hash_value(node.original_text)
            ):
                raise ValueError("TRANSLATION_CITATION_VERSION_MISMATCH")
            nodes.append(node)
        a, target_node = nodes
        return {
            "source_node_id": a.structure_node_id,
            "target_node_id": target_node.structure_node_id,
            "source_citation_id": a.citation_id,
            "target_citation_id": target_node.citation_id,
            "source_locator": a.canonical_locator,
            "target_locator": target_node.canonical_locator,
            "source_text_sha256": text_digest(a.original_text),
            "target_text_sha256": text_digest(target_node.original_text),
        }

    @staticmethod
    def _view(row):
        p = row.provenance_json
        return {
            "translation_id": row.translation_id,
            "source_version_id": row.knowledge_version_id,
            "target_version_id": p["target_version_id"],
            "source_language": row.source_language,
            "target_language": row.target_language,
            "source_content_hash": p["source_content_hash"],
            "target_content_hash": p["target_content_hash"],
            "pairs": p["pairs"],
            "translation_method": row.translation_method,
            "review_status": row.review_status,
            "record_version": row.record_version,
            "submitted_by": p["submitted_by"],
            "submitted_at": p["submitted_at"],
            "reviewer": row.reviewer,
            "reviewed_at": p.get("reviewed_at"),
            "reason": p["reason"],
            "review_reason": p.get("review_reason"),
            "official_evidence": False,
        }

    def create(self, request):
        require_management_permission(self.context, "translation:write")
        with self.sessions() as s, s.begin():
            # Stable lock ordering avoids reciprocal source/target deadlocks.
            versions = {
                identity: self._version(s, identity, expected)
                for identity, expected in sorted(
                    [
                        (request.source_version_id, request.expected_source_record_version),
                        (request.target_version_id, request.expected_target_record_version),
                    ],
                    key=lambda item: str(item[0]),
                )
            }
            source, target = (
                versions[request.source_version_id],
                versions[request.target_version_id],
            )
            if source.language == target.language:
                raise ValueError("TRANSLATION_REQUIRES_DISTINCT_LANGUAGES")
            pairs = [self._pair(s, pair, source, target) for pair in request.pairs]
            row = k.KnowledgeTranslationEntity(
                translation_id=str(uuid4()),
                tenant_id=self.tenant_id,
                knowledge_version_id=source.knowledge_version_id,
                source_language=source.language,
                target_language=target.language,
                translated_text_ref="knowledge-version://" + target.knowledge_version_id,
                translation_method="HUMAN",
                review_status="PENDING",
                version=1,
                provenance_json={
                    "schema": ALIGNMENT_SCHEMA,
                    "target_version_id": target.knowledge_version_id,
                    "source_content_hash": source.content_hash,
                    "target_content_hash": target.content_hash,
                    "pairs": pairs,
                    "submitted_by": self.context.permission.actor_id,
                    "submitted_at": datetime.now(UTC).isoformat(),
                    "reason": request.reason,
                },
            )
            s.add(row)
            s.flush()
            return self._view(row)

    def list(self, source_version_id, *, page=1, page_size=25):
        require_management_permission(self.context, "translation:read")
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("INVALID_PAGINATION")
        with self.sessions() as s:
            self.owner.get(s, k.KnowledgeDocumentVersionEntity, source_version_id)
            query = select(k.KnowledgeTranslationEntity).where(
                k.KnowledgeTranslationEntity.tenant_id == self.tenant_id,
                k.KnowledgeTranslationEntity.knowledge_version_id == str(source_version_id),
                k.KnowledgeTranslationEntity.provenance_json["schema"].as_string()
                == ALIGNMENT_SCHEMA,
            )
            total = s.scalar(select(func.count()).select_from(query.subquery()))
            rows = s.scalars(
                query.order_by(k.KnowledgeTranslationEntity.translation_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [self._view(row) for row in rows],
            }

    def review(self, identity, request):
        require_management_permission(self.context, "translation:approve")
        with self.sessions() as s, s.begin():
            row = self.owner.get(s, k.KnowledgeTranslationEntity, identity, True)
            p = row.provenance_json
            if p.get("schema") != ALIGNMENT_SCHEMA:
                raise ValueError("LEGACY_TRANSLATION_USE_CANONICAL_REVIEW")
            if (
                row.record_version != request.expected_record_version
                or row.review_status != "PENDING"
            ):
                raise KnowledgeManagementConflict("TRANSLATION_REVIEW_VERSION_CONFLICT")
            if (
                self.context.permission.system
                or p["submitted_by"] == self.context.permission.actor_id
            ):
                raise KnowledgeManagementConflict("INDEPENDENT_TRANSLATION_REVIEW_REQUIRED")
            versions = {
                key: self._version(s, key)
                for key in sorted([row.knowledge_version_id, p["target_version_id"]])
            }
            source, target = versions[row.knowledge_version_id], versions[p["target_version_id"]]
            if (
                source.content_hash != p["source_content_hash"]
                or target.content_hash != p["target_content_hash"]
            ):
                raise KnowledgeManagementConflict("TRANSLATION_CONTENT_CHANGED")
            from crossborder_compliance.domain.knowledge_translation_alignment import (
                ClauseTranslationPair,
            )

            for pair in p["pairs"]:
                current = self._pair(
                    s,
                    ClauseTranslationPair(
                        source_node_id=pair["source_node_id"],
                        target_node_id=pair["target_node_id"],
                    ),
                    source,
                    target,
                )
                if current != pair:
                    raise KnowledgeManagementConflict("TRANSLATION_ALIGNMENT_CHANGED")
            row.review_status = "APPROVED" if request.action == "APPROVE" else "REJECTED"
            row.reviewer = self.context.permission.actor_id
            row.record_version += 1
            row.provenance_json = {
                **p,
                "reviewed_at": datetime.now(UTC).isoformat(),
                "review_reason": request.reason,
            }
            s.flush()
            return self._view(row)
