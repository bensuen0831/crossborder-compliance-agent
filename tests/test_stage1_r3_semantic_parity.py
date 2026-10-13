from copy import deepcopy
import pytest
from stage1_semantic_parity import formal_difference

@pytest.mark.parametrize('path',[('cross_border','status'),('risk','risk_level'),('classification','jurisdiction_id'),('support','evidence_ids'),('support','legal_basis_ids'),('support','fact_refs'),('reason_codes','codes')])
def test_formal_difference_preserves_legal_support_and_semantic_changes(path):
    original={'cross_border':{'status':'CONDITIONAL_TRANSFER_ALLOWED'},'risk':{'risk_level':'HIGH'},'classification':{'jurisdiction_id':'authorized-jurisdiction'},'support':{'evidence_ids':['authorized-source'],'legal_basis_ids':['pinned-legal-basis'],'fact_refs':['count:3']},'reason_codes':{'codes':['FORMAL_REASON']}}
    changed=deepcopy(original);changed[path[0]][path[1]]=[] if isinstance(changed[path[0]][path[1]],list) else 'CHANGED'
    assert formal_difference(original,changed)==['/'+path[0]+'/'+path[1]+(':length' if isinstance(original[path[0]][path[1]],list) else '')]

@pytest.mark.runtime_smoke
def test_actual_result_normalizer_rejects_lost_support_jurisdiction_and_outcome(tmp_path):
    from stage1_business_fixtures import business_environment
    from test_stage1_business_http import web_business
    from stage1_semantic_parity import normalize_formal
    from crossborder_compliance.domain.decision_contracts import LegalSupport
    with business_environment(tmp_path,'DIRECT') as f:
        result,_,_=web_business(f);original=normalize_formal(f,result)
        for field in LegalSupport.model_fields:
            mutated=deepcopy(result)
            current=mutated['final_path']['items'][0]['support'][field]
            mutated['final_path']['items'][0]['support'][field]=[] if current else ['untrusted-injected-source']
            assert normalize_formal(f,mutated)!=original,field
        for section,field in [('cross_border','status'),('risk','risk_level')]:
            mutated=deepcopy(result);mutated[section]['items'][0][field]='TAMPERED'
            assert normalize_formal(f,mutated)!=original
        mutated=deepcopy(result);mutated['classification'][0]['jurisdiction_id']='unknown-jurisdiction'
        assert normalize_formal(f,mutated)!=original
