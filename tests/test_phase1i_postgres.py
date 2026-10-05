"""Actual PostgreSQL + existing Phase1E/F/G/H paths, profile governance and security."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from phase1g_fixtures import publish
from phase1h_fixtures import contract
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from test_phase1f_postgres import binding, item, metadata
from test_phase1f_postgres import fixture as fixture
from test_phase1g_persistence_postgres import policies, query, service
from test_phase1h_postgres import payload as rule_payload
from test_phase1h_postgres import publish as publish_h

from crossborder_compliance.application.classification_services import ClassificationService
from crossborder_compliance.application.country_compliance_services import (
    ApplicabilityRequest,
    CountryComplianceSkill,
)
from crossborder_compliance.application.metadata_services import MetadataLifecycleService
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.compliance_profile_worker import (
    ComplianceProfilePublicationWorker,
)
from crossborder_compliance.infrastructure.persistence import applicability_models as i
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.classification_repository import (
    PostgresFormalClassificationRepository,
)
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.rule_admin_repository import (
    PostgresRuleAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresClassificationAdminRepository,
)

pytestmark = pytest.mark.runtime_smoke


def config_service(f, actor="author"):
    ctx = RepositoryContext.user(
        UUID(f["tenant"]), actor, {"metadata:admin", "metadata:review", "metadata:publish"}
    )
    return MetadataLifecycleService(PostgresAdminMetadataRepository(f["sf"], ctx), ctx)


def publish_config(f, kind, payload, definition_id=None):
    svc = config_service(f)
    body = {"effective_from": "2025-01-01", **payload}
    if definition_id:
        version = svc._repository.create_version(
            definition_id=UUID(str(definition_id)), payload=body
        )
    else:
        version = svc.create_draft(
            kind=kind, code=str(uuid4()), display_name="Generic configuration", payload=body
        )
    ident = UUID(version["version_id"])
    v = svc.submit_review(ident, expected_record_version=version["record_version"])
    v = config_service(f, "independent-reviewer").approve(
        ident, expected_record_version=v["record_version"]
    )
    return svc.publish(ident, expected_record_version=v["record_version"])


@pytest.fixture
def foundation_i(fixture, request):
    f = fixture
    params = getattr(request, "param", {})
    wide = {
        "knowledge:admin",
        "read:internal",
        "metadata:admin",
        "metadata:review",
        "metadata:publish",
        "classification:execute",
        "classification:read",
        f"project:{f['project']}:classify",
        "applicability:execute",
        "applicability:read",
        f"project:{f['project']}:comply",
    }
    f["ctx"] = RepositoryContext.user(UUID(f["tenant"]), "author", wide)
    authority = metadata(f["sf"], f["tenant"], "AUTHORITY")
    source = f["repo"].get_source(f["source"])
    f["source"] = f["repo"].create_source(
        {
            k: v
            for k, v in {**source, "code": str(uuid4()), "authority_ref": authority}.items()
            if k not in {"source_id", "source_hash", "record_version"}
        }
    )["source_id"]
    with f["sf"]() as s, s.begin():
        run = s.scalar(
            select(c.ContextResolutionRunEntity).where(
                c.ContextResolutionRunEntity.tenant_id == f["tenant"],
                c.ContextResolutionRunEntity.project_id == f["project"],
            )
        )
        run_version = run.version
        s.add(
            c.BusinessFactEntity(
                fact_id=str(uuid4()),
                tenant_id=f["tenant"],
                project_id=f["project"],
                fact_type="COUNT",
                normalized_key="count",
                normalized_value_json=params.get("count", 3),
                resolution_method="DETERMINISTIC",
                confidence=1,
                validation_status="VALIDATED",
                version=run_version,
            )
        )
    subject = None if params.get("no_data") else item(f, f["a"], run_version)
    f["item"] = subject
    version = publish(
        f, [binding(f, dimensions={"product": [f["a"]], "jurisdiction": [f["juri"]]})]
    )
    f["knowledge_version"] = version["knowledge_version_id"]
    f["repo"].build_index(version["knowledge_version_id"])
    retrieval, p, _ = policies(f)
    if params.get("partial"):
        topic = metadata(f["sf"], f["tenant"], "KNOWLEDGE_TOPIC")
        suff = retrieval.create_policy("sufficiency", {"required_topic_refs": [topic]})
        retrieval.publish_policy("sufficiency", suff["policy_version_id"], 1)
        p = retrieval.create_policy(
            "retrieval",
            {"vector_weight": 0, "lexical_weight": 1, "sufficiency_policy_id": suff["policy_id"]},
        )
        retrieval.publish_policy("retrieval", p["policy_version_id"], 1)
    response = service(f, retrieval).retrieve(
        query(
            f,
            p,
            subject_type="PROJECT" if subject is None else "DATA_ITEM",
            subject_id=f["project"] if subject is None else subject,
        )
    )
    f["retrieval"] = response
    with f["sf"]() as s, s.begin():
        extension = s.scalar(
            select(k.KnowledgeStructureNodeEntity).where(
                k.KnowledgeStructureNodeEntity.tenant_id == f["tenant"],
                k.KnowledgeStructureNodeEntity.knowledge_version_id
                == version["knowledge_version_id"],
                k.KnowledgeStructureNodeEntity.node_type == "ARTICLE",
            )
        )
        node = s.get(b.RegulatoryStructureNodeEntity, extension.regulatory_structure_node_id)
        basis = str(uuid4())
        s.add(
            b.LegalBasisItemEntity(
                legal_basis_id=basis,
                tenant_id=f["tenant"],
                jurisdiction_id=f["juri"],
                regulatory_structure_node_id=node.regulatory_structure_node_id,
                legal_basis_summary="Canonical rule basis",
                applicability_reason="Versioned rule",
                official_source=node.official_source,
                citation_locator=extension.canonical_locator,
            )
        )
        f["basis"] = basis
        f["node"] = node.regulatory_structure_node_id
    schemes = PostgresClassificationAdminRepository(f["sf"], f["ctx"])
    reviewer = RepositoryContext.user(UUID(f["tenant"]), "independent-reviewer", wide)
    draft = schemes.create_draft(
        code=str(uuid4()),
        display_name="Generic scheme",
        payload={
            "applicability": {
                "phase1h": {
                    "jurisdiction_ids": [f["juri"]],
                    "categories": [{"code": "CATEGORY"}],
                    "levels": [],
                }
            }
        },
    )
    publish_h(schemes, draft, PostgresClassificationAdminRepository(f["sf"], reviewer))
    details = schemes.get_detail(UUID(draft["version_id"]))
    category = details["applicability"]["phase1h"]["categories"][0]["category_id"]
    rules = PostgresRuleAdminRepository(f["sf"], f["ctx"])
    con = contract(
        draft["version_id"],
        f["juri"],
        category,
        evidence_required=["KNOWLEDGE_ORIGINAL"],
        legal_basis_ids=[basis],
    )
    rule = rules.create_draft(
        code=str(uuid4()), display_name="Generic rule", payload=rule_payload(con)
    )
    publish_h(rules, rule, PostgresRuleAdminRepository(f["sf"], reviewer))
    classifier = PostgresFormalClassificationRepository(f["sf"], f["ctx"])
    classifier.pin_configuration(UUID(f["project"]), UUID(f["snapshot"]), UUID(draft["version_id"]))
    out = ClassificationService(classifier).execute(
        project_id=UUID(f["project"]),
        snapshot_id=UUID(f["snapshot"]),
        data_item_id=UUID(subject) if subject else None,
        scheme_version_id=UUID(draft["version_id"]),
    )
    f["classification"] = out
    f["rule"] = rule
    f["scheme_version"] = draft["version_id"]
    f["policy"] = p
    cfg = {
        "jurisdiction_id": f["juri"],
        "knowledge_version_id": f["knowledge_version"],
        "regulatory_structure_node_ids": [f["node"]],
        "legal_basis_ids": [basis],
        "required_rule_ids": [rule["definition_id"]],
        "reason_code": "CONFIGURED_APPLICABILITY",
        "requires_classification": not params.get("no_data", False),
        **params.get("config", {}),
    }
    cfg["localized_code_labels"] = {
        "APPLICABLE": {
            "localized_display_names": {"zh-CN": "适用", "zh-HK": "適用", "en-US": "Applicable"}
        },
        "CONFIGURED_APPLICABILITY": {
            "localized_display_names": {
                "zh-CN": "规则已匹配",
                "zh-HK": "規則已配對",
                "en-US": "Rule matched",
            }
        },
    }
    applicability = publish_config(f, "APPLICABILITY_CONFIG", cfg)
    cap = publish_config(
        f,
        "COUNTRY_CAPABILITY",
        {
            "kind": "CLASSIFICATION",
            **({"effective_to": "2025-12-31"} if params.get("missing_capability") else {}),
        },
    )
    pack = publish_config(f, "RULE_PACK", {"rule_definition_ids": [rule["definition_id"]]})
    country_payload = {
        "jurisdiction_id": f["juri"],
        "capability_ids": [cap["definition_id"]],
        "rule_pack_ids": [pack["definition_id"]],
        "knowledge_collection_ids": [f["col"]],
        "applicability_config_ids": [applicability["definition_id"]],
    }
    country = publish_config(
        f,
        "COUNTRY_PROFILE",
        {
            **country_payload,
            **({"effective_to": "2025-12-31"} if params.get("country_expired") else {}),
        },
    )
    if params.get("country_conflict"):
        publish_config(f, "COUNTRY_PROFILE", country_payload)
    skill = publish_config(f, "SKILL", {})["definition_id"]
    adjustment = publish_config(
        f,
        "SCENARIO_ADJUSTMENT",
        {
            "scenario_definition_id": f["scenario"],
            "required_inputs": ["FORMAL_CONTEXT", "SCENARIO", "JURISDICTION", "COUNT"],
            "required_skill_ids": [skill],
            "required_country_capability_ids": [cap["definition_id"]],
            "required_outputs": ["APPLICABILITY"],
        },
    )
    f.update(
        country=country,
        country_payload=country_payload,
        capability=cap,
        pack=pack,
        adjustment=adjustment,
        config=applicability,
        config_payload=cfg,
    )
    repo = PostgresCountryComplianceRepository(f["sf"], f["ctx"])
    f["compliance_repo"] = repo
    repo.initialize(UUID(f["project"]), UUID(f["snapshot"]), UUID(f["juri"]))
    f["request"] = ApplicabilityRequest(
        project_id=f["project"],
        analysis_snapshot_id=f["snapshot"],
        subject_type="SCENARIO" if subject is None else "DATA_ITEM",
        subject_id=f["scenario"] if subject is None else subject,
        jurisdiction_id=f["juri"],
        applicability_config_id=applicability["definition_id"],
        retrieval_run_id=response["retrieval_run_id"],
        classification_result_ids=(out.result.classification_result_id,) if out.result else (),
        rule_hit_ids=tuple(h.rule_hit_id for h in out.rule_hits),
    )
    return f


def execute(f):
    return CountryComplianceSkill(f["compliance_repo"]).resolve_regulation_applicability(
        f["request"]
    )


def test_actual_canonical_chain_persistence_links_and_idempotency(foundation_i):
    f = foundation_i
    result = execute(f)
    assert result.applicability_status == "APPLICABLE" and result.regulatory_structure_node_ids == (
        UUID(f["node"]),
    ), result.reason_codes
    assert (
        result.regulation_version_ref == UUID(f["knowledge_version"])
        and result.classification_result_ids
    )
    assert (
        result.country_profile_version_id == UUID(f["country"]["version_id"])
        and result.scenario_adjustment_profile_versions
    )
    assert execute(f).applicability_result_id == result.applicability_result_id
    assert f["compliance_repo"].read(result.applicability_result_id) == result
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(i.RegulationApplicabilityResultEntity)
                .where(i.RegulationApplicabilityResultEntity.tenant_id == f["tenant"])
            )
            == 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.LegalBasisRuleHitLinkEntity)
                .where(b.LegalBasisRuleHitLinkEntity.tenant_id == f["tenant"])
            )
            >= 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.LegalBasisEvidenceLinkEntity)
                .where(b.LegalBasisEvidenceLinkEntity.tenant_id == f["tenant"])
            )
            >= 1
        )


@pytest.mark.parametrize(
    "foundation_i",
    [
        {"config": {"matched_status": "CONDITIONALLY_APPLICABLE"}},
        {"config": {"matched_status": "REVIEW_REQUIRED"}},
        {"count": 2, "config": {"requires_classification": False}},
        {"partial": True},
    ],
    indirect=True,
)
def test_actual_configured_and_insufficient_statuses(foundation_i):
    f = foundation_i
    result = execute(f)
    if f["retrieval"]["rag_context_pack"]["knowledge_sufficiency"]["status"] != "SUFFICIENT":
        assert (
            result.applicability_status == "INSUFFICIENT_EVIDENCE"
            and result.fallback_guidance_context.operational_next_steps
        )
    elif not f["classification"].result:
        assert (
            result.applicability_status == "NOT_APPLICABLE" and not result.classification_result_ids
        )
    else:
        assert result.applicability_status == f["config_payload"]["matched_status"]


@pytest.mark.parametrize(
    "field",
    [
        "project_id",
        "analysis_snapshot_id",
        "jurisdiction_id",
        "subject_id",
        "applicability_config_id",
        "retrieval_run_id",
    ],
)
def test_wrong_scope_references_fail_closed(foundation_i, field):
    f = foundation_i
    with pytest.raises((LookupError, ValueError)):
        f["compliance_repo"].prepare(f["request"].model_copy(update={field: uuid4()}))


def test_cross_tenant_project_operation_and_evidence_denial(foundation_i):
    f = foundation_i
    for ctx in (
        RepositoryContext.user(uuid4(), "author", set(f["ctx"].permission.scopes)),
        RepositoryContext.user(UUID(f["tenant"]), "author", {"applicability:execute"}),
        RepositoryContext.user(UUID(f["tenant"]), "other", set(f["ctx"].permission.scopes)),
    ):
        with pytest.raises((LookupError, PermissionError)):
            PostgresCountryComplianceRepository(f["sf"], ctx).prepare(f["request"])
    result = execute(f)
    f["repo"].update_source(f["source"], {"enabled": False}, 1)
    with pytest.raises((LookupError, ValueError)):
        f["compliance_repo"].read(result.applicability_result_id)


def test_wrong_classification_snapshot_and_missing_basis(foundation_i):
    f = foundation_i
    with pytest.raises(LookupError):
        f["compliance_repo"].prepare(
            f["request"].model_copy(update={"classification_result_ids": (uuid4(),)})
        )
    with f["sf"]() as s, s.begin():
        s.get(b.LegalBasisItemEntity, f["basis"]).citation_locator = "wrong locator"
    result = execute(f)
    assert result.applicability_status == "INSUFFICIENT_EVIDENCE"


def test_independent_review_and_atomic_validation_failure(foundation_i):
    f = foundation_i
    svc = config_service(f)
    draft = svc.create_draft(
        kind="COUNTRY_PROFILE",
        code=str(uuid4()),
        display_name="New version",
        payload={"effective_from": "2025-01-01", **f["country_payload"]},
    )
    v = svc.submit_review(UUID(draft["version_id"]), expected_record_version=1)
    with pytest.raises(ValueError):
        svc.approve(UUID(v["version_id"]), expected_record_version=v["record_version"])
    with pytest.raises((ValueError, LookupError)):
        svc.create_draft(
            kind="COUNTRY_PROFILE",
            code=str(uuid4()),
            display_name="Wrong tenant reference",
            payload={
                "effective_from": "2025-01-01",
                "jurisdiction_id": f["juri"],
                "capability_ids": [uuid4()],
            },
        )
    with f["sf"]() as s:
        assert not s.scalar(
            select(m.RegistrySyncEventEntity).where(
                m.RegistrySyncEventEntity.tenant_id == f["tenant"],
                m.RegistrySyncEventEntity.version_id == draft["version_id"],
            )
        )


def test_immutable_profile_result_and_pins(foundation_i):
    f = foundation_i
    result = execute(f)
    actions = [
        (
            m.MetadataVersionEntity,
            m.MetadataVersionEntity.version_id,
            f["country"]["version_id"],
            {"payload_json": {}},
        ),
        (
            i.RegulationApplicabilityResultEntity,
            i.RegulationApplicabilityResultEntity.applicability_result_id,
            str(result.applicability_result_id),
            {"result_json": {}},
        ),
    ]
    for model, pk, ident, values in actions:
        with pytest.raises(DBAPIError):
            with f["sf"]() as s, s.begin():
                s.execute(update(model).where(pk == ident).values(**values))
    with pytest.raises(DBAPIError):
        with f["sf"]() as s, s.begin():
            s.execute(
                update(m.AnalysisSnapshotRegistryPinEntity)
                .where(
                    m.AnalysisSnapshotRegistryPinEntity.tenant_id == f["tenant"],
                    m.AnalysisSnapshotRegistryPinEntity.pin_type.like("PHASE1I_%"),
                )
                .values(version_id=str(uuid4()))
            )


def test_profile_version_effective_date_and_snapshot_history(foundation_i):
    f = foundation_i
    original = execute(f)
    new = publish_config(f, "COUNTRY_PROFILE", f["country_payload"], f["country"]["definition_id"])
    resolution = f["compliance_repo"].resolve_profile(
        UUID(f["project"]), UUID(f["snapshot"]), UUID(f["juri"])
    )
    assert (
        resolution.profiles[0].version_id == UUID(f["country"]["version_id"])
        and resolution.profiles[0].lifecycle == "SUPERSEDED"
    )
    assert execute(f).applicability_result_id == original.applicability_result_id
    assert new["version_no"] == 2
    with f["sf"]() as s, s.begin():
        snapshot = s.get(b.AnalysisSnapshotEntity, f["snapshot"])
        new_snapshot = uuid4()
        s.add(
            b.AnalysisSnapshotEntity(
                analysis_snapshot_id=str(new_snapshot),
                tenant_id=f["tenant"],
                project_version_id=snapshot.project_version_id,
                analysis_as_of_date=date.today(),
                snapshot_version="2",
                provenance_json={},
            )
        )
        s.flush()
        pin = s.scalar(
            select(c.AnalysisSnapshotContextPinEntity).where(
                c.AnalysisSnapshotContextPinEntity.tenant_id == f["tenant"],
                c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == f["snapshot"],
            )
        )
        s.add(
            c.AnalysisSnapshotContextPinEntity(
                analysis_snapshot_context_pin_id=str(uuid4()),
                tenant_id=f["tenant"],
                analysis_snapshot_id=str(new_snapshot),
                project_id=f["project"],
                context_resolution_run_id=pin.context_resolution_run_id,
                context_resolution_version=pin.context_resolution_version,
                product_context_version=pin.product_context_version,
                data_inventory_version=pin.data_inventory_version,
                data_flow_version=pin.data_flow_version,
            )
        )
    # New snapshot has no authorized KnowledgeScope yet: it cannot adopt legal source silently.
    with pytest.raises(ValueError):
        f["compliance_repo"].initialize(UUID(f["project"]), new_snapshot, UUID(f["juri"]))


def test_projection_publish_outbox_and_zero_code_additional_jurisdiction(foundation_i):
    f = foundation_i
    additional = uuid4()
    with f["sf"]() as s, s.begin():
        s.add(
            b.JurisdictionEntity(
                jurisdiction_id=str(additional),
                tenant_id=f["tenant"],
                code="EXTRA-" + str(additional),
                name="Additional configured jurisdiction",
            )
        )
    cap = publish_config(
        f,
        "COUNTRY_CAPABILITY",
        {"kind": "FILING", "availability": "NOT_APPLICABLE", "data_specific": False},
    )
    profile = publish_config(
        f,
        "COUNTRY_PROFILE",
        {"jurisdiction_id": str(additional), "capability_ids": [cap["definition_id"]]},
    )
    worker = ComplianceProfilePublicationWorker(f["sf"])
    results = worker.run_once()
    projection = worker.projections[(f["tenant"], "COUNTRY_PROFILE")]
    assert projection.get(UUID(profile["definition_id"]))["payload"]["jurisdiction_id"] == str(
        additional
    )
    assert results[f["tenant"]]["applied"] > 0 and worker.run_once()[f["tenant"]]["applied"] == 0
    # Actual resolution is still constrained to the project's formal jurisdiction.
    with pytest.raises(LookupError):
        f["compliance_repo"].resolve_profile(UUID(f["project"]), UUID(f["snapshot"]), additional)

    from crossborder_compliance.application.context_services import ContextResolutionService
    from crossborder_compliance.domain.compliance_profiles import CapabilityInput
    from crossborder_compliance.infrastructure.persistence.context_repositories import (
        PostgresContextResolutionRepository,
    )

    scenario = metadata(f["sf"], f["tenant"], "SCENARIO")
    context_repo = PostgresContextResolutionRepository(f["sf"], f["ctx"])
    run = ContextResolutionService(context_repo).run(
        UUID(f["project"]),
        selected_product_scope=(UUID(f["a"]),),
        detected_product_scope=(UUID(f["a"]),),
        selected_scenarios=(UUID(scenario),),
        detected_scenarios=(UUID(scenario),),
        jurisdictions=(
            {
                "jurisdiction_id": str(additional),
                "input_value": "Configured location",
                "context_type": "STORAGE",
                "precision": "COUNTRY",
                "source": "APPROVED_METADATA",
                "confidence": 1,
            },
        ),
    )
    new_snapshot = uuid4()
    with f["sf"]() as session, session.begin():
        previous = session.get(b.AnalysisSnapshotEntity, f["snapshot"])
        session.add(
            b.AnalysisSnapshotEntity(
                analysis_snapshot_id=str(new_snapshot),
                tenant_id=f["tenant"],
                project_version_id=previous.project_version_id,
                analysis_as_of_date=date.today(),
                snapshot_version="additional-jurisdiction",
                provenance_json={"zero_code": True},
            )
        )
    context_repo.pin_snapshot_context(
        analysis_snapshot_id=new_snapshot,
        project_id=UUID(f["project"]),
        context_resolution_run_id=UUID(run["context_resolution_run_id"]),
    )
    f["compliance_repo"].initialize(UUID(f["project"]), new_snapshot, additional)
    resolution = f["compliance_repo"].resolve_profile(UUID(f["project"]), new_snapshot, additional)
    assert resolution.status == "READY" and resolution.profiles[0].profile_id == UUID(
        profile["definition_id"]
    )
    request = CapabilityInput(
        tenant_id=UUID(f["tenant"]),
        project_id=UUID(f["project"]),
        analysis_snapshot_id=new_snapshot,
        jurisdiction_id=additional,
        kind="FILING",
    )
    resolved = CountryComplianceSkill(f["compliance_repo"]).resolve_filing_requirements(request)
    assert resolved.status == "NOT_APPLICABLE" and not resolved.legal_obligation


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_actual_scenario_only_h_engine_delegation_no_fake_classification(foundation_i):
    f = foundation_i
    assert f["classification"].status == "NOT_APPLICABLE" and f["classification"].result is None
    args = tuple(UUID(f[k]) for k in ("project", "snapshot", "scenario", "juri")) + (
        UUID(f["retrieval"]["retrieval_run_id"]),
    )
    hits = f["compliance_repo"].scenario_rule_hits(*args)
    assert hits and hits[0].matched and hits[0].data_item_id is None
    assert f["compliance_repo"].scenario_rule_hits(*args)[0].rule_hit_id == hits[0].rule_hit_id
    f["request"] = f["request"].model_copy(
        update={"rule_hit_ids": tuple(h.rule_hit_id for h in hits)}
    )
    result = execute(f)
    assert (
        result.applicability_status == "APPLICABLE"
        and not result.classification_result_ids
        and not result.data_item_ids
    )
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.ClassificationResultEntity)
                .where(b.ClassificationResultEntity.tenant_id == f["tenant"])
            )
            == 0
        )
    from crossborder_compliance.domain.compliance_profiles import CapabilityInput

    request = CapabilityInput(
        tenant_id=UUID(f["tenant"]),
        project_id=UUID(f["project"]),
        analysis_snapshot_id=UUID(f["snapshot"]),
        jurisdiction_id=UUID(f["juri"]),
        kind="CLASSIFICATION",
    )
    assert (
        CountryComplianceSkill(f["compliance_repo"]).resolve_capability(request).status
        == "NOT_APPLICABLE"
    )


def test_read_permission_and_result_identity_fail_closed(foundation_i):
    f = foundation_i
    result = execute(f)
    read_scopes = set(f["ctx"].permission.scopes) - {"applicability:execute"}
    reader = PostgresCountryComplianceRepository(
        f["sf"], RepositoryContext.user(UUID(f["tenant"]), "author", read_scopes)
    )
    assert reader.read(result.applicability_result_id) == result
    with pytest.raises(LookupError):
        reader.prepare(f["request"])
    with pytest.raises(LookupError):
        f["compliance_repo"].save(f["request"], result.model_copy(update={"subject_id": uuid4()}))


def test_definition_identity_and_publication_provenance_immutable(foundation_i):
    f = foundation_i
    for model, pk, ident, values in (
        (
            m.MetadataDefinitionEntity,
            m.MetadataDefinitionEntity.definition_id,
            f["country"]["definition_id"],
            {"kind": "SKILL"},
        ),
        (
            m.MetadataVersionEntity,
            m.MetadataVersionEntity.version_id,
            f["country"]["version_id"],
            {"approved_by": "different"},
        ),
    ):
        with pytest.raises(DBAPIError):
            with f["sf"]() as s, s.begin():
                s.execute(update(model).where(pk == ident).values(**values))


def test_actual_api_reference_only_contract_and_scope_denials(foundation_i):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.routes.country_compliance import router

    f = foundation_i
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_repository_context] = lambda: f["ctx"]
    with TestClient(app) as client:
        body = f["request"].model_dump(mode="json")
        body.pop("project_id")
        endpoint = f"/api/v1/projects/{f['project']}/regulation-applicability"
        for field in ("tenant_id", "facts", "knowledge_scope", "applicability_status", "narrative"):
            assert client.post(endpoint, json={**body, field: "forged"}).status_code == 422
        response = client.post(endpoint, json=body)
        assert (
            response.status_code == 200 and response.json()["applicability_status"] == "APPLICABLE"
        ), response.text
        ident = response.json()["applicability_result_id"]
        assert client.get(f"/api/v1/regulation-applicability/{ident}").status_code == 200
        available = client.post(
            f"/api/v1/projects/{f['project']}/country-capabilities",
            json={
                "analysis_snapshot_id": f["snapshot"],
                "jurisdiction_id": f["juri"],
                "kind": "CLASSIFICATION",
                "data_item_id": f["item"],
                "classification_result_id": str(
                    f["classification"].result.classification_result_id
                ),
            },
        )
        assert available.status_code == 200 and available.json()["status"] == "CONFIGURED", (
            available.text
        )
        app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
            uuid4(), "author", set(f["ctx"].permission.scopes)
        )
        assert client.post(endpoint, json=body).status_code == 404
        assert client.get(f"/api/v1/regulation-applicability/{ident}").status_code == 404


@pytest.mark.parametrize(
    "foundation_i",
    [{"country_expired": True}, {"missing_capability": True}, {"country_conflict": True}],
    indirect=True,
)
def test_effective_profile_missing_capability_and_ambiguity_conservative(foundation_i):
    f = foundation_i
    resolution = f["compliance_repo"].resolve_profile(
        UUID(f["project"]), UUID(f["snapshot"]), UUID(f["juri"])
    )
    result = execute(f)
    assert resolution.status != "READY"
    assert (
        result.applicability_status in {"CONFLICTED", "REVIEW_REQUIRED"} and result.review_required
    )


def test_versioned_multilingual_runtime_api_presentation_and_source_integrity(foundation_i):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from test_phase1i_localized_metadata import LABELS

    from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
        PostgresJurisdictionAdminRepository,
    )
    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.routes.country_compliance import (
        router as compliance_router,
    )
    from crossborder_compliance.interfaces.api.routes.metadata import router as metadata_router

    f = foundation_i
    result = execute(f)
    # The original result is pinned: publish a new config label version and show that replay
    # still uses its original version, then exercise multilingual generic metadata separately.
    localized = {
        "localized_display_names": {"zh-CN": "配置", "zh-HK": "設定", "en-US": "Configuration"},
        "fallback_locale": "en-US",
    }
    profile = publish_config(
        f,
        "COUNTRY_PROFILE",
        {**f["country_payload"], "localized_display": localized},
        f["country"]["definition_id"],
    )
    for kind in ("SCENARIO", "SKILL"):
        publish_config(f, kind, {"localized_display": localized})
    jurisdictions = PostgresJurisdictionAdminRepository(f["sf"], f["ctx"])
    jurisdiction = jurisdictions.create_draft(
        code="NEW_JURISDICTION",
        display_name="Canonical jurisdiction",
        payload={"localized_display": localized},
    )
    v = jurisdictions.transition(
        UUID(jurisdiction["version_id"]), target_status="PENDING_REVIEW", expected_record_version=1
    )
    reviewer = PostgresJurisdictionAdminRepository(
        f["sf"],
        RepositoryContext.user(
            UUID(f["tenant"]), "independent-reviewer", set(f["ctx"].permission.scopes)
        ),
    )
    v = reviewer.transition(
        UUID(v["version_id"]), target_status="APPROVED", expected_record_version=v["record_version"]
    )
    jurisdictions.transition(
        UUID(v["version_id"]), target_status="ACTIVE", expected_record_version=v["record_version"]
    )
    app = FastAPI()
    app.include_router(compliance_router)
    app.include_router(metadata_router)
    app.dependency_overrides[get_repository_context] = lambda: f["ctx"]
    with TestClient(app) as client:
        for resource in (
            "country-profiles",
            "scenario-adjustments",
            "country-capabilities",
            "skills",
            "scenarios",
            "jurisdictions",
        ):
            for locale in LABELS:
                response = client.get(f"/api/v1/metadata/{resource}", params={"locale": locale})
                assert response.status_code == 200, response.text
                rows = response.json()["items"]
                assert rows and all(
                    row["presentation"]["requested_locale"] == locale for row in rows
                )
                if resource == "country-profiles":
                    assert (
                        rows[0]["version_id"] == profile["version_id"]
                        and rows[0]["presentation"]["display_name"]
                        == localized["localized_display_names"][locale]
                    )
                if resource == "jurisdictions":
                    row = next(
                        row for row in rows if row["definition_id"] == jurisdiction["definition_id"]
                    )
                    assert (
                        row["presentation"]["display_name"]
                        == localized["localized_display_names"][locale]
                    )
        presentations = [
            client.get(
                f"/api/v1/regulation-applicability/{result.applicability_result_id}/presentation",
                params={"locale": locale},
            ).json()
            for locale in LABELS
        ]
        assert all(p["result"] == result.model_dump(mode="json") for p in presentations)
        assert all(
            p["presentation"]["status"]["stable_code"] == "APPLICABLE" for p in presentations
        )
        assert (
            client.get("/api/v1/metadata/country-profiles", params={"locale": "fr-FR"}).status_code
            == 422
        )
    with pytest.raises(ValueError):
        publish_config(
            f,
            "COUNTRY_PROFILE",
            {**f["country_payload"], "localized_display": {"fallback_locale": "invalid"}},
        )
    with pytest.raises(ValueError):
        config_service(f).create_draft(
            kind="COUNTRY_PROFILE",
            code="适用",
            display_name="Display only",
            payload={"effective_from": "2025-01-01", **f["country_payload"]},
        )


def test_actual_flow_consumes_linked_h_classification_and_exact_flow_evidence(foundation_i):
    f = foundation_i
    nodes = [str(uuid4()), str(uuid4())]
    flow = str(uuid4())
    with f["sf"]() as s, s.begin():
        for ident in nodes:
            s.add(
                b.DataFlowNodeEntity(
                    flow_node_id=ident,
                    tenant_id=f["tenant"],
                    project_id=f["project"],
                    node_type="SYSTEM",
                    display_name="Formal system",
                    jurisdiction_id=f["juri"],
                )
            )
        s.flush()
        s.add(
            b.DataFlowEdgeEntity(
                flow_edge_id=flow,
                tenant_id=f["tenant"],
                project_id=f["project"],
                source_node_id=nodes[0],
                target_node_id=nodes[1],
                flow_type="TRANSFER",
            )
        )
        s.flush()
        s.add(
            c.DataFlowEdgeDetailEntity(
                flow_edge_id=flow,
                tenant_id=f["tenant"],
                direction="SOURCE_TO_TARGET",
                confidence=1,
                validation_status="VALIDATED",
                version=f["classification"].result.context_version,
            )
        )
        s.add(
            b.DataItemFlowLinkEntity(
                link_id=str(uuid4()),
                tenant_id=f["tenant"],
                data_item_id=f["item"],
                flow_edge_id=flow,
            )
        )
    repo, p = f["compliance_repo"].retrieval, f["policy"]
    response = service(f, repo).retrieve(query(f, p, subject_type="DATA_FLOW", subject_id=flow))
    f["request"] = f["request"].model_copy(
        update={
            "subject_type": "DATA_FLOW",
            "subject_id": UUID(flow),
            "retrieval_run_id": UUID(response["retrieval_run_id"]),
        }
    )
    result = execute(f)
    assert (
        result.applicability_status == "APPLICABLE"
        and result.data_flow_ids == (UUID(flow),)
        and result.data_item_ids == (UUID(f["item"]),)
    )
    with pytest.raises(LookupError):
        f["compliance_repo"].prepare(
            f["request"].model_copy(
                update={"retrieval_run_id": UUID(f["retrieval"]["retrieval_run_id"])}
            )
        )


def test_template_capability_binding_requires_governed_published_version(foundation_i):
    from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
        PostgresGovernedArtifactAdminRepository,
    )

    f = foundation_i
    repo = PostgresGovernedArtifactAdminRepository(f["sf"], f["ctx"], "templates")
    draft = repo.create_draft(
        code=str(uuid4()),
        display_name="Governed resource",
        payload={"template_type": "GENERIC", "content_ref": "test://template"},
    )
    ident = UUID(draft["version_id"])
    with f["sf"]() as session:
        with pytest.raises(ValueError):
            f["compliance_repo"].validate_resource(
                session, m.TemplateVersionEntity, ident, date.today()
            )
    v = repo.transition(ident, target_status="PENDING_REVIEW", expected_record_version=1)
    reviewer = PostgresGovernedArtifactAdminRepository(
        f["sf"],
        RepositoryContext.user(
            UUID(f["tenant"]), "independent-reviewer", set(f["ctx"].permission.scopes)
        ),
        "templates",
    )
    v = reviewer.transition(
        ident, target_status="APPROVED", expected_record_version=v["record_version"]
    )
    repo.transition(ident, target_status="ACTIVE", expected_record_version=v["record_version"])
    with f["sf"]() as session:
        assert (
            f["compliance_repo"]
            .validate_resource(session, m.TemplateVersionEntity, ident, date.today())
            .lifecycle_status
            == "ACTIVE"
        )
