"""Validate F0 records inside the one canonical MetadataVersion transaction."""

import hashlib
import json
from datetime import UTC, datetime

from crossborder_compliance.domain.regulatory_acceptance import (
    ACCEPTANCE_TYPES,
    RegulatoryAcceptanceCase,
    RegulatoryExpertAuthorization,
    RegulatoryGoldReview,
    RegulatorySourceVerification,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b


def payload_digest(payload):
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def scoped(session, model, identity, tenant):
    row = session.get(model, str(identity))
    if row is None or row.tenant_id != tenant:
        raise LookupError("ACCEPTANCE_REFERENCED_RECORD_NOT_FOUND")
    return row


def version(session, identity, tenant, kind):
    row = scoped(session, m.MetadataVersionEntity, identity, tenant)
    definition = scoped(session, m.MetadataDefinitionEntity, row.definition_id, tenant)
    if definition.kind != kind or row.lifecycle_status not in {"APPROVED", "ACTIVE", "SUPERSEDED"}:
        raise ValueError("ACCEPTANCE_EXACT_APPROVED_VERSION_REQUIRED")
    if not row.approved_by or row.approved_by == row.created_by:
        raise ValueError("ACCEPTANCE_INDEPENDENT_APPROVAL_REQUIRED")
    return row, ACCEPTANCE_TYPES[kind].model_validate(row.payload_json)


def source_pin(session, pin, tenant, *, require_original=False):
    row = scoped(session, k.KnowledgeDocumentVersionEntity, pin.knowledge_version_id, tenant)
    if row.content_hash != pin.content_sha256 or row.lifecycle not in {
        "APPROVED",
        "ACTIVE",
        "SUPERSEDED",
    }:
        raise ValueError("ACCEPTANCE_SOURCE_PIN_MISMATCH")
    if require_original:
        from sqlalchemy import select

        from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
            KnowledgeBinaryAttachmentEntity as Attachment,
        )
        from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
            KnowledgeUploadSessionEntity as Upload,
        )

        upload = session.scalar(
            select(Upload)
            .join(
                Attachment,
                (Attachment.tenant_id == Upload.tenant_id)
                & (Attachment.upload_session_id == Upload.upload_session_id),
            )
            .where(
                Attachment.tenant_id == tenant,
                Attachment.knowledge_version_id == row.knowledge_version_id,
            )
        )
        if (
            upload is None
            or upload.status != "VERIFIED"
            or not row.original_artifact_ref
            or upload.content_sha256 != row.content_hash
        ):
            raise ValueError("ACCEPTANCE_AUTHORIZED_ORIGINAL_PENDING")
    for identity in pin.structure_node_ids:
        node = scoped(session, k.KnowledgeStructureNodeEntity, identity, tenant)
        if node.knowledge_version_id != row.knowledge_version_id:
            raise ValueError("ACCEPTANCE_CLAUSE_OUTSIDE_PINNED_VERSION")
    return row


def authorization(session, identity, tenant, dataset, jurisdictions):
    row, value = version(session, identity, tenant, "REGULATORY_EXPERT_AUTHORIZATION")
    today = datetime.now(UTC).date()
    if (
        value.dataset_kind != dataset
        or not set(jurisdictions) <= set(value.jurisdiction_ids)
        or row.lifecycle_status != "ACTIVE"
        or today < value.valid_from
        or value.valid_to
        and today > value.valid_to
    ):
        raise ValueError("ACCEPTANCE_EXPERT_AUTHORIZATION_NOT_CURRENT")
    return row, value


