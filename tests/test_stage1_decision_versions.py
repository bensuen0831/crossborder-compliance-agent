import ast
import subprocess
from pathlib import Path
import pytest
from phase1j_fixtures import decision_fixture
from pydantic import ValidationError
from crossborder_compliance.application.decision_services import DecisionRequest,calculate,verify_calculation
from crossborder_compliance.domain.decision_contracts import DecisionEngineVersion,ENVELOPE_TYPES

ROOT=Path(__file__).resolve().parents[1]
SOURCE='4c79243bbfa22108f1005c8e92265e2137012d4d'
PARENTS={'OBLIGATION':(), 'CANDIDATE_PATH':('OBLIGATION',),'RISK':('CANDIDATE_PATH',),
 'RECOMMENDATION':('CANDIDATE_PATH','RISK'),'FINAL_PATH':('OBLIGATION','CANDIDATE_PATH','RISK','RECOMMENDATION')}

def test_legacy_helper_is_exact_frozen_source_semantics():
    old=ast.parse(subprocess.check_output(['git','show',SOURCE+':src/crossborder_compliance/domain/decision_engine.py'],cwd=ROOT))
    expected=next(node for node in old.body if isinstance(node,ast.FunctionDef) and node.name=='merge_support')
    actual=ast.parse((ROOT/'src/crossborder_compliance/domain/decision_calculation_versions.py').read_text())
    actual=next(node for node in actual.body if isinstance(node,ast.FunctionDef) and node.name=='legacy_merge_support')
    actual.name='merge_support'
    assert ast.dump(expected)==ast.dump(actual)

def test_versions_are_explicit_and_uniform_across_every_stage():
    inputs=decision_fixture();legacy={};current={}
    for stage,parents in PARENTS.items():
        legacy[stage]=verify_calculation(stage,inputs,{p:legacy[p] for p in parents},DecisionEngineVersion.LEGACY)
        current[stage]=calculate(stage,inputs,{p:current[p] for p in parents})
        assert legacy[stage].engine_version==legacy[stage].provenance.engine_version=='FORMAL_DECISION_V2'
        assert current[stage].engine_version==current[stage].provenance.engine_version=='FORMAL_DECISION_V2_1'
    assert not legacy['CANDIDATE_PATH'].items[0].support.evidence_ids
    assert current['CANDIDATE_PATH'].items[0].support.evidence_ids
    with pytest.raises(ValueError):verify_calculation('OBLIGATION',inputs,{},'UNTRUSTED_VERSION')
    with pytest.raises(ValueError,match='MIXED_ENGINE'):
        calculate('CANDIDATE_PATH',inputs,{'OBLIGATION':legacy['OBLIGATION']})
    with pytest.raises(ValidationError):
        DecisionRequest(project_id=inputs.identity.project_id,analysis_snapshot_id=inputs.identity.analysis_snapshot_id,
            subject_type=inputs.identity.subject_type,subject_id=inputs.identity.subject_id,stage_kind='OBLIGATION',
            applicability_result_ids=[inputs.applicability[0].applicability_result_id],idempotency_key='caller',engine_version='FORMAL_DECISION_V2')

def test_envelope_provenance_mismatch_and_unknown_version_fail_closed():
    value=calculate('OBLIGATION',decision_fixture(),{}).model_dump(mode='json')
    value['provenance']['engine_version']='FORMAL_DECISION_V2'
    with pytest.raises(ValidationError,match='ENGINE_VERSION_MISMATCH'):ENVELOPE_TYPES['OBLIGATION'].model_validate(value)
    value['engine_version']='UNKNOWN'
    with pytest.raises(ValidationError):ENVELOPE_TYPES['OBLIGATION'].model_validate(value)
