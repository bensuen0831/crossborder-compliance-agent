"""C0 owners using canonical E/G/H/I/J PostgreSQL authorities and publication."""

# ruff: noqa: F811, F401 -- imported canonical pytest fixtures
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from test_phase1j_postgres import fixture, foundation_i, foundation_j, publish_config, run_pipeline

from crossborder_compliance.application.formal_result_services import (
    CrossBorderAssessmentService,
    FormalAuthorityRequest,
    RegulatoryDocumentRequirementService,
)
from crossborder_compliance.domain.decision_contracts import result_digest
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import formal_result_models as a
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)

pytestmark = pytest.mark.runtime_smoke


def publish_template(f):
    from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
        PostgresGovernedArtifactAdminRepository,
    )

    def admin(actor):
        ctx = RepositoryContext.user(
            UUID(f["tenant"]), actor, {"metadata:admin", "metadata:review", "metadata:publish"}
        )
        return PostgresGovernedArtifactAdminRepository(f["sf"], ctx, "templates")

    author = admin("author")
    draft = author.create_draft(
        code="TEMPLATE_" + uuid4().hex,
        display_name="Governed template",
        payload={
            "template_type": "REGULATORY_TEMPLATE",
            "field_schema": {},
            "effective_from": "2025-01-01",
        },
    )
    ident = UUID(draft["version_id"])
    reviewed = author.transition(
        ident, target_status="PENDING_REVIEW", expected_record_version=draft["record_version"]
    )
    approved = admin("independent-reviewer").transition(
        ident, target_status="APPROVED", expected_record_version=reviewed["record_version"]
    )
    return author.transition(
        ident, target_status="ACTIVE", expected_record_version=approved["record_version"]
    )


def condition(threshold=3, field="count"):
    return dict(
        entry_id=str(uuid4()),
        code="GOVERNED_INPUT_TEST",
        fields=[dict(code=field, field_type=dict(kind="integer"))],
        predicate=json.dumps(dict(op="gte", field=field, value=threshold)),
        examples=[dict(facts=[dict(code=field, value=threshold)], expected="TRUE")],
    )


@pytest.fixture
def authority(foundation_i, request):
    params = getattr(request, "param", {})

    def configure(f):
        with f["sf"]() as s, s.begin():
            run = s.scalar(
                select(c.ContextResolutionRunEntity).where(
                    c.ContextResolutionRunEntity.tenant_id == f["tenant"],
                    c.ContextResolutionRunEntity.project_id == f["project"],
                )
            )
            for role in ("SOURCE", "DESTINATION"):
                s.add(
                    c.JurisdictionContextEntity(
                        jurisdiction_context_id=str(uuid4()),
                        tenant_id=f["tenant"],
                        project_id=f["project"],
                        jurisdiction_id=f["juri"],
                        context_type=role,
                        location_precision="COUNTRY",
                        source="APPROVED_METADATA",
                        confidence=1,
                        validation_status="VALIDATED",
                        version=run.version,
                    )
                )
            if params.get("conflict"):
                run.conflict_count = 1
            if params.get("product_conflict"):
                product = s.scalar(
                    select(c.ProductScopeResolutionEntity).where(
                        c.ProductScopeResolutionEntity.tenant_id == f["tenant"],
                        c.ProductScopeResolutionEntity.project_id == f["project"],
                    )
                )
                product.resolution_status = "CONFLICTED"
                product.review_required = True
        ob = f["j_policies"]["OBLIGATION_POLICY"]
        entry = ob["payload"]["entries"][0]["entry_id"] if "payload" in ob else None
        if not entry:
            with f["sf"]() as s:
                entry = s.get(m.MetadataVersionEntity, ob["version_id"]).payload_json["entries"][0][
                    "entry_id"
                ]
        cross = publish_config(
            f,
            "CROSS_BORDER_ASSESSMENT_POLICY",
            dict(
                jurisdiction_ids=[f["juri"]],
                obligation_policy_id=ob["definition_id"],
                transfer_legally_possible=condition(field=params.get("permission_field", "count")),
                prerequisites=[dict(requirement_id=entry, kind="APPROVAL")],
            ),
        )
        levels = ("REQUIRED", "CONDITIONAL", "RECOMMENDED", "NOT_APPLICABLE")
        entries = [
            dict(
                entry_id=str(uuid4()),
                document_type_code=code,
                name=code,
                requirement_level=level,
                trigger_obligation_entry_ids=[entry],
            )
            for code, level in zip(("SCC", "DPIA", "DPA", "NONE"), levels, strict=True)
        ]
        entries.append(
            dict(
                entry_id=str(uuid4()),
                document_type_code="UNTRIGGERED",
                name="No legal trigger",
                requirement_level="REQUIRED",
                trigger_path_action_codes=["UNUSED_GOVERNED_ACTION"],
            )
        )
        if params.get("templates"):
            template = publish_template(f)
            with f["sf"]() as s, s.begin():
                for item in (entries[0], entries[-1]):
                    binding_id = str(uuid4())
                    item["template_binding_id"] = binding_id
                    s.add(
                        m.TemplateBindingEntity(
                            template_binding_id=binding_id,
                            tenant_id=f["tenant"],
                            template_version_id=template["version_id"],
                            binding_type="DOCUMENT_REQUIREMENT",
                            binding_ref=item["entry_id"],
                        )
                    )
            f["c0_template"] = template
        document = publish_config(
            f,
            "DOCUMENT_REQUIREMENT_POLICY",
            dict(
                jurisdiction_ids=[f["juri"]],
                obligation_policy_id=ob["definition_id"],
                cross_border_policy_id=cross["definition_id"],
                entries=entries,
            ),
        )
        f.update(c0_cross_policy=cross, c0_document_policy=document, c0_entries=entries)

    overrides = dict(
        legal_effect_code=params.get("effect", "REQUIREMENT"),
        fulfillment_conditions=[condition(params.get("threshold", 3))],
    )
    return foundation_j.__wrapped__(
        foundation_i,
        SimpleNamespace(
            param=dict(
                obligation_entry=overrides,
                before_j_initialization=configure,
                path_template=params.get("path_template", {}),
            )
        ),
    )


