from stage1_business_fixtures import business_environment
from stage1_external_business import external_business
from stage1_formal_acceptance import assert_formal_chain
from test_stage1_business_http import web_business
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

