"""Test-only semantic and provenance checks. No producer or legal authority."""
from sqlalchemy import select

from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence.decision_models import MODELS, PARENTS

def exact_support_union(actual,sources):
    from crossborder_compliance.domain.decision_contracts import LegalSupport
    sources=tuple(sources)
    for field in LegalSupport.model_fields:
        expected=sorted({ref for support in sources for ref in support[field]})
        assert actual[field]==expected,field


def assert_formal_chain(f, result, record, preview):
    project, snapshot = record['project_id'], record['analysis_snapshot_id']
    assert result['analysis_snapshot_id'] == snapshot
    assert result['generation_available'] is False
    assert result['mode'] == 'DATA_AWARE'
    assert len(result['data_items']) == 1 and len(result['flows']) == 1
    edge = result['flows'][0]
    nodes = {n['flow_node_id']: n for n in result['flow_nodes']}
    assert nodes[edge['source_node_id']]['jurisdiction_id'] != nodes[edge['target_node_id']]['jurisdiction_id']
    assert edge['data_item_ids'] == [result['data_items'][0]['data_item_id']]
    classes = result['classification']
    assert len(classes) == 2
    assert len({i['data_item_id'] for i in classes}) == 1
    assert len({i['scheme_version_id'] for i in classes}) == 1
    assert {i['jurisdiction_id'] for i in classes} == set(f['facts']['source_locations'] + f['facts']['destination_locations'])
    assert all(i['analysis_snapshot_id'] == snapshot and i['project_id'] == project for i in classes)
    for app in result['applicability']:
        same = next(i for i in classes if i['jurisdiction_id'] == app['jurisdiction_id'])
        assert app['classification_result_ids'] == [same['classification_result_id']]
        assert set(app['rule_hit_ids']) == set(same['rule_hit_ids'])
        assert app['evidence_ids'] and app['legal_basis_ids']
    assert len(result['applicability']) == 2
    cross = result['cross_border']['items'][0]
    assert cross['status'] == f['expected']
    assert cross['source_jurisdiction_ids'] == f['facts']['source_locations']
    assert cross['destination_jurisdiction_ids'] == f['facts']['destination_locations']
    assert cross['data_flow_ids'] == [edge['flow_edge_id']]
    assert cross['evidence_ids'] and cross['legal_basis_ids']
    evidence = result['retrieval']['evidence_pack']['items']
    assert evidence and result['legal_basis']
    assert all(i['knowledge_version_id'] and i['source_id'] and i['citation_id'] and i['original_text'] for i in evidence)
    assert all(i['legal_decision'] is False and i['scope_validation_status'] == 'VALIDATED' for i in evidence)
    assert all(i['official_source'] and i['citation_locator'] for i in result['legal_basis'])
    if f['outcome'] == 'REVIEW':
        assert result['status'] == 'REVIEW_REQUIRED' and result['review_id']
        assert result['final_path'] is None and result['document_requirements'] is None
    else:
        assert result['status'] == 'COMPLETED'
        for key in ('obligation','candidate_path','risk','recommendation','final_path','document_requirements'):
            env = result[key]
            assert env and env['items'], key
            assert env['project_id'] == project and env['analysis_snapshot_id'] == snapshot
            assert env['tenant_id'] == f['tenant']
            assert env['engine_version']==env['provenance']['engine_version']=='FORMAL_DECISION_V2_1' if key!='document_requirements' else env['engine_version']=='FORMAL_RESULT_AUTHORITY_V2'
            assert all(i.get('support',i).get('evidence_ids') for i in env['items'] if i.get('requirement_level')!='NOT_APPLICABLE')
        paths = {i['candidate_path_id'] for i in result['candidate_path']['items']}
        by_obligation={i['obligation_id']:i for i in result['obligation']['items']}
        by_path={i['candidate_path_id']:i for i in result['candidate_path']['items']}
        for item in result['candidate_path']['items']:
            exact_support_union(item['support'],(by_obligation[ref]['support'] for ref in item['obligation_ids']))
        for item in result['risk']['items']:
            exact_support_union(item['support'],(by_path[item['candidate_path_id']]['support'],))
        for item in result['recommendation']['items']:
            exact_support_union(item['support'],(p['support'] for p in result['candidate_path']['items']))
        for item in result['final_path']['items']:
            exact_support_union(item['support'],(o['support'] for o in result['obligation']['items']))
        risks = {i['risk_assessment_id'] for i in result['risk']['items']}
        assert all(i['candidate_path_id'] in paths for i in result['risk']['items'])
        assert all(set(i['risk_assessment_ids']) <= risks for i in result['recommendation']['items'])
        for item in result['final_path']['items']:
            if item['selected_candidate_path_id'] is not None:
                assert item['selected_candidate_path_id'] in paths
            else:
                assert set(item['alternative_candidate_ids']) <= paths
                assert item['unmet_requirement_ids'] or item['unresolved_codes']
        assert {i['requirement_level'] for i in result['document_requirements']['items']} == {'REQUIRED','CONDITIONAL','RECOMMENDED','NOT_APPLICABLE'}
        assert cross['status'] != result['final_path']['items'][0]['status']
        with f['sf']() as s:
            for kind, model in MODELS.items():
                row = s.get(model, result[kind.lower()]['result_id'])
                assert row and row.project_id == project and row.analysis_snapshot_id == snapshot
                assert row.engine_version==row.result_json['engine_version']==row.provenance_json['engine_version']=='FORMAL_DECISION_V2_1'
                for parent in PARENTS[kind]:
                    assert getattr(row,parent.lower()+'_result_id') == result[parent.lower()]['result_id']
    if f['outcome'] == 'DIRECT':
        assert f['provider_requests'] and any(i['candidate_origin']=='LLM_STRUCTURED_OUTPUT' for i in preview['candidates'])
        with f['sf']() as s:
            fact = s.scalar(select(c.BusinessFactEntity).where(c.BusinessFactEntity.project_id == project,c.BusinessFactEntity.fact_type == 'PROCESSING_PURPOSE'))
            assert fact and fact.normalized_value_json == 'service-processing'
            assert fact.resolution_method != 'POLICY'
            resolution = s.scalar(select(c.BusinessFactResolutionEntity).where(c.BusinessFactResolutionEntity.business_fact_id == fact.fact_id))
            assert resolution and resolution.source_trace_ids_json
            trace = s.get(b.SourceTraceRefEntity,resolution.source_trace_ids_json[0])
            assert trace.document_version_id == result['documents'][0]['document_version_id']
            detail=s.get(d.SourceTraceDetailEntity,trace.source_trace_ref_id)
            assert detail.parse_run_id == result['documents'][0]['parse_run_id']
            assert any(fact.fact_id in i['source_fact_refs'] for i in classes)

