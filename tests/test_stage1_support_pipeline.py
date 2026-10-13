"""PostgreSQL exact-authority propagation and historical read regression."""
# ruff: noqa: F401 -- imported PostgreSQL fixture graph
from uuid import UUID

import pytest
from test_phase1j_postgres import fixture, foundation_i, foundation_j, run_pipeline

from crossborder_compliance.domain.decision_contracts import LegalSupport

pytestmark=pytest.mark.runtime_smoke


def assert_union(actual, sources):
    sources=tuple(sources)
    for field in LegalSupport.model_fields:
        expected=tuple(sorted({ref for source in sources for ref in getattr(source,field)},key=str))
        assert getattr(actual,field)==expected,field


@pytest.mark.parametrize('foundation_i',[{}, {'no_data':True}],indirect=True)
def test_exact_pinned_upstream_support_and_immutable_saved_replay(foundation_j):
    f=foundation_j
    results,requests=run_pipeline(f)
    o,c,r,rec,final=(results[k] for k in ('OBLIGATION','CANDIDATE_PATH','RISK','RECOMMENDATION','FINAL_PATH'))
    inputs,_=f['jrepo'].prepare_decision(requests['OBLIGATION'])
    entry=inputs.policy('OBLIGATION_POLICY').config.entries[0]
    matched=[hit for hit in inputs.rule_hits if hit.matched and hit.rule_id in entry.required_rule_ids]
    authority=LegalSupport(applicability_result_ids=tuple(a.applicability_result_id for a in inputs.applicability),
        rule_hit_ids=tuple(h.rule_hit_id for h in matched),rule_version_ids=tuple(h.rule_version_id for h in matched),legal_basis_ids=entry.legal_basis_ids)
    assert_union(o.items[0].support,(inputs.support,authority))
    by_obligation={item.obligation_id:item for item in o.items}
    for item in c.items:
        assert_union(item.support,(by_obligation[ref].support for ref in item.obligation_ids))
    by_path={item.candidate_path_id:item for item in c.items}
    for item in r.items:
        assert_union(item.support,(by_path[item.candidate_path_id].support,))
    for item in rec.items:assert_union(item.support,(p.support for p in c.items))
    for item in final.items:assert_union(item.support,(v.support for v in o.items))
    for kind,result in results.items():
        assert result.analysis_snapshot_id==UUID(f['snapshot'])
        assert result.subject_id==f['request'].subject_id
        assert result.pins==result.provenance.pins
        saved=f['jrepo'].read_decision(kind,result.result_id)
        assert saved==result
        original=saved.model_dump(mode='json')
        assert f['jrepo'].read_decision(kind,result.result_id).model_dump(mode='json')==original
        for item in result.items:
            assert item.support.legal_basis_ids and item.support.evidence_ids
            if any(hit.matched for hit in inputs.rule_hits):assert item.support.rule_hit_ids
            else:assert not item.support.rule_hit_ids
            assert item.support.knowledge_version_ids
            assert item.support.citation_ids and item.support.fact_refs
