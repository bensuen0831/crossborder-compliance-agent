from uuid import uuid4
import pytest
from test_stage1_candidate_governance_http import governed_http,prepare

pytestmark=pytest.mark.runtime_smoke

def test_server_owned_preparation_discovery_is_exact_draft_scoped(governed_http):
    f=governed_http;c=f['client'];path=f['path']
    before=c.get(path+'/intake');assert before.status_code==200 and before.json()['candidate_preparation_id'] is None
    prepared=prepare(f)
    after=c.get(path+'/intake');assert after.status_code==200
    assert after.json()['candidate_preparation_id']==prepared['candidate_preparation_id']
    changed=c.put(path+'/intake',json=dict(expected_version=f['version'],idempotency_key=uuid4().hex,facts={**f['facts'],'scenario_description':'Changed governed draft'}))
    assert changed.status_code==200 and changed.json()['candidate_preparation_id'] is None
    assert c.get(path+'/intake').json()['candidate_preparation_id'] is None

def test_client_cannot_inject_preparation_discovery_authority(governed_http):
    f=governed_http
    response=f['client'].put(f['path']+'/intake',json=dict(expected_version=f['version'],idempotency_key=uuid4().hex,facts=f['facts'],candidate_preparation_id=str(uuid4())))
    assert response.status_code==422
    assert f['client'].get(f['path']+'/intake').json()['candidate_preparation_id'] is None
