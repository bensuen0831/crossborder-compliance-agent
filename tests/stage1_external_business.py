"""Actual OAuth and SDK business journey over the existing external contract."""
import io
import sys
from pathlib import Path
from uuid import UUID, uuid4

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.integration_worker import IntegrationDeliveryWorker
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from stage1_business_fixtures import genuine_docx
from stage1_business_manifest import business_facts
from test_m2e_http import credential


def external_business(f, *, after_result=None):
    # The fixture governor creates a real credential through the control plane;
    # only the OAuth-issued principal is used for the business journey.
    f['app'].dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(UUID(f['tenant']),'fixture-integration-admin',{'integration:manage'})
    try:
        identity = credential(f['client'])
    finally:
        f['app'].dependency_overrides[get_repository_context] = lambda:f['user']
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sdk/python/src'))
    try:
        from crossborder_agent import AgentClient
    finally:
        sys.path.pop(0)
    sdk = AgentClient(str(f['client'].base_url),timeout=180)
    worker = IntegrationDeliveryWorker(f['app'])
    try:
        sdk.authenticate(identity['client']['client_id'],identity['credential'])
        draft = sdk.create_project({'name':'Stage1 independent API '+uuid4().hex,'facts':{'analysis_as_of_date':f['facts']['analysis_as_of_date']}},uuid4().hex)
        assert draft['status']=='DRAFT' and draft['analysis_snapshot_id'] is None
        project = draft['project_id'];f['provision_project_models'](project)
        flow = dict(input_key=uuid4().hex,data_item_canonical_name='Governed Data',source_jurisdiction_id=f['facts']['source_locations'][0],destination_jurisdiction_id=f['facts']['destination_locations'][0],direction='SOURCE_TO_DESTINATION',source_name='Business source',destination_name='Business destination')
        draft = sdk.update_intake(project,dict(expected_version=draft['version'],facts={**business_facts(f),'data_flows':[flow]}),uuid4().hex)
        uploaded = sdk.upload_document(project,io.BytesIO(genuine_docx(project,semantic_only=f['outcome']=='DIRECT')),'business.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',draft['version'],uuid4().hex)
        doc = uploaded['items'][0]['document_version_id'];version=uploaded['intake_version']
        sdk.parse_document(project,doc,version,uuid4().hex)
        preview = sdk.prepare_candidates(project,version,uuid4().hex)
        assert preview['candidates']
        assert sdk.candidate_preview(project)==preview
        decision = sdk.resolve_candidates(project,dict(expected_version=version,candidate_preparation_id=preview['candidate_preparation_id'],candidate_universe_digest=preview['candidate_universe_digest'],decisions=[dict(preparation_candidate_id=i['preparation_candidate_id'],action='ACCEPT') for i in preview['candidates']]),uuid4().hex)
        requests=len(f['provider_requests'])
        record=sdk.confirm(project,version,uuid4().hex,candidate_decision_set_id=decision['candidate_decision_set_id'])
        assert len(f['provider_requests'])==requests
        accepted=sdk.start_analysis(project,record['analysis_snapshot_id'],uuid4().hex)
        assert accepted['status']=='ACCEPTED'
        worker.start()
        status=sdk.wait_for_completion(record['workflow_run_id'],timeout=180,interval=1)
        assert status['status'] in {'COMPLETED','REVIEW_REQUIRED'},status
        result=sdk.get_result(record['workflow_run_id'])
        assert result['status']==status['status']
        events=list(sdk.events(record['workflow_run_id']))
        assert events and events[-1]['event_code']==('REVIEW_REQUIRED' if status['status']=='REVIEW_REQUIRED' else 'WORKFLOW_COMPLETED')
        if after_result:after_result(f,sdk,worker,result,record,preview)
        return result,record,preview
    finally:
        worker.stop();sdk.close()

