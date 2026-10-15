"""Canonical metadata review records with explicitly synthetic appointed reviewers."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_kb01_acceptance_readiness import semantics
from test_kb01_document_management_postgres import knowledge as knowledge
from test_phase1f_postgres import publish

from crossborder_compliance.domain.regulatory_acceptance import RegulatorySourcePin
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.regulatory_acceptance import (
    PostgresRegulatoryAcceptance,
)
from crossborder_compliance.infrastructure.persistence.regulatory_acceptance_governance import (
    payload_digest,
)
from crossborder_compliance.interfaces.api.regulatory_acceptance_schemas import (
    ImportAcceptanceDraft,
)

pytestmark = pytest.mark.runtime_smoke
LEVEL = {"dataset_kind": "L1_SYNTHETIC_GOVERNED", "synthetic_label": "SYNTHETIC_GOVERNED_TEST_DATA"}


def owner(f, actor="record-preparer", scopes=None):
    grants = {"metadata:admin", "metadata:review", "metadata:publish"} | {
        "knowledge:acceptance:" + scope for scope in ("read", "write", "review", "publish")
    }
    return PostgresRegulatoryAcceptance(
        f["sf"],
        RepositoryContext.user(UUID(f["tenant"]), actor, grants if scopes is None else scopes),
    )


def record(f, kind, payload, actor="record-preparer"):
    return owner(f, actor).import_draft(
        ImportAcceptanceDraft(
            kind=kind,
            code="F0-" + uuid4().hex,
            display_name="SYNTHETIC_GOVERNED_TEST_DATA engineering record",
            payload={**LEVEL, **payload},
        )
    )


def approved(f, row, reviewer):
    prepared = owner(f, row["created_by"]).transition(
        row["version_id"], "submit-review", row["record_version"]
    )
    approved = owner(f, reviewer).transition(
        row["version_id"], "approve", prepared["record_version"]
    )
    return owner(f, "configuration-publisher").transition(
        row["version_id"], "publish", approved["record_version"]
    )


def universe(f):
    published = publish(f)
    version = f["repo"].get_version(published["knowledge_version_id"])
    with f["sf"]() as session:
        nodes = session.scalars(
            select(k.KnowledgeStructureNodeEntity).where(
                k.KnowledgeStructureNodeEntity.knowledge_version_id
                == version["knowledge_version_id"]
            )
        ).all()
    pin = RegulatorySourcePin(
        knowledge_version_id=version["knowledge_version_id"],
        content_sha256=version["content_hash"],
        structure_node_ids=tuple(n.structure_node_id for n in nodes),
    )
    authorization = record(
        f,
        "REGULATORY_EXPERT_AUTHORIZATION",
        {
            "expert_actor_id": "synthetic-appointed-expert",
            "jurisdiction_ids": [f["juri"]],
            "appointment_record_ref": "SYNTHETIC_APPOINTMENT_NOT_REAL_EXPERT_APPROVAL",
            "valid_from": "2020-01-01",
        },
    )
    authorization = approved(f, authorization, "independent-appointment-reviewer")
    case = record(
        f,
        "REGULATORY_ACCEPTANCE_CASE",
        {
            "description": "Synthetic Gold mechanism fixture, not a real legal outcome",
            "jurisdiction_ids": [f["juri"]],
            "analysis_as_of_date": "2026-10-15",
            "input_manifest_sha256": "c" * 64,
            "source_pins": [pin.model_dump(mode="json")],
            "expected": semantics()
            .model_copy(
                update={"legal_source_pins": (pin,), "jurisdiction_ids": (UUID(f["juri"]),)}
            )
            .model_dump(mode="json"),
            "evaluation_criteria": ["TRACEABILITY", "EXACT_SEMANTIC_RECONCILIATION"],
        },
        actor="case-author",
    )
    case = approved(f, case, "independent-case-reviewer")
    return pin, authorization, case


def test_synthetic_appointed_expert_flow_preserves_canonical_versions_and_never_claims_f1(
    knowledge,
):
    f = knowledge
    pin, authorization, case = universe(f)
    pending = owner(f).readiness(case["version_id"])
    assert pending["decision"] == "ENGINEERING_READINESS_ONLY"
    assert pending["checks"]["formal_expert_approval_record"] is False
    verification = record(
        f,
        "REGULATORY_SOURCE_VERIFICATION",
        {
            "source_pin": pin.model_dump(mode="json"),
            "jurisdiction_id": f["juri"],
            "expert_authorization_version_id": authorization["version_id"],
            "official_source_record_ref": "SYNTHETIC_SOURCE_VERIFICATION_NOT_OFFICIAL_LAW",
            "effective_from": "2020-01-01",
            "verification_notes": "Engineering-only synthetic source review",
        },
    )
    verification = approved(f, verification, "synthetic-appointed-expert")
    gold = record(
        f,
        "REGULATORY_GOLD_REVIEW",
        {
            "case_version_id": case["version_id"],
            "case_payload_sha256": case["payload_sha256"],
            "expected_semantics_sha256": payload_digest(case["payload"]["expected"]),
            "expert_authorization_version_id": authorization["version_id"],
            "source_verification_version_ids": [verification["version_id"]],
            "expert_review_record_ref": "SYNTHETIC_GOLD_RECORD_NOT_REAL_LEGAL_ACCEPTANCE",
            "review_notes": "Only tests the engineering appointment and review mechanism",
        },
    )
    gold = approved(f, gold, "synthetic-appointed-expert")
    result = owner(f).readiness(case["version_id"], gold["version_id"])
    assert all(result["checks"].values())
    assert result["decision"] == "ENGINEERING_READINESS_ONLY"
    assert result["real_regulatory_legal_acceptance"] == "NOT_EXECUTED"
    assert gold["approved_by"] == "synthetic-appointed-expert" and gold["approved_at"]
    assert owner(f).read(case["version_id"]) == case
    foreign = PostgresRegulatoryAcceptance(
        f["sf"], RepositoryContext.user(uuid4(), "foreign", {"knowledge:acceptance:read"})
    )
    with pytest.raises(LookupError):
        foreign.read(case["version_id"])


def test_expert_cannot_self_appoint_or_be_replaced_by_an_arbitrary_admin(knowledge):
    f = knowledge
    row = record(
        f,
        "REGULATORY_EXPERT_AUTHORIZATION",
        {
            "expert_actor_id": "candidate-expert",
            "jurisdiction_ids": [f["juri"]],
            "appointment_record_ref": "SYNTHETIC_APPOINTMENT",
            "valid_from": "2020-01-01",
        },
    )
    prepared = owner(f).transition(row["version_id"], "submit-review", row["record_version"])
    with pytest.raises(ValueError, match="CANNOT_SELF_APPOINT"):
        owner(f, "candidate-expert").transition(
            row["version_id"], "approve", prepared["record_version"]
        )
    with pytest.raises(PermissionError):
        owner(f, scopes={"knowledge:admin"}).read(row["version_id"])


def test_l2_raw_source_without_authorized_binary_original_is_not_acceptance_evidence(knowledge):
    f = knowledge
    version = publish(f)
    content = f["repo"].get_version(version["knowledge_version_id"])
    with f["sf"]() as session:
        node = session.scalar(
            select(k.KnowledgeStructureNodeEntity).where(
                k.KnowledgeStructureNodeEntity.knowledge_version_id
                == content["knowledge_version_id"]
            )
        )
    payload = {
        "dataset_kind": "L2_REAL_REGULATORY",
        "description": "Pending external original",
        "jurisdiction_ids": [f["juri"]],
        "analysis_as_of_date": "2026-10-15",
        "input_manifest_sha256": "a" * 64,
        "source_pins": [
            {
                "knowledge_version_id": content["knowledge_version_id"],
                "content_sha256": content["content_hash"],
                "structure_node_ids": [node.structure_node_id],
            }
        ],
        "evaluation_criteria": ["SOURCE_AUTHENTICITY"],
    }
    with pytest.raises(ValueError, match="AUTHORIZED_ORIGINAL_PENDING"):
        owner(f).import_draft(
            ImportAcceptanceDraft(
                kind="REGULATORY_ACCEPTANCE_CASE",
                code="REAL-PENDING-" + uuid4().hex,
                display_name="External evidence pending",
                payload=payload,
            )
        )


def test_arbitrary_admin_cannot_approve_source_verification_for_appointed_expert(knowledge):
    f = knowledge
    pin, authorization, _ = universe(f)
    row = record(
        f,
        "REGULATORY_SOURCE_VERIFICATION",
        {
            "source_pin": pin.model_dump(mode="json"),
            "jurisdiction_id": f["juri"],
            "expert_authorization_version_id": authorization["version_id"],
            "official_source_record_ref": "SYNTHETIC_SOURCE_REFERENCE",
            "effective_from": "2020-01-01",
            "verification_notes": "Technical independent-review fixture",
        },
    )
    prepared = owner(f).transition(row["version_id"], "submit-review", row["record_version"])
    with pytest.raises(ValueError, match="APPOINTED_EXPERT_REQUIRED"):
        owner(f, "unappointed-metadata-reviewer").transition(
            row["version_id"], "approve", prepared["record_version"]
        )
    after = owner(f).read(row["version_id"])
    assert after["lifecycle"] == "PENDING_REVIEW" and after["approved_by"] is None


def test_acceptance_http_import_rejects_caller_approval_identity_and_retains_real_f1_blocker(
    knowledge,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.routes.regulatory_acceptance import router

    f = knowledge
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)

    @app.middleware("http")
    async def trusted_host(request, call_next):
        request.state.repository_context = owner(f).context
        return await call_next(request)

    prefix = "/api/v1/admin/knowledge-management/acceptance"
    with TestClient(app) as client:
        template = client.get(prefix + "/templates")
        assert template.status_code == 200
        assert template.json()["approval_status"] == "TEMPLATES_NOT_APPROVED_GOLD_STANDARDS"
        body = {
            "kind": "REGULATORY_ACCEPTANCE_CASE",
            "code": "PENDING-" + uuid4().hex,
            "display_name": "Real regulatory readiness — no materials supplied",
            "payload": {
                "dataset_kind": "L2_REAL_REGULATORY",
                "description": "External evidence still pending",
                "jurisdiction_ids": [f["juri"]],
                "analysis_as_of_date": "2026-10-15",
                "input_manifest_sha256": "a" * 64,
                "source_pins": [],
                "evaluation_criteria": ["SOURCE_AUTHENTICITY"],
            },
        }
        assert (
            client.post(
                prefix + "/records", json={**body, "approved_by": "spoofed-expert"}
            ).status_code
            == 422
        )
        created = client.post(prefix + "/records", json=body)
        assert created.status_code == 201, created.text
        value = created.json()
        assert value["created_by"] == "record-preparer" and value["approved_by"] is None
        readiness = client.get(prefix + "/cases/" + value["version_id"] + "/readiness").json()
        assert readiness["decision"] == "BLOCKED_EXTERNAL_EVIDENCE_PENDING"
        assert readiness["real_regulatory_legal_acceptance"] == "NOT_EXECUTED"
        assert not readiness["checks"]["authorized_originals"]