def execute(f, *, missing_obligation=False):
    results, _ = run_pipeline(f) if not missing_obligation else ({}, None)
    req = FormalAuthorityRequest(
        project_id=f["project"],
        analysis_snapshot_id=f["snapshot"],
        subject_type=f["request"].subject_type,
        subject_id=f["request"].subject_id,
        stage_kind="CROSS_BORDER",
        obligation_result_id=results["OBLIGATION"].result_id if results else None,
        idempotency_key=str(uuid4()),
    )
    cross = CrossBorderAssessmentService(f["jrepo"]).execute(req)
    dreq = req.model_copy(
        update=dict(
            stage_kind="DOCUMENT_REQUIREMENT",
            cross_border_result_id=cross.result_id,
            final_path_result_id=results["FINAL_PATH"].result_id if results else None,
            idempotency_key=str(uuid4()),
        )
    )
    docs = RegulatoryDocumentRequirementService(f["jrepo"]).execute(dreq)
    return cross, docs, req, dreq, results


@pytest.mark.parametrize(
    "authority,status,reason",
    [
        (
            {"effect": "TRANSFER_PROHIBITED"},
            "TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED",
            "LEGAL_PROHIBITION",
        ),
        (
            {"effect": "LOCALIZATION_REQUIRED"},
            "TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED",
            "LOCALIZATION_REQUIRED",
        ),
        ({}, "DIRECT_TRANSFER_ALLOWED", "TRANSFER_PREREQUISITES_SATISFIED"),
        ({"threshold": 4}, "CONDITIONAL_TRANSFER_ALLOWED", "APPROVAL_PENDING"),
        ({"permission_field": "unavailable"}, "REVIEW_REQUIRED", "EVIDENCE_INSUFFICIENT"),
    ],
    indirect=["authority"],
)
def test_governed_cross_border_precedence(authority, status, reason):
    cross, docs, _, _, results = execute(authority)
    assert cross.items[0].status == status
    assert reason in cross.items[0].reason_codes
    assert cross.items[0].localization_required == ("LOCALIZATION_REQUIRED" == reason)
    assert cross.items[0].evidence_ids and cross.items[0].legal_basis_ids
    assert cross.items[0].policy_version_id == UUID(authority["c0_cross_policy"]["version_id"])
    if cross.review_required:
        assert docs.review_required and not docs.items
    else:
        assert not docs.review_required
        assert [d.requirement_level for d in docs.items] == [
            "REQUIRED",
            "CONDITIONAL",
            "RECOMMENDED",
            "NOT_APPLICABLE",
            "NOT_APPLICABLE",
        ]
        assert docs.items[0].template_version_id is None
        assert docs.items[0].requirement_level == "REQUIRED"


