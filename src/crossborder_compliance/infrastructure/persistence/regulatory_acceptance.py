"""F0 draft import, review and readiness over canonical versioned Metadata storage."""

from uuid import UUID

from crossborder_compliance.application.metadata_services import MetadataLifecycleService
from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.domain.regulatory_acceptance import ACCEPTANCE_TYPES
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.regulatory_acceptance_governance import (
    payload_digest,
    scoped,
    validate_acceptance_payload,
    validate_acceptance_transition,
)


class PostgresRegulatoryAcceptance:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant = str(context.tenant_id)
        self.repository = PostgresAdminMetadataRepository(sessions, context)
        self.lifecycle = MetadataLifecycleService(self.repository, context)

    def _view(self, s, row):
        definition = scoped(s, m.MetadataDefinitionEntity, row.definition_id, self.tenant)
        if definition.kind not in ACCEPTANCE_TYPES:
            raise LookupError("ACCEPTANCE_RECORD_NOT_FOUND")
        return {
            "definition_id": row.definition_id,
            "version_id": row.version_id,
            "kind": definition.kind,
            "code": definition.code,
            "version_no": row.version_no,
            "record_version": row.record_version,
            "lifecycle": row.lifecycle_status,
            "created_by": row.created_by,
            "approved_by": row.approved_by,
            "approved_at": row.approved_at,
            "published_at": row.published_at,
            "payload": row.payload_json,
            "payload_sha256": payload_digest(row.payload_json),
        }

    def read(self, identity):
        require_management_permission(self.context, "acceptance:read")
        with self.sessions() as s:
            return self._view(s, scoped(s, m.MetadataVersionEntity, identity, self.tenant))

    def import_draft(self, request):
        require_management_permission(self.context, "acceptance:write")
        payload = (
            ACCEPTANCE_TYPES[request.kind].model_validate(request.payload).model_dump(mode="json")
        )
        row = self.lifecycle.create_draft(
            kind=request.kind, code=request.code, display_name=request.display_name, payload=payload
        )
        return self.read(row["version_id"])

    def transition(self, identity, action, expected):
        grant = {
            "submit-review": "acceptance:write",
            "approve": "acceptance:review",
            "reject": "acceptance:review",
            "publish": "acceptance:publish",
        }[action]
        require_management_permission(self.context, grant)
        self.read(identity)
        function = {
            "submit-review": self.lifecycle.submit_review,
            "approve": self.lifecycle.approve,
            "reject": self.lifecycle.reject,
            "publish": self.lifecycle.publish,
        }[action]
        function(UUID(str(identity)), expected_record_version=expected)
        return self.read(identity)

    def readiness(self, case_id, gold_review_id=None):
        require_management_permission(self.context, "acceptance:read")
        case = self.read(case_id)
        if case["kind"] != "REGULATORY_ACCEPTANCE_CASE":
            raise LookupError("ACCEPTANCE_CASE_NOT_FOUND")
        technical = case["payload"]["dataset_kind"] == "L1_SYNTHETIC_GOVERNED"
        checks = {
            "authorized_originals": False,
            "verified_source_version_effectivity": False,
            "independent_expert_expected_answers": False,
            "formal_expert_approval_record": False,
            "defined_case_jurisdiction_criteria": bool(case["payload"]["evaluation_criteria"]),
        }
        reasons = []
        with self.sessions() as s:
            if gold_review_id is not None:
                gold = scoped(s, m.MetadataVersionEntity, gold_review_id, self.tenant)
                definition = scoped(s, m.MetadataDefinitionEntity, gold.definition_id, self.tenant)
                if definition.kind != "REGULATORY_GOLD_REVIEW" or gold.payload_json.get(
                    "case_version_id"
                ) != str(case_id):
                    raise ValueError("ACCEPTANCE_GOLD_CASE_IDENTITY_MISMATCH")
                if gold.lifecycle_status not in {"APPROVED", "ACTIVE"} or not gold.approved_by:
                    reasons.append("EXPERT_GOLD_APPROVAL_PENDING")
                else:
                    validate_acceptance_payload(s, definition, gold.payload_json)
                    validate_acceptance_transition(s, definition, gold, gold.approved_by, "ACTIVE")
                    checks.update({key: True for key in checks})
            else:
                reasons.append(
                    "EXTERNAL_EVIDENCE_PENDING"
                    if not technical
                    else "SYNTHETIC_REVIEW_RECORD_PENDING"
                )
        return {
            "case_version_id": str(case_id),
            "gold_review_version_id": str(gold_review_id) if gold_review_id else None,
            "dataset_kind": case["payload"]["dataset_kind"],
            "checks": checks,
            "decision": "ENGINEERING_READINESS_ONLY"
            if technical
            else "READY_FOR_INDEPENDENT_ACCEPTANCE"
            if all(checks.values())
            else "BLOCKED_EXTERNAL_EVIDENCE_PENDING",
            "reason_codes": reasons,
            "real_regulatory_legal_acceptance": "NOT_EXECUTED",
            "production_business_uat": "NOT_EXECUTED",
        }
