"""Additive acceptance/owner guards; frozen legal owners remain byte-identical."""
import ast,json,subprocess
from pathlib import Path
BASE='292fc6e9e1bc58deb1ec20920c1acf43e3e9109e'
def check(root):
    root=Path(root);read=lambda p:(root/p).read_text()
    fixture=read('tests/stage1_business_fixtures.py');journey=read('tests/test_stage1_business_http.py')
    browser=read('frontend/e2e/stage1-business.spec.ts');parity=read('tests/stage1_semantic_parity.py')
    rag=read('tests/test_stage1_r3_llm_rag.py');temporal=read('tests/test_stage1_r3_temporal_business.py')
    assertion=read('tests/stage1_formal_acceptance.py');uat=read('frontend/scripts/stage1/uat.py')
    candidate=read('src/crossborder_compliance/infrastructure/persistence/candidate_governance.py')
    product=list((root/'src').rglob('*.py'))
    cases=[json.loads(p.read_text()) for p in sorted((root/'tests/e2e/stage1/business_cases').glob('TC-*.json'))]
    frozen=['src/crossborder_compliance/domain/decision_engine.py','src/crossborder_compliance/application/decision_services.py','src/crossborder_compliance/infrastructure/persistence/decision_repository.py']
    same=lambda p:(root/p).read_bytes()==subprocess.check_output(['git','show',BASE+':'+p],cwd=root)
    return {
      'stage1_e2e_uses_canonical_workflow':"/workflow" in journey and 'WorkflowRuntime(' not in fixture+uat and 'external_router' in uat,
      'stage1_e2e_has_real_crossborder_dataflow':all(x in assertion for x in ("flow_node_id","flow_edge_id","data_item_ids","source_node_id","target_node_id")) and "data_flows" in journey,
      'stage1_e2e_document_participates_in_formal_context':all(x in assertion for x in ('BusinessFactResolutionEntity','SourceTraceDetailEntity','document_version_id','parse_run_id','source_fact_refs')),
      'stage1_candidate_is_not_formal_input':'/candidate-decisions' in journey and journey.index('/candidate-decisions')<journey.index('/intake/confirm') and 'USER_CONFIRMED_DOCUMENT_CANDIDATE' in read('src/crossborder_compliance/application/context_services.py'),
      'stage1_llm_is_not_formal_legal_authority':all(same(p) for p in frozen) and 'legal_decision' in assertion,
      'stage1_query_expansion_terms_are_not_evidence':'DERIVED_CANDIDATE' in rag and "not i['legal_decision']" in rag,
      'stage1_rag_scope_cannot_expand_from_llm':"forbidden['knowledge_version_id']" in rag and "scope_validation_status" in rag,
      'stage1_classification_is_jurisdiction_scoped':"len(classes) == 2" in assertion and 'scheme_version_id' in assertion,
      'stage1_applicability_same_jurisdiction':'same = next' in assertion and "app['classification_result_ids']" in assertion,
      'stage1_crossborder_status_not_final_path_status':"cross['status'] != result['final_path']['items'][0]['status']" in assertion,
      'stage1_risk_depends_on_candidate_path':"by_path[item['candidate_path_id']]['support']" in assertion,
      'stage1_recommendation_depends_on_risk':"set(i['risk_assessment_ids']) <= risks" in assertion,
      'stage1_final_path_depends_on_recommendation':'PARENTS[kind]' in assertion and 'final_path' in assertion,
      'stage1_required_document_does_not_generate':"result['generation_available'] is False" in assertion and all(not c['stage2_started'] for c in cases),
      'stage1_web_api_share_formal_authority':"normalize_formal(f,web)" in read('tests/test_stage1_channel_parity.py') and 'assert_formal_chain(f,api' in read('tests/test_stage1_channel_parity.py'),
      'stage1_locale_does_not_change_formal_semantics':all(x in browser for x in ("zh-CN","zh-HK","en-US","toEqual(result)","errors).toEqual([])")),
      'stage1_historical_snapshot_does_not_resolve_latest':all(same(p) for p in frozen) and 'snapshot_digest(f,snapshot)==before' in temporal,
      'stage1_successor_does_not_mutate_predecessor':"reread==old" in temporal and "prepared['candidate_preparation_id']!=preview['candidate_preparation_id']" in temporal,
      'stage1_case_id_not_used_by_product_logic':not any(any(isinstance(n,ast.Name) and n.id=='case_id' or isinstance(n,ast.Constant) and n.value=='case_id' for n in ast.walk(ast.parse(p.read_text()))) or 'TC-01' in p.read_text() or 'DIRECT_TEST' in p.read_text() for p in product),
      'stage1_synthetic_acceptance_not_real_law':len(cases)==4 and all(c['fixture_kind']=='SYNTHETIC_GOVERNED_TEST_DATA' for c in cases) and 'SYNTHETIC_GOVERNED_CONDITION' in fixture,
      'stage1_frozen_migrations_no_new_schema':frozen_migrations_or_approved_kb_addition(root, same),
      'stage1_browser_zero_retry_contract': 'retries: 0' in read('frontend/playwright.config.ts') and 'retries:test.info().retry' in browser,
    }


def frozen_migrations_or_approved_kb_addition(root, same):
    migrations = list((root / 'alembic/versions').glob('*.py'))
    historical = [p for p in migrations if p.name[:4].isdigit() and int(p.name[:4]) <= 20]
    if len(historical) != 20 or not all(same(str(p.relative_to(root))) for p in historical):
        return False
    additional = set(migrations) - set(historical)
    if not additional:
        return True
    # Stage1's schema remains frozen. KB01 is separately authorized, additive,
    # and every additional migration must match its committed owner proof.
    from scripts.kb01_ownership import overlay
    valid, owned, _ = overlay(root)
    return valid and all(str(path.relative_to(root)) in owned for path in additional)