def test_missing_formal_evidence_is_review_not_certainty(authority):
    cross, docs, *_ = execute(authority, missing_obligation=True)
    assert cross.summary_status == "REVIEW_REQUIRED"
    assert "EVIDENCE_INSUFFICIENT" in cross.reason_codes
    assert docs.items == () and docs.review_required


@pytest.mark.parametrize(
    "authority,reason",
    [
        ({"conflict": True}, "FACT_CONFLICT"),
        ({"product_conflict": True}, "PRODUCT_CONTEXT_CONFLICT"),
    ],
    indirect=["authority"],
)
def test_pinned_context_conflicts_require_review(authority, reason):
    # The owner can persist a review result without manufacturing J decisions.
    cross, docs, *_ = execute(authority, missing_obligation=True)
    assert cross.review_required and reason in cross.reason_codes
    assert docs.review_required and not docs.items


def test_restart_aliases_and_snapshot_exact_reads(authority):
    f = authority
    cross, docs, req, dreq, _ = execute(f)
    restarted = PostgresCountryComplianceRepository(f["sf"], f["jctx"])
    for service, request, result in (
        (CrossBorderAssessmentService(restarted), req, cross),
        (RegulatoryDocumentRequirementService(restarted), dreq, docs),
    ):
        assert result_digest(service.read(result.result_id)) == result_digest(result)
        assert service.execute(request).result_id == result.result_id
        assert (
            service.execute(request.model_copy(update={"idempotency_key": str(uuid4())})).result_id
            == result.result_id
        )
    with f["sf"]() as s:
        for model in a.MODELS.values():
            assert (
                s.scalar(
                    select(func.count()).select_from(model).where(model.tenant_id == f["tenant"])
                )
                == 1
            )
    updated = publish_config(
        f,
        "CROSS_BORDER_ASSESSMENT_POLICY",
        dict(
            jurisdiction_ids=[f["juri"]],
            obligation_policy_id=f["j_policies"]["OBLIGATION_POLICY"]["definition_id"],
            transfer_legally_possible=condition(4),
        ),
        definition_id=f["c0_cross_policy"]["definition_id"],
    )
    assert updated["version_id"] != f["c0_cross_policy"]["version_id"]
    assert result_digest(
        CrossBorderAssessmentService(restarted).read(cross.result_id)
    ) == result_digest(cross)
    assert result_digest(
        RegulatoryDocumentRequirementService(restarted).read(docs.result_id)
    ) == result_digest(docs)


def test_authorization_and_immutable_result(authority):
    f = authority
    cross, docs, *_ = execute(f)
    for ctx in (
        RepositoryContext.user(uuid4(), "author", f["jctx"].permission.scopes),
        RepositoryContext.user(UUID(f["tenant"]), "author", set()),
    ):
        repo = PostgresCountryComplianceRepository(f["sf"], ctx)
        with pytest.raises((LookupError, PermissionError)):
            CrossBorderAssessmentService(repo).read(cross.result_id)
    with pytest.raises(DBAPIError), f["sf"]() as s, s.begin():
        s.execute(
            update(a.MODELS["CROSS_BORDER"])
            .where(a.MODELS["CROSS_BORDER"].result_id == str(cross.result_id))
            .values(summary_status="DIRECT_TRANSFER_ALLOWED")
        )


@pytest.mark.parametrize(
    "authority",
    [
        {
            "effect": "TRANSFER_PROHIBITED",
            "threshold": 4,
            "path_template": {
                "prohibiting_obligation_entry_ids": [],
                "actions": [{"entry_id": str(uuid4()), "code": "LOCAL_PROCESSING", "sequence": 1}],
            },
        }
    ],
    indirect=True,
)
def test_conditional_local_alternative_is_not_transfer_permission(authority):
    cross, _, _, _, results = execute(authority)
    assert results["FINAL_PATH"].items[0].status == "CONDITIONAL_PROPOSAL"
    assert results["FINAL_PATH"].items[0].actions[0].action_code == "LOCAL_PROCESSING"
    assert cross.items[0].status == "TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED"
    assert cross.items[0].reason_codes == ("LEGAL_PROHIBITION",)


