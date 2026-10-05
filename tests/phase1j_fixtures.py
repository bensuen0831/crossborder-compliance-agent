from datetime import datetime, timezone
from uuid import uuid4

from phase1i_fixtures import prepared
from test_phase1j_contracts import risk_policy

from crossborder_compliance.domain.decision_contracts import LegalSupport, PinRef
from crossborder_compliance.domain.decision_engine import (
    AuthorizedFact,
    DecisionIdentity,
    PinnedDecisionPolicy,
    PreparedDecisionInput,
)
from crossborder_compliance.domain.decision_policies import (
    CompliancePathPolicy,
    ObligationPolicy,
    RecommendationPolicy,
)
from crossborder_compliance.domain.regulation_applicability import RegulationApplicabilitySkill


def decision_fixture(*, paths=1, risk_value=25):
    original = prepared()
    app = RegulationApplicabilitySkill().execute(original)
    entry = uuid4()
    obligation = ObligationPolicy(
        effective_from=original.analysis_as_of_date,
        jurisdiction_ids=(app.jurisdiction_id,),
        entries=(
            {
                "entry_id": entry,
                "code": "FORMAL_REQUIREMENT",
                "jurisdiction_id": app.jurisdiction_id,
                "applicability_config_id": app.applicability_config_id,
                "required_rule_ids": [original.rule_hits[0].rule_id],
                "legal_basis_ids": app.legal_basis_ids,
            },
        ),
    )
    ids = {
        k: uuid4()
        for k in (
            "OBLIGATION_POLICY",
            "COMPLIANCE_PATH_POLICY",
            "RISK_POLICY",
            "RECOMMENDATION_POLICY",
        )
    }
    path = CompliancePathPolicy(
        effective_from=original.analysis_as_of_date,
        jurisdiction_ids=(app.jurisdiction_id,),
        obligation_policy_id=ids["OBLIGATION_POLICY"],
        templates=tuple(
            {
                "entry_id": uuid4(),
                "path_code": f"PATH_{n}",
                "obligation_entry_ids": [entry],
                "actions": [{"entry_id": uuid4(), "code": "PERFORM_REQUIREMENT", "sequence": 1}],
            }
            for n in range(paths)
        ),
    )
    risk = risk_policy(jurisdiction_ids=[app.jurisdiction_id])
    rec = RecommendationPolicy(
        effective_from=original.analysis_as_of_date,
        jurisdiction_ids=(app.jurisdiction_id,),
        path_policy_id=ids["COMPLIANCE_PATH_POLICY"],
        risk_policy_id=ids["RISK_POLICY"],
        criteria=({"kind": "RISK_SCORE", "direction": "ASC"},),
    )
    configs = dict(zip(ids, (obligation, path, risk, rec)))
    pins = tuple(
        PinRef(pin_id=uuid4(), kind=k, object_id=ids[k], version_id=uuid4(), version_no=1)
        for k in ids
    )
    support = LegalSupport(
        applicability_result_ids=(app.applicability_result_id,),
        rule_hit_ids=app.rule_hit_ids,
        rule_version_ids=tuple(h.rule_version_id for h in original.rule_hits),
        legal_basis_ids=app.legal_basis_ids,
        evidence_ids=app.evidence_ids,
        evidence_pack_ids=app.evidence_pack_ids,
        knowledge_version_ids=(app.regulation_version_ref,),
        structure_node_ids=app.regulatory_structure_node_ids,
        fact_refs=original.fact_refs,
    )
    identity = DecisionIdentity(
        **{k: getattr(app, k) for k in DecisionIdentity.model_fields if hasattr(app, k)},
        project_version_id=uuid4(),
        jurisdiction_ids=(app.jurisdiction_id,),
    )
    return PreparedDecisionInput(
        identity=identity,
        applicability=(app,),
        rule_hits=original.rule_hits,
        facts=(
            AuthorizedFact(
                code="count",
                value=risk_value,
                fact_refs=original.fact_refs,
                evidence_ids=app.evidence_ids,
            ),
        ),
        authorized_evidence_ids=app.evidence_ids,
        support=support,
        policies=tuple(PinnedDecisionPolicy(pin=p, config=configs[p.kind]) for p in pins),
        pins=pins,
        capabilities=(),
        prepared_at=datetime.now(timezone.utc),
        actor_ref="trusted",
        request_id="r",
        correlation_id="c",
    )
