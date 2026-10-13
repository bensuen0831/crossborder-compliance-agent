from uuid import UUID,uuid4
from dataclasses import replace
import pytest
from stage1_business_fixtures import business_environment
from test_stage1_business_http import web_business
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.classification import router as classification_router
from crossborder_compliance.interfaces.api.routes.country_compliance import router as applicability_router

pytestmark=pytest.mark.runtime_smoke

def test_owned_project_preview_reads_revalidate_creator_tenant_and_stage_permissions(tmp_path):
    with business_environment(tmp_path,'DIRECT') as f:
        f['app'].include_router(classification_router);f['app'].include_router(applicability_router)
        result,record,_=web_business(f)
        urls=[('/api/v1/classifications/'+result['classification'][0]['classification_result_id'],'classification:read'),('/api/v1/regulation-applicability/'+result['applicability'][0]['applicability_result_id'],'applicability:read')]
        assert not any(s==f"project:{record['project_id']}:classify" for s in f['user'].permission.scopes)
        for url,_ in urls:assert f['client'].get(url).status_code==200
        for attack in ('wrong_actor','wrong_tenant','missing_stage_permission','missing_project_read'):
            for url,permission in urls:
                actor='unauthorized-user' if attack=='wrong_actor' else f['user'].permission.actor_id
                tenant=uuid4() if attack=='wrong_tenant' else UUID(f['tenant'])
                scopes=set(f['user'].permission.scopes)
                if attack=='missing_stage_permission':scopes.remove(permission)
                if attack=='missing_project_read':scopes.remove('project:read')
                caller=RepositoryContext.user(tenant,actor,scopes)
                f['app'].dependency_overrides[get_repository_context]=lambda:caller
                assert f['client'].get(url).status_code in (403,404)
        f['app'].dependency_overrides[get_repository_context]=lambda:f['user']
        for url,_ in urls:assert f['client'].get(url).status_code==200