@pytest.mark.parametrize("authority", [{"templates": True}], indirect=True)
def test_template_availability_is_independent_and_history_is_pinned(authority):
    f = authority
    cross, docs, *_ = execute(f)
    assert docs.items[0].requirement_level == "REQUIRED"
    assert docs.items[0].template_version_id == UUID(f["c0_template"]["version_id"])
    assert docs.items[-1].template_version_id == UUID(f["c0_template"]["version_id"])
    assert docs.items[-1].requirement_level == "NOT_APPLICABLE"
    replacement = publish_template(f)
    entries = [dict(e) for e in f["c0_entries"]]
    with f["sf"]() as s, s.begin():
        for item in (entries[0], entries[-1]):
            binding_id = str(uuid4())
            item["template_binding_id"] = binding_id
            s.add(
                m.TemplateBindingEntity(
                    template_binding_id=binding_id,
                    tenant_id=f["tenant"],
                    template_version_id=replacement["version_id"],
                    binding_type="DOCUMENT_REQUIREMENT",
                    binding_ref=item["entry_id"],
                )
            )
    publish_config(
        f,
        "DOCUMENT_REQUIREMENT_POLICY",
        dict(
            jurisdiction_ids=[f["juri"]],
            obligation_policy_id=f["j_policies"]["OBLIGATION_POLICY"]["definition_id"],
            cross_border_policy_id=f["c0_cross_policy"]["definition_id"],
            entries=entries,
        ),
        definition_id=f["c0_document_policy"]["definition_id"],
    )
    with f["sf"]() as s, s.begin():
        s.get(
            m.TemplateVersionEntity, f["c0_template"]["version_id"]
        ).lifecycle_status = "SUPERSEDED"
    assert result_digest(
        CrossBorderAssessmentService(f["jrepo"]).read(cross.result_id)
    ) == result_digest(cross)
    assert result_digest(
        RegulatoryDocumentRequirementService(f["jrepo"]).read(docs.result_id)
    ) == result_digest(docs)
    with pytest.raises(DBAPIError), f["sf"]() as s, s.begin():
        s.get(m.TemplateVersionEntity, f["c0_template"]["version_id"]).content_ref = "changed"