def validate_acceptance_payload(session, definition, payload):
    parsed = ACCEPTANCE_TYPES[definition.kind].model_validate(payload)
    if len(json.dumps(parsed.model_dump(mode="json"), ensure_ascii=False).encode()) > 1024**2:
        raise ValueError("ACCEPTANCE_PAYLOAD_LIMIT")
    tenant = definition.tenant_id
    if isinstance(parsed, (RegulatoryAcceptanceCase, RegulatoryExpertAuthorization)):
        if len(set(parsed.jurisdiction_ids)) != len(parsed.jurisdiction_ids):
            raise ValueError("DUPLICATE_ACCEPTANCE_JURISDICTION")
        for identity in parsed.jurisdiction_ids:
            scoped(session, b.JurisdictionEntity, identity, tenant)
    if isinstance(parsed, RegulatoryAcceptanceCase):
        for pin in parsed.source_pins:
            source_pin(
                session, pin, tenant, require_original=parsed.dataset_kind == "L2_REAL_REGULATORY"
            )
        if parsed.expected and set(parsed.expected.jurisdiction_ids) != set(
            parsed.jurisdiction_ids
        ):
            raise ValueError("ACCEPTANCE_ORACLE_JURISDICTION_MISMATCH")
        if parsed.expected and not {
            payload_digest(pin) for pin in parsed.expected.legal_source_pins
        } <= {payload_digest(pin) for pin in parsed.source_pins}:
            raise ValueError("ACCEPTANCE_ORACLE_SOURCE_OUTSIDE_CASE")
    elif isinstance(parsed, RegulatorySourceVerification):
        source_pin(
            session,
            parsed.source_pin,
            tenant,
            require_original=parsed.dataset_kind == "L2_REAL_REGULATORY",
        )
        authorization(
            session,
            parsed.expert_authorization_version_id,
            tenant,
            parsed.dataset_kind,
            (parsed.jurisdiction_id,),
        )
    elif isinstance(parsed, RegulatoryGoldReview):
        case, contents = version(
            session, parsed.case_version_id, tenant, "REGULATORY_ACCEPTANCE_CASE"
        )
        if (
            contents.expected is None
            or parsed.case_payload_sha256 != payload_digest(case.payload_json)
            or parsed.expected_semantics_sha256 != payload_digest(contents.expected)
            or parsed.dataset_kind != contents.dataset_kind
        ):
            raise ValueError("ACCEPTANCE_GOLD_EXACT_CASE_DIGEST_MISMATCH")
        authorization(
            session,
            parsed.expert_authorization_version_id,
            tenant,
            contents.dataset_kind,
            contents.jurisdiction_ids,
        )
        verified = set()
        for identity in parsed.source_verification_version_ids:
            record, verification = version(
                session, identity, tenant, "REGULATORY_SOURCE_VERIFICATION"
            )
            _, expert = authorization(
                session,
                verification.expert_authorization_version_id,
                tenant,
                contents.dataset_kind,
                (verification.jurisdiction_id,),
            )
            if (
                record.approved_by != expert.expert_actor_id
                or verification.dataset_kind != contents.dataset_kind
                or verification.jurisdiction_id not in contents.jurisdiction_ids
                or verification.effective_from > contents.analysis_as_of_date
                or verification.effective_to
                and verification.effective_to < contents.analysis_as_of_date
            ):
                raise ValueError("ACCEPTANCE_SOURCE_VERIFICATION_NOT_APPLICABLE")
            verified.add(payload_digest(verification.source_pin))
        if not {payload_digest(pin) for pin in contents.source_pins} <= verified:
            raise ValueError("ACCEPTANCE_SOURCE_VERIFICATION_INCOMPLETE")
    return parsed


def validate_acceptance_transition(session, definition, row, actor, target):
    parsed = validate_acceptance_payload(session, definition, row.payload_json)
    if target not in {"PENDING_REVIEW", "APPROVED", "ACTIVE"}:
        return
    if isinstance(parsed, RegulatoryAcceptanceCase) and (
        not parsed.source_pins or parsed.expected is None
    ):
        raise ValueError("ACCEPTANCE_CASE_NOT_READY_FOR_REVIEW")
    if isinstance(parsed, RegulatoryExpertAuthorization):
        if target == "APPROVED" and actor == parsed.expert_actor_id:
            raise ValueError("ACCEPTANCE_EXPERT_CANNOT_SELF_APPOINT")
    if isinstance(parsed, (RegulatorySourceVerification, RegulatoryGoldReview)):
        jurisdictions = (
            (parsed.jurisdiction_id,)
            if isinstance(parsed, RegulatorySourceVerification)
            else version(
                session, parsed.case_version_id, row.tenant_id, "REGULATORY_ACCEPTANCE_CASE"
            )[1].jurisdiction_ids
        )
        _, expert = authorization(
            session,
            parsed.expert_authorization_version_id,
            row.tenant_id,
            parsed.dataset_kind,
            jurisdictions,
        )
        approver = actor if target == "APPROVED" else row.approved_by
        if target in {"APPROVED", "ACTIVE"} and approver != expert.expert_actor_id:
            raise ValueError("ACCEPTANCE_APPOINTED_EXPERT_REQUIRED")
        if isinstance(parsed, RegulatoryGoldReview):
            case, _ = version(
                session, parsed.case_version_id, row.tenant_id, "REGULATORY_ACCEPTANCE_CASE"
            )
            if target == "APPROVED" and actor == case.created_by:
                raise ValueError("ACCEPTANCE_ORACLE_REQUIRES_INDEPENDENT_EXPERT")
