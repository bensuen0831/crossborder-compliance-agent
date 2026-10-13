"""Blank-project business pipeline; measured outcomes from canonical owners."""
from uuid import uuid4
import pytest
from stage1_business_fixtures import business_environment,genuine_docx
from stage1_formal_acceptance import assert_formal_chain

pytestmark=pytest.mark.runtime_smoke

def web_business(f, *, after_confirm=None, input_overrides=None, candidate_action=None, expected_confirmation_failure=None):
    from stage1_business_manifest import load_case,business_facts
    manifest=load_case(f['outcome'])
    c=f['client'];created=c.post('/api/v1/projects',json=dict(name='Stage1 blank business '+uuid4().hex,idempotency_key=uuid4().hex,facts={'analysis_as_of_date':f['facts']['analysis_as_of_date']}))
    assert created.status_code==201,created.text
    v=created.json();assert v['analysis_snapshot_id'] is None and v['status']=='DRAFT'
    f['provision_project_models'](v['project_id'])
    p='/api/v1/projects/'+v['project_id']
    flow=dict(input_key=uuid4().hex,data_item_canonical_name=manifest['data_items'][0],source_jurisdiction_id=f['facts']['source_locations'][0],destination_jurisdiction_id=f['facts']['destination_locations'][0],direction='SOURCE_TO_DESTINATION',source_name=manifest['data_flow']['source'],destination_name=manifest['data_flow']['destination'])
    saved=c.put(p+'/intake',json=dict(expected_version=v['version'],idempotency_key=uuid4().hex,facts={**business_facts(f),'data_flows':[flow],**(input_overrides or {})}));assert saved.status_code==200,saved.text
    version=saved.json()['version']
    upload=c.post(p+'/intake/documents',data=dict(expected_version=version,idempotency_key=uuid4().hex),files={'file':('business.docx',genuine_docx(v['project_id'],semantic_only=f['outcome']=='DIRECT'),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')});assert upload.status_code==201,upload.text
    version=upload.json()['intake_version'];doc=upload.json()['items'][0]['document_version_id']
    parsed=c.post(p+f'/intake/documents/{doc}/parse',json=dict(expected_version=version,idempotency_key=uuid4().hex));assert parsed.status_code==200,parsed.text
    prepared=c.post(p+'/candidate-preparation',json=dict(expected_version=version,idempotency_key=uuid4().hex));assert prepared.status_code==200,(prepared.text,f['failures'])
    preview=prepared.json()
    if not preview['candidates']:
        from sqlalchemy import select
        from crossborder_compliance.infrastructure.persistence import models as b
        with f['sf']() as s:
            audit=s.scalars(select(b.AuditEventEntity).where(b.AuditEventEntity.candidate_preparation_id==preview['candidate_preparation_id'])).all()
            diagnostic=dict(provider_requests=f['provider_requests'],provider_calls=f['provider_calls'],audit=[dict(event=a.event_type,reason=a.provenance_json.get('reason_code')) for a in audit])
        assert preview['candidates'],diagnostic
    decision=c.post(p+'/candidate-decisions',json=dict(expected_version=version,candidate_preparation_id=preview['candidate_preparation_id'],candidate_universe_digest=preview['candidate_universe_digest'],idempotency_key=uuid4().hex,
        decisions=[dict(preparation_candidate_id=i['preparation_candidate_id'],action=candidate_action(i) if candidate_action else 'ACCEPT') for i in preview['candidates']]));assert decision.status_code==200,decision.text
    requests=len(f['provider_requests'])
    confirmed=c.post(p+'/intake/confirm',json=dict(expected_version=version,candidate_decision_set_id=decision.json()['candidate_decision_set_id']))
    if expected_confirmation_failure is not None:
        assert confirmed.status_code==422 and confirmed.json()['detail']==expected_confirmation_failure,confirmed.text
        unchanged=c.get(p+'/intake').json();assert unchanged['status']=='DRAFT' and unchanged['analysis_snapshot_id'] is None and unchanged['workflow_run_id'] is None
        return None,unchanged,preview
    assert confirmed.status_code==200,confirmed.text
    assert len(f['provider_requests'])==requests
    record=confirmed.json()
    if after_confirm:after_confirm(f,record,preview)
    started=c.post(p+f"/snapshots/{record['analysis_snapshot_id']}/workflow",json={});assert started.status_code==200,started.text
    run=started.json()['workflow_run_id']
    result=c.get('/api/v1/workflows/'+run+'/stage1-result');assert result.status_code==200,result.text
    value=result.json()
    import json, os
    from pathlib import Path
    diagnostic=Path(os.getenv('EVIDENCE_DIR','artifacts/stage1-r2'))/'business'
    diagnostic.mkdir(parents=True,exist_ok=True)
    (diagnostic/(f['outcome'].lower()+'_web_result.json')).write_text(json.dumps(value,indent=2)+'\n')
    return value,record,preview

@pytest.mark.parametrize('outcome',['DIRECT','CONDITIONAL','LOCALIZATION','REVIEW'])
def test_blank_project_document_flow_and_four_formal_outcomes(tmp_path,outcome):
    with business_environment(tmp_path,outcome) as f:
        result,record,preview=web_business(f)
        assert result['cross_border'] is not None, {k:result[k] for k in ('status','current_step','reason_codes','classification')}
        from stage1_business_manifest import load_case
        oracle=load_case(outcome)
        assert result['cross_border']['items'][0]['status']==oracle['expected_formal_outcome'],result
        assert result['status']==('REVIEW_REQUIRED' if outcome=='REVIEW' else 'COMPLETED'),result
        assert result['classification'] and len(result['classification'])==2
        assert_formal_chain(f,result,record,preview)