@pytest.mark.parametrize("authority", [{"templates": True}], indirect=True)
def test_s1_results_survive_s2_binary_policy_template_and_legal_knowledge(authority):
    from test_phase1d_postgres import MemoryStorage, Queue
    from test_phase1f_postgres import ingest, step
    from test_phase1g_publication_postgres import snapshot

    from crossborder_compliance.application.document_services import (
        DocumentIngestionService,
        DocumentParseService,
    )
    from crossborder_compliance.infrastructure.document_parsers import TextParserAdapter
    from crossborder_compliance.infrastructure.persistence import models as b
    from crossborder_compliance.infrastructure.persistence.document_repositories import (
        PostgresDocumentIntelligenceRepository,
    )

    f = authority
    cross, docs, *_ = execute(f)
    storage = MemoryStorage()
    document_repo = PostgresDocumentIntelligenceRepository(f["sf"], f["jctx"])
    version = DocumentIngestionService(document_repo, storage, None, scan_required=False).ingest(
        tenant_id=UUID(f["tenant"]),
        project_id=UUID(f["project"]),
        filename="later.txt",
        mime_type="text/plain",
        content=b"Purpose: later confirmed analysis input\n",
    )
    parser = DocumentParseService(document_repo, storage, [TextParserAdapter()], Queue())
    task = parser.request_parse(
        document_version_id=UUID(version["document_version_id"]), idempotency_key=str(uuid4())
    )
    parsed = parser.process_task(UUID(task["task_id"]))
    assert parsed["status"] == "COMPLETED"
    replacement = publish_template(f)
    entries = [dict(e) for e in f["c0_entries"]]
    with f["sf"]() as s, s.begin():
        binding_id = str(uuid4())
        entries[0]["template_binding_id"] = binding_id
        s.add(
            m.TemplateBindingEntity(
                template_binding_id=binding_id,
                tenant_id=f["tenant"],
                template_version_id=replacement["version_id"],
                binding_type="DOCUMENT_REQUIREMENT",
                binding_ref=entries[0]["entry_id"],
            )
        )
    updated_cross = publish_config(
        f,
        "CROSS_BORDER_ASSESSMENT_POLICY",
        dict(
            jurisdiction_ids=[f["juri"]],
            obligation_policy_id=f["j_policies"]["OBLIGATION_POLICY"]["definition_id"],
            transfer_legally_possible=condition(4),
        ),
        definition_id=f["c0_cross_policy"]["definition_id"],
    )
    updated_docs = publish_config(
        f,
        "DOCUMENT_REQUIREMENT_POLICY",
        dict(
            jurisdiction_ids=[f["juri"]],
            obligation_policy_id=f["j_policies"]["OBLIGATION_POLICY"]["definition_id"],
            cross_border_policy_id=f["c0_cross_policy"]["definition_id"],
            entries=entries,
        ),
        definition_id=f["c0_document_policy"]["definition_id"],
    )
    old_knowledge = f["repo"].get_version(f["knowledge_version"])
    new_knowledge = f["repo"].create_version(
        old_knowledge["document_id"],
        dict(
            collection_version_id=f["cv"],
            language="en",
            effective_from="2025-01-01",
            provenance={"fixture": "later legal knowledge"},
        ),
    )
    ingest(f, new_knowledge)
    step(f, new_knowledge, "validate")
    step(f, new_knowledge, "submit-review")
    step(f, new_knowledge, "approve", True)
    step(f, new_knowledge, "publish")
    assert new_knowledge["knowledge_version_id"] != f["knowledge_version"]
    second = UUID(snapshot(f))
    document_repo.pin_parse_run(
        analysis_snapshot_id=second,
        document_version_id=UUID(version["document_version_id"]),
        parse_run_id=UUID(parsed["parse_run_id"]),
    )
    CrossBorderAssessmentService(f["jrepo"]).initialize(UUID(f["project"]), second)
    with f["sf"]() as s:
        versions = set(
            s.scalars(
                select(m.AnalysisSnapshotRegistryPinEntity.version_id).where(
                    m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(second)
                )
            )
        )
        assert updated_cross["version_id"] in versions and updated_docs["version_id"] in versions
        assert replacement["version_id"] in versions
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.SourceTraceRefEntity)
                .where(b.SourceTraceRefEntity.document_version_id == version["document_version_id"])
            )
            > 0
        )
    assert result_digest(
        CrossBorderAssessmentService(f["jrepo"]).read(cross.result_id)
    ) == result_digest(cross)
    assert result_digest(
        RegulatoryDocumentRequirementService(f["jrepo"]).read(docs.result_id)
    ) == result_digest(docs)


def test_authority_api_is_typed_authorized_and_reference_only(authority, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.routes import decisions

    f = authority
    cross, docs, req, dreq, _ = execute(f)
    app = FastAPI()
    app.include_router(decisions.router)
    app.dependency_overrides[get_repository_context] = lambda: f["jctx"]
    monkeypatch.setattr(
        decisions,
        "repository",
        lambda context: PostgresCountryComplianceRepository(f["sf"], context),
    )
    client = TestClient(app)
    url = f"/api/v1/projects/{f['project']}/formal-authority-results"
    for request, result in ((req, cross), (dreq, docs)):
        response = client.post(url, json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        assert response.json()["result_id"] == str(result.result_id)
        read = client.get(
            f"/api/v1/formal-authority-results/{request.stage_kind}/{result.result_id}"
        )
        assert read.status_code == 200 and read.json() == response.json()
    for field in ("tenant_id", "policy_version_id", "status", "final_path_status"):
        assert (
            client.post(url, json={**req.model_dump(mode="json"), field: str(uuid4())}).status_code
            == 422
        )
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        uuid4(), "author", f["jctx"].permission.scopes
    )
    assert (
        client.get(f"/api/v1/formal-authority-results/CROSS_BORDER/{cross.result_id}").status_code
        == 404
    )
