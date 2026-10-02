from uuid import uuid4

import pytest
from phase1h_fixtures import cases, domain_fixture

from crossborder_compliance.application.classification_services import ClassificationService
from crossborder_compliance.domain.classification import ClassificationPolicy, classify
from crossborder_compliance.domain.rules import SafeRuleEngine, run_rule_tests, validate_conflicts


def evaluate(r, f, **kwargs):
    return SafeRuleEngine().evaluate(
        (r,), f, pinned_versions=frozenset({r.rule_version_id}), **kwargs
    )


def test_match_provenance_and_classification():
    r, f, s = domain_fixture()
    run_rule_tests(r.contract, cases(r.contract))
    hits = evaluate(r, f)
    out = classify(s, f, hits)
    assert out.status == "CLASSIFIED"
    assert out.result.rule_hit_ids == (hits[0].rule_hit_id,)
    assert out.result.source_fact_refs == f.fact_refs["count"]
    assert out.result.evidence_ids == f.evidence_ids
    assert out.result.scheme_version_id == s.scheme_version_id


def test_nonmatch_and_evidence_requirements():
    r, f, s = domain_fixture()
    assert not evaluate(r, f.model_copy(update={"values": {"count": 2}}))[0].matched
    missing = f.model_copy(update={"evidence_types": ("OTHER",)})
    assert evaluate(r, missing)[0].review_required
    assert classify(s, missing, evaluate(r, missing)).status == "INSUFFICIENT_INPUT"


def test_nonmatched_rule_does_not_demand_unused_evidence_review():
    r, f, _ = domain_fixture()
    f = f.model_copy(update={"values": {"count": 2}, "evidence_ids": (), "evidence_types": ()})
    hit = evaluate(r, f)[0]
    assert not hit.matched and not hit.review_required
    assert hit.evidence_requirement == ()
    reviewed = evaluate(r, f.model_copy(update={"review_required": True}))[0]
    assert reviewed.review_required


@pytest.mark.parametrize("status", ["DRAFT", "PENDING_REVIEW", "APPROVED", "SUPERSEDED", "EXPIRED"])
def test_inactive_rule_rejected_for_new_evaluation(status):
    r, f, _ = domain_fixture()
    with pytest.raises(ValueError):
        evaluate(r.model_copy(update={"lifecycle": status}), f)


def test_snapshot_history_and_effective_date():
    r, f, _ = domain_fixture()
    old = r.model_copy(update={"lifecycle": "SUPERSEDED"})
    assert evaluate(old, f, historical=True)[0].matched
    c = r.contract.model_copy(update={"effective_to": f.as_of.replace(year=2025)})
    assert evaluate(r.model_copy(update={"contract": c}), f) == ()
    with pytest.raises(ValueError, match="pinned"):
        SafeRuleEngine().evaluate((r,), f, pinned_versions=frozenset())


def test_priority_conflicts_and_multiple_hits():
    r, f, s = domain_fixture()
    same = r.model_copy(update={"rule_id": uuid4(), "rule_version_id": uuid4()})
    hits = SafeRuleEngine().evaluate(
        (r, same), f, pinned_versions=frozenset({r.rule_version_id, same.rule_version_id})
    )
    assert len(classify(s, f, hits).result.rule_hit_ids) == 2
    action = r.contract.actions[0].model_copy(update={"reason_code": "DIFFERENT"})
    other = same.model_copy(
        update={"contract": r.contract.model_copy(update={"actions": (action,)})}
    )
    with pytest.raises(ValueError, match="ambiguous"):
        validate_conflicts((r, other))
    other = other.model_copy(
        update={"contract": other.contract.model_copy(update={"priority": 200})}
    )
    validate_conflicts((r, other))
    hits = SafeRuleEngine().evaluate(
        (r, other), f, pinned_versions=frozenset({r.rule_version_id, other.rule_version_id})
    )
    assert hits[0].priority == 200


@pytest.mark.parametrize(
    "field", ["tenant_id", "project_id", "analysis_snapshot_id", "data_item_id"]
)
def test_rule_hit_isolation(field):
    r, f, s = domain_fixture()
    hits = evaluate(r, f)
    with pytest.raises(LookupError):
        classify(s, f, (hits[0].model_copy(update={field: uuid4()}),))


def test_scheme_jurisdiction_and_version_isolation():
    r, f, s = domain_fixture()
    with pytest.raises(LookupError):
        classify(s.model_copy(update={"jurisdiction_ids": (uuid4(),)}), f, evaluate(r, f))
    assert (
        classify(s.model_copy(update={"scheme_version_id": uuid4()}), f, evaluate(r, f)).status
        == "INSUFFICIENT_INPUT"
    )


def test_no_data_policy_no_fabrication():
    r, f, s = domain_fixture()

    class Repo:
        def prepare(self, *args):
            return f.model_copy(update={"data_item_id": None}), s, (r,)

        def save(self, outcome):
            pytest.fail("no data outcome must not persist classification")

    args = dict(
        project_id=f.project_id,
        snapshot_id=f.analysis_snapshot_id,
        data_item_id=None,
        scheme_version_id=s.scheme_version_id,
    )
    assert ClassificationService(Repo()).execute(**args).status == "NOT_APPLICABLE"
    assert (
        ClassificationService(Repo(), ClassificationPolicy(no_data="INSUFFICIENT_INPUT"))
        .execute(**args)
        .result
        is None
    )


def test_fail_test_gate_and_review_confidence():
    r, f, s = domain_fixture()
    with pytest.raises(ValueError, match="test failed"):
        run_rule_tests(
            r.contract, (cases(r.contract)[0].model_copy(update={"expected_match": False}),)
        )
    f = f.model_copy(update={"confidence": 0.75, "review_required": True})
    out = classify(s, f, evaluate(r, f))
    assert out.status == "REVIEW_REQUIRED" and out.result.confidence == 0.75
