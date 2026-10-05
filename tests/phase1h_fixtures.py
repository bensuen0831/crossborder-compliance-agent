from datetime import date
from uuid import uuid4

from crossborder_compliance.domain.classification import ClassificationScheme
from crossborder_compliance.domain.rules import (
    ComplianceRule,
    RuleContract,
    RuleFactContext,
    RuleTestCase,
)


def contract(scheme, jurisdiction, category, **overrides):
    return RuleContract.model_validate(
        {
            "fields": {"count": {"kind": "integer"}},
            "conditions": {"op": "gte", "field": "count", "value": 3},
            "actions": [
                {
                    "scheme_version_id": str(scheme),
                    "category_ids": [str(category)],
                    "reason_code": "COUNT_RULE",
                }
            ],
            "scope": {"jurisdiction_ids": [str(jurisdiction)]},
            "severity": "HIGH",
            "priority": 100,
            "evidence_required": ["DOCUMENT"],
            "effective_from": "2025-01-01",
            **overrides,
        }
    )


def cases(c):
    return (
        RuleTestCase(
            facts={"count": 3},
            expected_match=True,
            expected_actions=c.actions,
            expected_severity=c.severity,
            expected_evidence_requirement=c.evidence_required,
        ),
        RuleTestCase(
            facts={"count": 2},
            expected_match=False,
            expected_actions=(),
            expected_severity=None,
            expected_evidence_requirement=(),
        ),
    )


def domain_fixture():
    tenant, project, snapshot, item, jurisdiction, scheme, version, category = [
        uuid4() for _ in range(8)
    ]
    c = contract(version, jurisdiction, category)
    r = ComplianceRule(
        rule_id=uuid4(),
        rule_version_id=uuid4(),
        tenant_id=tenant,
        version=1,
        contract=c,
        lifecycle="ACTIVE",
        approved_by="reviewer",
        published_by="publisher",
    )
    f = RuleFactContext(
        tenant_id=tenant,
        project_id=project,
        analysis_snapshot_id=snapshot,
        context_version=1,
        data_item_id=item,
        jurisdiction_id=jurisdiction,
        as_of=date(2026, 1, 1),
        values={"count": 3},
        fact_refs={"count": (uuid4(),)},
        evidence_ids=(uuid4(),),
        evidence_types=("DOCUMENT",),
    )
    s = ClassificationScheme(
        scheme_id=scheme,
        scheme_version_id=version,
        tenant_id=tenant,
        jurisdiction_ids=(jurisdiction,),
        version=1,
        categories=({"category_id": category, "code": "CATEGORY"},),
        levels=(),
        lifecycle="ACTIVE",
    )
    return r, f, s
