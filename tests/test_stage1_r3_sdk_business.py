import base64,json,subprocess,sys,os
from pathlib import Path
from uuid import UUID,uuid4
import pytest
from stage1_business_fixtures import business_environment,genuine_docx
from stage1_business_manifest import business_facts
from stage1_formal_acceptance import assert_formal_chain
from test_m2e_http import credential
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.infrastructure.integration_worker import IntegrationDeliveryWorker

pytestmark=pytest.mark.runtime_smoke
ROOT=Path(__file__).resolve().parents[1]

def test_typescript_sdk_real_oauth_docx_candidates_async_conditional_business(tmp_path):
    with business_environment(tmp_path,'CONDITIONAL') as f:
        f['app'].dependency_overrides[get_repository_context]=lambda:RepositoryContext.user(UUID(f['tenant']),'fixture-integration-admin',{'integration:manage'})
        try:identity=credential(f['client'])
        finally:f['app'].dependency_overrides[get_repository_context]=lambda:f['user']
        sys.path.insert(0,str(ROOT/'sdk/python/src'))
        try:from crossborder_agent import AgentClient
        finally:sys.path.pop(0)
        python_sdk=AgentClient(str(f['client'].base_url),timeout=180)
        try:
            python_sdk.authenticate(identity['client']['client_id'],identity['credential'])
            draft=python_sdk.create_project({'name':'Synthetic SDK business','facts':{'analysis_as_of_date':f['facts']['analysis_as_of_date']}},uuid4().hex)
        finally:python_sdk.close()
        f['provision_project_models'](draft['project_id'])
        flow=dict(input_key=uuid4().hex,data_item_canonical_name='Governed Data',source_jurisdiction_id=f['facts']['source_locations'][0],destination_jurisdiction_id=f['facts']['destination_locations'][0],direction='SOURCE_TO_DESTINATION',source_name='Business source',destination_name='Business destination')
        payload=dict(url=str(f['client'].base_url),client_id=identity['client']['client_id'],credential=identity['credential'],project_id=draft['project_id'],facts={**business_facts(f),'data_flows':[flow]},document_base64=base64.b64encode(genuine_docx(draft['project_id'])).decode(),document_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',expected=f['expected'])
        subprocess.run([os.getenv('STAGE1_TYPESCRIPT_TSC',str(ROOT/'frontend/node_modules/.bin/tsc')),'-p','sdk/typescript/tsconfig.json'],cwd=ROOT,check=True,capture_output=True)
        worker=IntegrationDeliveryWorker(f['app']);worker.start()
        try:
            result=subprocess.run(['node','tests/e2e/stage1/typescript-business.mjs'],cwd=ROOT,input=json.dumps(payload),text=True,capture_output=True,timeout=240)
        finally:worker.stop()
        assert result.returncode==0,'TypeScript SDK business failed; private process output withheld'
        measured=json.loads(result.stdout.splitlines()[-1]);assert_formal_chain(f,measured['result'],measured['record'],measured['preview'])
        assert measured['terminal_event']=='WORKFLOW_COMPLETED' and not measured['credentials_archived']
