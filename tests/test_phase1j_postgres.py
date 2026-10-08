"""Real PG canonical E/G/H/I inputs, publication, snapshot pins, isolation and retries."""

# ruff: noqa: F811 -- pytest fixture imports are intentionally injected by name

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError
from test_phase1i_postgres import execute as applicability
from test_phase1i_postgres import (  # noqa: F401 -- shared real-PG fixtures
    fixture,
    foundation_i,
    publish_config,
)
from test_phase1j_contracts import risk_policy

from crossborder_compliance.application.decision_services import (
    PARENTS,
    DecisionRequest,
    FormalDecisionService,
    UpstreamIdentifier,
)
from crossborder_compliance.domain.decision_contracts import canonical, result_digest
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import decision_models as j
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import (
    PostgresCountryComplianceRepository,
)

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def foundation_j(foundation_i, request):
    f = foundation_i
    params = getattr(request, "param", {})
    app = applicability(f)
    scopes = set(f["ctx"].permission.scopes) | {"decision:execute", "decision:read"}
    f["jctx"] = RepositoryContext.user(UUID(f["tenant"]), "author", scopes)
    f["jrepo"] = PostgresCountryComplianceRepository(f["sf"], f["jctx"])
    entry = str(uuid4())
    ob = publish_config(
        f,
        "OBLIGATION_POLICY",
        {
            "jurisdiction_ids": [f["juri"]],
            "entries": [
                {
                    "entry_id": entry,
                    "code": "FORMAL_REQUIREMENT",
                    "jurisdiction_id": f["juri"],
                    "applicability_config_id": f["config"]["definition_id"],
                    "required_rule_ids": f["config_payload"]["required_rule_ids"],
                    "legal_basis_ids": [f["basis"]],
                    **params.get("obligation_entry", {}),
                }
            ],
        },
    )
    path = publish_config(
        f,
        "COMPLIANCE_PATH_POLICY",
        {
            "jurisdiction_ids": [f["juri"]],
            "obligation_policy_id": ob["definition_id"],
            "templates": [
                {
                    "entry_id": str(uuid4()),
                    "path_code": "GOVERNED_PATH",
                    "obligation_entry_ids": [entry],
                    "actions": [
                        {"entry_id": str(uuid4()), "code": "PERFORM_REQUIREMENT", "sequence": 1}
                    ],
                    **params.get("path_template", {}),
                }
            ],
        },
    )
    risk = publish_config(
        f, "RISK_POLICY", risk_policy(jurisdiction_ids=[f["juri"]]).model_dump(mode="json")
    )
    rec = publish_config(
        f,
        "RECOMMENDATION_POLICY",
        {
            "jurisdiction_ids": [f["juri"]],
            "path_policy_id": path["definition_id"],
            "risk_policy_id": risk["definition_id"],
            "criteria": [{"kind": "RISK_SCORE", "direction": "ASC"}],
            "localized_code_labels": {
                "CONDITIONAL_PROPOSAL": {
                    "localized_display_names": {
                        "zh-CN": "条件方案",
                        "zh-HK": "附條件方案",
                        "en-US": "Conditional proposal",
                    },
                    "fallback_locale": "en-US",
                }
            },
        },
    )
    f.update(
        j_app=app,
        j_policies={
            "OBLIGATION_POLICY": ob,
            "COMPLIANCE_PATH_POLICY": path,
            "RISK_POLICY": risk,
            "RECOMMENDATION_POLICY": rec,
        },
    )
    if getattr(request, "param", {}).get("duplicate_risk"):
        publish_config(
            f, "RISK_POLICY", risk_policy(jurisdiction_ids=[f["juri"]]).model_dump(mode="json")
        )
    if params.get("before_j_initialization"):
        params["before_j_initialization"](f)
    f["jrepo"].initialize_decisions(UUID(f["project"]), UUID(f["snapshot"]))
    return f


def request(f, kind, upstream=(), key=None):
    return DecisionRequest(
        project_id=f["project"],
        analysis_snapshot_id=f["snapshot"],
        subject_type=f["request"].subject_type,
        subject_id=f["request"].subject_id,
        stage_kind=kind,
        applicability_result_ids=(f["j_app"].applicability_result_id,),
        upstream_refs=upstream,
        idempotency_key=key or str(uuid4()),
    )


def run_pipeline(f):
    service = FormalDecisionService(f["jrepo"])
    results, requests = {}, {}
    for kind in j.TABLES:
        requests[kind] = request(
            f,
            kind,
            tuple(
                UpstreamIdentifier(kind=k, result_id=results[k].result_id) for k in PARENTS[kind]
            ),
        )
        results[kind] = service.execute(requests[kind])
    return results, requests


