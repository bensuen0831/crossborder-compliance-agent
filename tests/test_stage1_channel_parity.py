from stage1_business_fixtures import business_environment
from stage1_external_business import external_business
from stage1_formal_acceptance import assert_formal_chain
from test_stage1_business_http import web_business
from stage1_semantic_parity import normalize_formal,formal_difference
import pytest

pytestmark=pytest.mark.runtime_smoke

@pytest.mark.parametrize('outcome',['DIRECT','CONDITIONAL','LOCALIZATION','REVIEW'])
def test_independent_web_external_oauth_blank_project_businesses(tmp_path,outcome):
    with business_environment(tmp_path,outcome) as f:
        web,w,wp=web_business(f)
        api,a,ap=external_business(f)
        assert w['project_id']!=a['project_id'] and w['analysis_snapshot_id']!=a['analysis_snapshot_id']
        assert_formal_chain(f,web,w,wp)
        assert_formal_chain(f,api,a,ap)
        normalized_web=normalize_formal(f,web);normalized_api=normalize_formal(f,api)
        import json,os
        from pathlib import Path
        output=Path(os.getenv('EVIDENCE_DIR','artifacts/stage1-r3'))/'parity';output.mkdir(parents=True,exist_ok=True)
        differences=formal_difference(normalized_web,normalized_api)
        (output/(outcome.lower()+'.json')).write_text(json.dumps(dict(outcome=outcome,passed=not differences,differences=differences,web=normalized_web,api=normalized_api),indent=2)+'\n')
        assert normalized_web==normalized_api,formal_difference(normalized_web,normalized_api)[:30]

