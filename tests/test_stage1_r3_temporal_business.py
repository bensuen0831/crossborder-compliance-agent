"""Real blank-project results, explicit successor consent and current owners."""
import copy,json
from uuid import UUID,uuid4
from functools import partial
import pytest
from sqlalchemy import select
from stage1_business_fixtures import business_environment
from test_stage1_business_http import web_business
from stage1_external_business import external_business
from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
from crossborder_compliance.infrastructure.persistence import models as b,metadata_models as m
from crossborder_compliance.infrastructure.persistence.candidate_governance import content_digest
pytestmark=pytest.mark.runtime_smoke

def snapshot_digest(f,snapshot):
    with f['sf']() as s:
        row=s.get(b.AnalysisSnapshotEntity,snapshot)
        pins=s.scalars(select(m.AnalysisSnapshotRegistryPinEntity).where(m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id==snapshot)).all()
        return content_digest({c.name:getattr(row,c.name) for c in row.__table__.columns}),content_digest(sorted([{c.name:getattr(p,c.name) for c in p.__table__.columns} for p in pins],key=lambda p:json.dumps(p,default=str,sort_keys=True)))

def source_decision_set(f,snapshot):
    with f['sf']() as s:return s.get(b.AnalysisSnapshotEntity,snapshot).provenance_json['candidate_decision_set_id']

def decisions(preview):
    return [dict(preparation_candidate_id=c['preparation_candidate_id'],action='ACCEPT') for c in preview['candidates']]