def test_actual_pipeline_immutable_refs_and_idempotent_aliases(foundation_j):
    f = foundation_j
    results, requests = run_pipeline(f)
    assert results["FINAL_PATH"].items[0].status == "CONDITIONAL_PROPOSAL"
    for kind, saved in results.items():
        assert result_digest(f["jrepo"].read_decision(kind, saved.result_id)) == result_digest(
            saved
        )
        new_key = requests[kind].model_copy(update={"idempotency_key": str(uuid4())})
        assert FormalDecisionService(f["jrepo"]).execute(new_key).result_id == saved.result_id
        with f["sf"]() as s:
            assert (
                s.scalar(
                    select(func.count())
                    .select_from(j.MODELS[kind])
                    .where(j.MODELS[kind].tenant_id == f["tenant"])
                )
                == 1
            )
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.DecisionRequestKeyEntity)
                .where(j.DecisionRequestKeyEntity.tenant_id == f["tenant"])
            )
            == 10
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.ObligationApplicabilityLinkEntity)
                .where(j.ObligationApplicabilityLinkEntity.tenant_id == f["tenant"])
            )
            == 1
        )


def test_concurrent_same_input_returns_single_authority(foundation_j):
    f = foundation_j
    req = request(f, "OBLIGATION")
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: FormalDecisionService(f["jrepo"]).execute(req), range(3)))
    assert len({r.result_id for r in results}) == 1
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.MODELS["OBLIGATION"])
                .where(j.MODELS["OBLIGATION"].tenant_id == f["tenant"])
            )
            == 1
        )


@pytest.mark.parametrize(
    "resource", ["RESULT", "PIN", "POLICY", "POLICY_STATE", "POLICY_PUBLICATION", "ALIAS"]
)
def test_authority_update_delete_refused(foundation_j, resource):
    f = foundation_j
    results, _ = run_pipeline(f)
    if resource == "RESULT":
        model = j.MODELS["FINAL_PATH"]
        pred = model.result_id == str(results["FINAL_PATH"].result_id)
        changes = {"summary_status": "APPROVED"}
    elif resource == "PIN":
        model = m.AnalysisSnapshotRegistryPinEntity
        pred = (model.tenant_id == f["tenant"]) & model.pin_type.like("PHASE1J_%")
        changes = {"version_no": 99}
    elif resource in {"POLICY", "POLICY_STATE", "POLICY_PUBLICATION"}:
        model = m.MetadataVersionEntity
        pred = model.version_id == f["j_policies"]["RISK_POLICY"]["version_id"]
        changes = (
            {"payload_json": {}}
            if resource == "POLICY"
            else {"lifecycle_status": "DRAFT"}
            if resource == "POLICY_STATE"
            else {"published_at": None}
        )
    else:
        model = j.DecisionRequestKeyEntity
        pred = model.tenant_id == f["tenant"]
        changes = {"input_fingerprint": "f" * 64}
    for op in (update(model).where(pred).values(**changes), delete(model).where(pred)):
        with pytest.raises(DBAPIError), f["sf"]() as s, s.begin():
            s.execute(op)


@pytest.mark.parametrize(
    "actor", ["foreign_tenant", "other_owner", "missing_read", "missing_project"]
)
def test_read_security_isolation(foundation_j, actor):
    f = foundation_j
    result = run_pipeline(f)[0]["FINAL_PATH"]
    scopes = set(f["jctx"].permission.scopes)
    if actor == "missing_read":
        scopes.remove("decision:read")
    if actor == "missing_project":
        scopes.remove(f"project:{f['project']}:comply")
    ctx = RepositoryContext.user(
        uuid4() if actor == "foreign_tenant" else UUID(f["tenant"]),
        "other" if actor == "other_owner" else "author",
        scopes,
    )
    with pytest.raises(LookupError):
        PostgresCountryComplianceRepository(f["sf"], ctx).read_decision(
            "FINAL_PATH", result.result_id
        )


def test_read_requires_no_execute_and_preserves_existing_upstream_scopes(foundation_j):
    f = foundation_j
    result = run_pipeline(f)[0]["FINAL_PATH"]
    scopes = set(f["jctx"].permission.scopes) - {
        "decision:execute",
        "applicability:execute",
        "classification:execute",
    }
    repo = PostgresCountryComplianceRepository(
        f["sf"], RepositoryContext.user(UUID(f["tenant"]), "author", scopes)
    )
    assert repo.read_decision("FINAL_PATH", result.result_id).result_id == result.result_id
    scopes.remove("classification:read")
    with pytest.raises(LookupError):
        PostgresCountryComplianceRepository(
            f["sf"], RepositoryContext.user(UUID(f["tenant"]), "author", scopes)
        ).read_decision("FINAL_PATH", result.result_id)


