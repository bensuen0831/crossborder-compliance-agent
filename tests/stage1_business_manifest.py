"""Acceptance input/oracle only; never imported by product code."""
import json
from pathlib import Path
CASES={'DIRECT':'TC-01','CONDITIONAL':'TC-02','LOCALIZATION':'TC-03','REVIEW':'TC-04'}
def load_case(outcome):
    case=json.loads((Path(__file__).parent/'e2e/stage1/business_cases'/f'{CASES[outcome]}.json').read_text())
    assert case['fixture_kind']=='SYNTHETIC_GOVERNED_TEST_DATA'
    assert case['source_jurisdiction']!=case['destination_jurisdiction']
    assert case['stage2_started'] is False
    return case

def business_facts(f):
    manifest=load_case(f['outcome']);mode=manifest['ai_mode']
    assert mode in ('AUTO','SINGLE','MULTI_MODEL')
    selection=[] if mode=='AUTO' else f['model_ids'][:1] if mode=='SINGLE' else f['model_ids']
    return {**f['facts'],'ai_model_preference':dict(usage_mode='ENHANCED' if mode=='MULTI_MODEL' else 'STANDARD',selection_mode=mode,selected_model_ids=selection)}
