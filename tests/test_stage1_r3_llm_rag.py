from uuid import UUID,uuid4
import pytest
from sqlalchemy import select
from stage1_business_fixtures import business_environment
from stage1_formal_acceptance import assert_formal_chain
from test_stage1_business_http import web_business
from phase1g_fixtures import publish as publish_knowledge
from test_phase1f_postgres import binding
from test_phase1g_persistence_postgres import service
from crossborder_compliance.domain.retrieval import KnowledgeRetrievalQuery
from crossborder_compliance.infrastructure.intake_composition import project_context
from crossborder_compliance.infrastructure.llm_query_expansion import query_expansion_planner
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import PostgresRetrievalRepository
from crossborder_compliance.infrastructure.persistence import context_models as c

pytestmark=pytest.mark.runtime_smoke

def test_blank_project_query_gap_real_http_second_retrieval_cannot_broaden_scope(tmp_path):
    with business_environment(tmp_path,'DIRECT') as f:
        forbidden=publish_knowledge(f,[binding(f,dimensions={'product':[f['b']]})]);f['repo'].build_index(forbidden['knowledge_version_id'])
        measured={}
        def gap(f,record,preview):
            context=project_context(f['sf'],f['user'],UUID(record['project_id']))
            query=KnowledgeRetrievalQuery(project_id=record['project_id'],analysis_snapshot_id=record['analysis_snapshot_id'],policy_id=record['retrieval_policy_id'],query_text='unmatched_initial_business_evidence_terms',idempotency_key=uuid4().hex)
            repo=PostgresRetrievalRepository(f['sf'],context);plain=service({'sf':f['sf'],'ctx':context},repo).retrieve(query)
            assert plain['rag_context_pack']['knowledge_sufficiency']['status']=='INSUFFICIENT'
            assert not plain['rag_context_pack']['evidence_pack']['items']
            query=query.model_copy(update={'idempotency_key':uuid4().hex})
            planner=query_expansion_planner(f['sf'],context,query,secrets=f['app'].state.llm_secret_store_factory(context))
            expanded=service({'sf':f['sf'],'ctx':context},repo,query_expansion=planner).retrieve(query)
            rag=expanded['rag_context_pack'];assert rag['knowledge_sufficiency']['status']=='SUFFICIENT'
            assert rag['evidence_pack']['items'] and rag['evidence_pack']['manifest']['query_expansion']['authority']=='DERIVED_CANDIDATE'
            assert all(i['knowledge_version_id']!=forbidden['knowledge_version_id'] and i['scope_validation_status']=='VALIDATED' and not i['legal_decision'] for i in rag['evidence_pack']['items'])
            assert any(r.get('query_expansion') for r in f['provider_requests'])
            repeated=service({'sf':f['sf'],'ctx':context},repo,query_expansion=planner).retrieve(query)
            assert repeated['retrieval_run_id']==expanded['retrieval_run_id']
            measured.update(first='INSUFFICIENT',second='SUFFICIENT',scope_preserved=True)
        result,record,preview=web_business(f,after_confirm=gap);assert_formal_chain(f,result,record,preview)
        assert measured=={'first':'INSUFFICIENT','second':'SUFFICIENT','scope_preserved':True}

def test_multi_model_disagreement_is_candidate_only_and_user_selects_input(tmp_path):
    with business_environment(tmp_path,'DIRECT',candidate_values={'A1':'service-processing','A2':'different-purpose'}) as f:
        def action(candidate):
            return 'REJECT' if candidate['candidate_type']=='BUSINESS_FACT' and candidate['proposed_payload'].get('normalized_value_json')=='different-purpose' else 'ACCEPT'
        preference=dict(usage_mode='ENHANCED',selection_mode='MULTI_MODEL',selected_model_ids=f['model_ids'])
        result,record,preview=web_business(f,input_overrides={'ai_model_preference':preference},candidate_action=action)
        facts=[i for i in preview['candidates'] if i['candidate_type']=='BUSINESS_FACT' and i['candidate_origin']=='LLM_STRUCTURED_OUTPUT']
        assert {i['proposed_payload']['normalized_value_json'] for i in facts}=={'service-processing','different-purpose'}
        assert len({i['candidate_id'] for i in facts})==2
        assert {r['model'] for r in f['provider_requests']}=={'A1','A2'}
        with f['sf']() as s:
            values=s.scalars(select(c.BusinessFactEntity).where(c.BusinessFactEntity.project_id==record['project_id'],c.BusinessFactEntity.fact_type=='PROCESSING_PURPOSE')).all()
            assert len(values)==1 and values[0].normalized_value_json=='service-processing' and values[0].resolution_method=='USER_CONFIRMED_DOCUMENT_CANDIDATE'
        assert_formal_chain(f,result,record,preview)