def test_context_change_requires_new_snapshot(foundation_j):
    f = foundation_j
    result = run_pipeline(f)[0]["FINAL_PATH"]
    with f["sf"]() as s, s.begin():
        s.execute(
            update(c.BusinessFactEntity)
            .where(
                c.BusinessFactEntity.tenant_id == f["tenant"],
                c.BusinessFactEntity.fact_type == "COUNT",
            )
            .values(normalized_value_json=99)
        )
    with pytest.raises((ValueError, LookupError)):
        f["jrepo"].read_decision("FINAL_PATH", result.result_id)


def test_pin_replay_does_not_select_latest_policy(foundation_j):
    f = foundation_j
    results, requests = run_pipeline(f)
    original = f["j_policies"]["RISK_POLICY"]
    fresh = risk_policy(
        jurisdiction_ids=[f["juri"]],
        bands=[
            {"lower": 0, "upper": 50, "band": "MEDIUM"},
            {"lower": 50, "upper": 100, "band": "CRITICAL"},
        ],
        examples=[
            {
                "facts": [{"code": "count", "value": 25}],
                "expected_score": 25,
                "expected_band": "MEDIUM",
            }
        ],
    )
    publish_config(
        f, "RISK_POLICY", fresh.model_dump(mode="json"), definition_id=original["definition_id"]
    )
    assert FormalDecisionService(f["jrepo"]).execute(requests["RISK"]).items[0].risk_level == "LOW"
    assert (
        f["jrepo"].read_decision("FINAL_PATH", results["FINAL_PATH"].result_id).result_id
        == results["FINAL_PATH"].result_id
    )


def test_server_rejects_fabricated_computation(foundation_j):
    f = foundation_j
    req = request(f, "OBLIGATION")
    result = FormalDecisionService(f["jrepo"]).execute(req)
    fake = result.model_copy(
        update={"items": (result.items[0].model_copy(update={"legal_effect": "NOT_APPLICABLE"}),)}
    )
    with pytest.raises(ValueError, match="authorized computation"):
        f["jrepo"].save_decision(req, fake)


@pytest.mark.parametrize(
    "field,value",
    [
        ("facts", {}),
        ("score", 0),
        ("risk_band", "LOW"),
        ("permissions", ["system"]),
        ("locale", "en-US"),
        ("policy_payload", {}),
    ],
)
def test_api_rejects_authoritative_client_fields(foundation_j, field, value):
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.main import app

    f = foundation_j
    app.dependency_overrides[get_repository_context] = lambda: f["jctx"]
    try:
        with TestClient(app) as client:
            body = request(f, "OBLIGATION").model_dump(mode="json")
            body[field] = value
            assert (
                client.post(
                    f"/api/v1/projects/{f['project']}/formal-decisions", json=body
                ).status_code
                == 422
            )
    finally:
        app.dependency_overrides.clear()


def test_locale_presentation_preserves_authority(foundation_j):
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.main import app

    f = foundation_j
    result = run_pipeline(f)[0]["FINAL_PATH"]
    app.dependency_overrides[get_repository_context] = lambda: f["jctx"]
    try:
        with TestClient(app) as client:
            records = [
                client.get(
                    f"/api/v1/formal-decisions/FINAL_PATH/{result.result_id}/presentation",
                    params={"locale": locale},
                )
                for locale in ("zh-CN", "zh-HK", "en-US")
            ]
            assert [r.status_code for r in records] == [200, 200, 200]
            payloads = [r.json() for r in records]
            assert all(p["result"] == payloads[0]["result"] for p in payloads)
            assert (
                len({p["presentation"]["CONDITIONAL_PROPOSAL"]["display_name"] for p in payloads})
                == 3
            )
            assert all(
                p["result"]["items"][0]["support"] == canonical(result.items[0].support)
                for p in payloads
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_actual_scenario_without_fake_classification(foundation_j):
    from crossborder_compliance.infrastructure.persistence.models import ClassificationResultEntity

    f = foundation_j
    final = run_pipeline(f)[0]["FINAL_PATH"]
    assert final.subject_type == "SCENARIO" and not final.data_item_ids
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(ClassificationResultEntity)
                .where(ClassificationResultEntity.tenant_id == f["tenant"])
            )
            == 0
        )


def test_current_evidence_source_revocation_denies_replay(foundation_j):
    f = foundation_j
    final = run_pipeline(f)[0]["FINAL_PATH"]
    source = f["repo"].get_source(f["source"])
    f["repo"].update_source(f["source"], {"enabled": False}, source["record_version"])
    with pytest.raises((LookupError, ValueError)):
        f["jrepo"].read_decision("FINAL_PATH", final.result_id)