@pytest.mark.parametrize('channel',['web','external','external_evidence_gap'])
def test_new_successor_requires_new_authorization_and_preserves_completed_result(tmp_path,channel):
    with business_environment(tmp_path,'DIRECT') as f:
        def sequel(f,sdk,worker,old,record,preview):
            project=record['project_id'];snapshot=record['analysis_snapshot_id'];before=snapshot_digest(f,snapshot)
            if sdk:
                successor=sdk.create_successor(project,record['version'],uuid4().hex)
                draft=sdk.get_intake(project)
            else:
                path='/api/v1/projects/'+project
                response=f['client'].post(path+'/intake/supersede',json=dict(expected_version=record['version'],idempotency_key=uuid4().hex));assert response.status_code==200,response.text
                successor=response.json();draft=f['client'].get(path+'/intake').json()
            assert draft['status']=='DRAFT'
            version=draft['version']
            from crossborder_compliance.application.intake_services import IntakeFacts
            facts={k:v for k,v in draft['intake'].items() if k in IntakeFacts.model_fields}
            if channel=='external_evidence_gap':facts['business_purpose']='User clarified future processing purpose'
            else:facts['data_volume']='4'
            # A changed document is a new genuine version, not an attachment-only edit.
            from stage1_business_fixtures import genuine_docx
            import io
            if sdk:
                uploaded=sdk.upload_document(project,io.BytesIO(genuine_docx(project+'-successor',semantic_only=True)),'business.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',version,uuid4().hex)
                version=uploaded['intake_version'];sdk.parse_document(project,uploaded['items'][-1]['document_version_id'],version,uuid4().hex)
            else:
                response=f['client'].post(path+'/intake/documents',data=dict(expected_version=version,idempotency_key=uuid4().hex),files={'file':('business.docx',genuine_docx(project+'-successor',semantic_only=True),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')});assert response.status_code==201,response.text
                uploaded=response.json();version=uploaded['intake_version'];response=f['client'].post(path+'/intake/documents/'+uploaded['items'][-1]['document_version_id']+'/parse',json=dict(expected_version=version,idempotency_key=uuid4().hex));assert response.status_code==200,response.text
            if sdk:
                draft=sdk.update_intake(project,dict(expected_version=version,facts=facts),uuid4().hex);version=draft['version']
                f['refresh_models']()
                prepared=sdk.prepare_candidates(project,version,uuid4().hex)
                assert prepared['candidates'],f['failures']
                receipt=sdk.resolve_candidates(project,dict(expected_version=version,candidate_preparation_id=prepared['candidate_preparation_id'],candidate_universe_digest=prepared['candidate_universe_digest'],decisions=decisions(prepared)),uuid4().hex)
                new=sdk.confirm(project,version,uuid4().hex,candidate_decision_set_id=receipt['candidate_decision_set_id'])
                sdk.start_analysis(project,new['analysis_snapshot_id'],uuid4().hex);sdk.wait_for_completion(new['workflow_run_id'],timeout=180,interval=1)
                result=sdk.get_result(new['workflow_run_id']);reread=sdk.get_result(record['workflow_run_id'])
            else:
                response=f['client'].put(path+'/intake',json=dict(expected_version=version,facts=facts,idempotency_key=uuid4().hex));assert response.status_code==200,response.text
                version=response.json()['version']
                stale=f['client'].post(path+'/intake/confirm',json=dict(expected_version=version,candidate_decision_set_id=source_decision_set(f,snapshot)))
                assert stale.status_code==409
                f['refresh_models']()
                response=f['client'].post(path+'/candidate-preparation',json=dict(expected_version=version,idempotency_key=uuid4().hex));assert response.status_code==200,response.text
                prepared=response.json();assert prepared['candidates']
                receipt=f['client'].post(path+'/candidate-decisions',json=dict(expected_version=version,candidate_preparation_id=prepared['candidate_preparation_id'],candidate_universe_digest=prepared['candidate_universe_digest'],decisions=decisions(prepared),idempotency_key=uuid4().hex));assert receipt.status_code==200,receipt.text
                response=f['client'].post(path+'/intake/confirm',json=dict(expected_version=version,candidate_decision_set_id=receipt.json()['candidate_decision_set_id']));assert response.status_code==200,response.text
                new=response.json();response=f['client'].post(path+f"/snapshots/{new['analysis_snapshot_id']}/workflow",json={});assert response.status_code==200,response.text
                result=f['client'].get('/api/v1/workflows/'+new['workflow_run_id']+'/stage1-result').json();reread=f['client'].get('/api/v1/workflows/'+record['workflow_run_id']+'/stage1-result').json()
            assert new['analysis_snapshot_id']!=snapshot and new['workflow_run_id']!=record['workflow_run_id']
            assert prepared['candidate_preparation_id']!=preview['candidate_preparation_id']
            if channel=='external_evidence_gap':
                # The client has no arbitrary prompt-use grant. An unmatched
                # knowledge query must stay insufficient, never fabricate law.
                assert result['status']=='WARNING' and 'JURISDICTION_SPECIFIC_EVIDENCE_MISSING' in result['reason_codes']
                assert result['final_path'] is None and result['risk'] is None
            else:
                assert result['status']=='COMPLETED', {k:result[k] for k in ('status','reason_codes','capability_gaps','current_step')}
                assert result['final_path']['engine_version']=='FORMAL_DECISION_V2_1'
            assert new['intake']['business_purpose']!=record['intake']['business_purpose'] if channel=='external_evidence_gap' else new['intake']['data_volume']!=record['intake']['data_volume']
            if channel!='external_evidence_gap':
                from crossborder_compliance.infrastructure.persistence import context_models as c
                with f['sf']() as s:
                    fact=s.scalar(select(c.BusinessFactEntity).where(c.BusinessFactEntity.project_id==project,c.BusinessFactEntity.version==result['project']['formal_context_version'],c.BusinessFactEntity.fact_type=='COUNT'))
                    assert fact.normalized_value_json==4
            assert reread==old and snapshot_digest(f,snapshot)==before
            assert new['intake']['analysis_as_of_date']==record['intake']['analysis_as_of_date']
        if channel.startswith('external'):external_business(f,after_result=sequel)
        else:
            result,record,preview=web_business(f);sequel(f,None,None,result,record,preview)

def test_blank_document_project_same_snapshot_review_reexecutes_owner(tmp_path):
    with business_environment(tmp_path,'DIRECT') as f:
        f['app'].state.intake_snapshot_preparer=partial(prepare_snapshot,requirement_confirmation=True)
        result,record,preview=web_business(f)
        assert result['status']=='REVIEW_REQUIRED' and result['review_id']
        path='/api/v1/reviews/'+result['review_id'];response=f['client'].get(path);assert response.status_code==200,response.text
        task=response.json()
        assert 'APPROVE' in task['allowed_actions']
        requests=len(f['provider_requests'])
        body=dict(decision='APPROVE',expected_record_version=task['record_version'],idempotency_key=uuid4().hex)
        response=f['client'].post(path+'/decisions',json=body);assert response.status_code==200,response.text
        assert response.json()['continuation_status']=='CONTINUED'
        assert f['client'].post(path+'/decisions',json=body).json()==response.json()
        done=f['client'].get('/api/v1/workflows/'+record['workflow_run_id']+'/stage1-result').json()
        assert done['status']=='COMPLETED' and done['analysis_snapshot_id']==record['analysis_snapshot_id']
        assert len(f['provider_requests'])==requests
        assert done['final_path']['engine_version']=='FORMAL_DECISION_V2_1'
        assert len(response.json()['history'])==1

def test_future_published_knowledge_rule_model_and_prompt_cannot_change_saved_business(tmp_path):
    from phase1g_fixtures import publish as publish_knowledge
    from test_phase1f_postgres import binding
    from test_phase1h_postgres import publish as publish_rule
    from test_phase1k_a_configuration_postgres import publish as publish_metadata
    from test_phase1kb_control_postgres import publish as publish_model
    from test_phase1c_model_registry import _ctx
    from crossborder_compliance.infrastructure.persistence.rule_admin_repository import PostgresRuleAdminRepository
    from crossborder_compliance.infrastructure.persistence.model_control import PostgresModelControlRepository
    from crossborder_compliance.infrastructure.persistence.config_admin_repositories import PostgresGovernedArtifactAdminRepository
    from crossborder_compliance.domain.model_control import ModelDraft
    from crossborder_compliance.domain.rules import RuleContract,RuleTestCase
    from crossborder_compliance.domain.security import RepositoryContext
    with business_environment(tmp_path,'DIRECT') as f:
        result,record,preview=web_business(f);source=record['analysis_snapshot_id'];before=snapshot_digest(f,source)
        future=publish_knowledge(f,[binding(f,dimensions={'product':[f['a']],'jurisdiction':[f['juri']]})])
        assert future['knowledge_version_id']!=f['knowledge_version']
        f['repo'].build_index(future['knowledge_version_id'])
        owner=PostgresRuleAdminRepository(f['sf'],f['ctx'])
        with f['sf']() as s:
            definition=s.get(m.RuleDefinitionEntity,f['rule']['definition_id']);payload=copy.deepcopy(s.get(m.RuleVersionEntity,definition.active_version_id).runtime_contract_json)
        payload['conditions']={'op':'eq','field':'processing_purpose','value':'future-only-purpose'}
        contract=RuleContract.model_validate(payload)
        cases=[RuleTestCase(facts={'count':3,'processing_purpose':value},expected_match=match,expected_actions=contract.actions if match else (),expected_severity=contract.severity if match else None,expected_evidence_requirement=contract.evidence_required if match else ()) for value,match in [('future-only-purpose',True),('service-processing',False)]]
        draft=owner.create_version(UUID(definition.rule_definition_id),{'runtime_contract':contract.model_dump(mode='json'),'tests':[c.model_dump(mode='json') for c in cases]})
        publish_rule(owner,draft,PostgresRuleAdminRepository(f['sf'],RepositoryContext.user(UUID(f['tenant']),'independent-reviewer',set(f['ctx'].permission.scopes))))
        prompt_owner=PostgresGovernedArtifactAdminRepository(f['sf'],_ctx(UUID(f['tenant'])),'prompts')
        draft=prompt_owner.create_draft(code=uuid4().hex,display_name='Published future synthetic prompt',payload={'template_text':'Future proposal wording; never legal authority.','capability_requirement':['STRUCTURED_OUTPUT']})
        published=publish_metadata(prompt_owner,draft)
        assert published['version_id']!=f['prompt']['version_id']
        model_owner=PostgresModelControlRepository(f['sf'],_ctx(UUID(f['tenant'])))
        view=next(m for m in model_owner.list_models(UUID(f['provider_ids'][0])) if m['model_id']==f['model_ids'][0])
        command=ModelDraft.model_validate({k:v for k,v in view.items() if k in ModelDraft.model_fields}|{'model_id':view['model_id'],'expected_record_version':view['model_record_version'],'max_output_tokens':2048,'effective_from':record['intake']['analysis_as_of_date']})
        new_model=publish_model(f['sf'],UUID(f['tenant']),'MODEL',model_owner.save_model(UUID(f['provider_ids'][0]),command))
        assert new_model['deployment_id']!=view['deployment_id']
        reread=f['client'].get('/api/v1/workflows/'+record['workflow_run_id']+'/stage1-result');assert reread.status_code==200,reread.text
        assert reread.json()==result and snapshot_digest(f,source)==before

def test_empty_authorized_knowledge_fails_closed_without_allowed_result(tmp_path):
    from crossborder_compliance.infrastructure.persistence import knowledge_models as k
    with business_environment(tmp_path,'DIRECT') as f:
        with f['sf']() as s:
            sources=s.scalars(select(m.KnowledgeSourceDefinitionEntity).where(m.KnowledgeSourceDefinitionEntity.tenant_id==f['tenant'])).all()
            identities=[(s.knowledge_source_definition_id,s.record_version) for s in sources]
        for identity,version in identities:f['repo'].update_source(identity,{'enabled':False},version)
        result,record,preview=web_business(f,expected_confirmation_failure='new applicability pin requires authorized effective ACTIVE READY knowledge already in snapshot scope')
        assert result is None and record['analysis_snapshot_id'] is None and preview['candidates']