def test_published_stable_entry_cannot_be_reassigned(foundation_j):
    f = foundation_j
    original = f["j_policies"]["OBLIGATION_POLICY"]
    with f["sf"]() as s:
        payload = dict(s.get(m.MetadataVersionEntity, original["version_id"]).payload_json)
    payload["entries"] = [{**payload["entries"][0], "entry_id": str(uuid4())}]
    with pytest.raises(ValueError, match="stable policy entry"):
        publish_config(f, "OBLIGATION_POLICY", payload, definition_id=original["definition_id"])


def test_explicit_empty_universe_does_not_adopt_later_published_policy(foundation_i):
    f = foundation_i
    app = applicability(f)
    ctx = RepositoryContext.user(
        UUID(f["tenant"]),
        "author",
        set(f["ctx"].permission.scopes) | {"decision:execute", "decision:read"},
    )
    f.update(jctx=ctx, jrepo=PostgresCountryComplianceRepository(f["sf"], ctx), j_app=app)
    f["jrepo"].initialize_decisions(UUID(f["project"]), UUID(f["snapshot"]))
    publish_config(
        f, "RISK_POLICY", risk_policy(jurisdiction_ids=[f["juri"]]).model_dump(mode="json")
    )
    result = FormalDecisionService(f["jrepo"]).execute(request(f, "OBLIGATION"))
    assert result.summary_status == "INSUFFICIENT_EVIDENCE" and not result.items
    assert not any(p.kind == "RISK_POLICY" for p in result.pins)


def test_same_key_different_authorized_subject_fingerprint_refused(foundation_j):
    from test_phase1g_persistence_postgres import query, service

    from crossborder_compliance.infrastructure.persistence import models as b

    f = foundation_j
    original = request(f, "OBLIGATION", key="FORMAL_KEY")
    FormalDecisionService(f["jrepo"]).execute(original)
    nodes, flow = (str(uuid4()), str(uuid4())), str(uuid4())
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
        link_id = str(uuid4())
        s.add(
            b.DataItemFlowLinkEntity(
                link_id=link_id,
                tenant_id=f["tenant"],
                data_item_id=f["item"],
                flow_edge_id=flow,
            )
        )
        s.flush()
        s.add(c.DataItemFlowLinkDetailEntity(link_id=link_id, tenant_id=f["tenant"], relationship_type="TRANSPORTS", confidence=1, data_inventory_version=f["classification"].result.context_version, source_trace_ids_json=[]))
    response = service(f, f["compliance_repo"].retrieval).retrieve(
        query(f, f["policy"], subject_type="DATA_FLOW", subject_id=flow)
    )
    f["request"] = f["request"].model_copy(
        update={
            "subject_type": "DATA_FLOW",
            "subject_id": UUID(flow),
            "retrieval_run_id": UUID(response["retrieval_run_id"]),
        }
    )
    f["j_app"] = applicability(f)
    changed = request(f, "OBLIGATION", key="FORMAL_KEY")
    with pytest.raises(ValueError, match="idempotency key fingerprint mismatch"):
        FormalDecisionService(f["jrepo"]).execute(changed)
    final = FormalDecisionService(f["jrepo"]).execute(
        changed.model_copy(update={"idempotency_key": "DIFFERENT_KEY"})
    )
    assert final.data_flow_ids == (UUID(flow),) and final.items[0].support.citation_ids


@pytest.mark.parametrize("foundation_j", [{"duplicate_risk": True}], indirect=True)
def test_competing_governed_policies_preserve_conflict(foundation_j):
    final = run_pipeline(foundation_j)[0]["FINAL_PATH"]
    assert final.summary_status == "CONFLICTED"
    assert not final.items or final.items[0].selected_candidate_path_id is None


def test_actual_reference_only_api_pipeline_and_retry(foundation_j):
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.main import app

    f = foundation_j
    app.dependency_overrides[get_repository_context] = lambda: f["jctx"]
    try:
        with TestClient(app) as client:
            saved = {}
            for kind in j.TABLES:
                parents = tuple(
                    UpstreamIdentifier(kind=k, result_id=saved[k]) for k in PARENTS[kind]
                )
                body = request(f, kind, parents).model_dump(mode="json")
                response = client.post(
                    f"/api/v1/projects/{f['project']}/formal-decisions", json=body
                )
                assert response.status_code == 200, response.text
                saved[kind] = response.json()["result"]["result_id"]
                retry = client.post(f"/api/v1/projects/{f['project']}/formal-decisions", json=body)
                assert (
                    retry.status_code == 200 and retry.json()["result"]["result_id"] == saved[kind]
                )
            assert response.json()["result"]["items"][0]["status"] == "CONDITIONAL_PROPOSAL"
    finally:
        app.dependency_overrides.clear()
