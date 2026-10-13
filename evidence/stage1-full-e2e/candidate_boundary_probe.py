"""D0 diagnostic only: unchanged product owners, genuine PG/DOCX/local HTTP.

This is not the Stage1 acceptance suite. No transport credential or raw
provider request is written into the output.
"""
import io
import json
import subprocess
from datetime import date
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from docx import Document
from sqlalchemy import func, select

from phase1kb_http_servers import local_provider
from test_m2a_intake import setup
from test_m2e_http import http_server
from test_m2e_vertical_postgres import server
from test_phase1c_model_registry import _ctx
from test_phase1k_a_configuration_postgres import publish as publish_metadata
from test_phase1kb_control_postgres import configured_model, provider_request, publish
from test_phase1l_b_postgres import fixture, foundation_i, foundation_j

from crossborder_compliance.application.model_control_services import ModelControlService
from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.domain.llm_invocation import InvocationPurpose
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.intake_composition import prepare_snapshot
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.llm_gateway_http import check_endpoint
from crossborder_compliance.infrastructure.llm_provider_inspection import ProviderInspection
from crossborder_compliance.infrastructure.llm_secrets import EncryptedFileSecretStore
from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import PostgresGovernedArtifactAdminRepository
from crossborder_compliance.infrastructure.persistence.metadata_repositories import PostgresAdminMetadataRepository
from crossborder_compliance.infrastructure.persistence.model_control import PostgresModelControlRepository
from crossborder_compliance.interfaces.api.dependencies import get_repository_context

ROOT = Path('/workspace/crossborder-compliance-agent')
OUT = Path('/workspace/stage1-e2e-control')

def main():
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert sha == 'df3a10923734495d728981f4f319b66afadf8c71'
    f = foundation_i.__wrapped__(fixture.__wrapped__(), SimpleNamespace(param={'no_data': True}))
    f = foundation_j.__wrapped__(f, SimpleNamespace(param={}))
    app, facts = server(f, OUT / uuid4().hex)
    _, _, base_context, _ = setup(f)
    tenant = UUID(f['tenant'])
    admin_context = _ctx(tenant)
    metadata = PostgresAdminMetadataRepository(f['sf'], admin_context)
    note = metadata.create_definition(kind='BUSINESS_FACT_TYPE', code='DOCUMENT_NOTE_' + uuid4().hex, display_name='Document-derived note')
    publish_metadata(metadata, metadata.create_version(definition_id=UUID(note['definition_id']), payload={}), True)
    prompts = PostgresGovernedArtifactAdminRepository(f['sf'], admin_context, 'prompts')
    prompt = publish_metadata(prompts, prompts.create_draft(code=uuid4().hex, display_name='Source-addressed document candidates', payload={'template_text': 'Return candidates with real source locators; never legal decisions.', 'capability_requirement': ['STRUCTURED_OUTPUT']}))
    prompts.bind_llm_invocation(UUID(prompt['version_id']), InvocationPurpose.DOCUMENT_CANDIDATE_EXTRACTION)
    inv = metadata.create_definition(kind='LLM_INVOCATION_POLICY', code=uuid4().hex, display_name='Diagnostic extraction policy')
    publish_metadata(metadata, metadata.create_version(definition_id=UUID(inv['definition_id']), payload={'allowed_triggers': {'STANDARD': ['DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED']}, 'max_models': 3, 'candidate_fact_type_ids': [note['definition_id']], 'candidate_min_confidence': .95}), True)
    requests = []
    def candidate(payload):
        if not payload['messages'][-1]['content'].startswith('{'):
            return {'ok': True}
        value = json.loads(payload['messages'][-1]['content'])
        if 'source_nodes' not in value:
            return {'ok': True}
        node = next(n for n in value['source_nodes'] if 'PROVENANCE_MARKER' in n['text'])
        requests.append({'source_node_id': node['source_node_id'], 'observed': True})
        return {'facts': [{'source_node_id': node['source_node_id'], 'fact_type': note['code'], 'value': 'ambiguous document note', 'confidence': 1}], 'items': [{'source_node_id': node['source_node_id'], 'name': 'Generic Field', 'description': 'document item', 'confidence': 1}], 'nodes': [], 'edges': []}
    with local_provider(('A1',), structured_response=candidate) as (url, calls):
        model_repo = PostgresModelControlRepository(f['sf'], admin_context)
        secret_store = EncryptedFileSecretStore(OUT / 'probe-private-secrets', Fernet.generate_key(), tenant)
        service = ModelControlService(model_repo, admin_context, secret_store, check_endpoint)
        provider = publish(f['sf'], tenant, 'PROVIDER', service.save_provider(provider_request(credential='ci-local-credential').model_copy(update={'base_url': url})))
        model = publish(f['sf'], tenant, 'MODEL', configured_model(f['sf'], tenant, model_repo, provider, 'A1'))
        assert ProviderInspection(model_repo, secret_store).model_test(UUID(model['deployment_id']), 'chat')['status'] == 'HEALTHY'
        user = RepositoryContext.user(tenant, 'author', set(base_context.permission.scopes) | {'llm:invoke', 'knowledge:retrieve', 'document:read', 'document:upload', 'document:parse', 'document:unlink', f"prompt:{prompt['definition_id']}:use"})
        assert not user.permission.system
        app.dependency_overrides[get_repository_context] = lambda: user
        app.state.intake_snapshot_preparer = partial(prepare_snapshot, llm_dependencies={'storage': app.state.document_object_storage, 'secrets': secret_store})
        with http_server(app) as c:
            c.timeout = 180
            created = c.post('/api/v1/projects', json={'name': 'D0 genuinely blank project ' + uuid4().hex, 'idempotency_key': uuid4().hex, 'facts': {'analysis_as_of_date': date.today().isoformat()}})
            assert created.status_code == 201, created.text
            blank = created.json()
            project = blank['project_id']
            assert blank['status'] == 'DRAFT' and blank['analysis_snapshot_id'] is None
            def count(model, project_field):
                with f['sf']() as s:
                    return s.scalar(select(func.count()).select_from(model).where(project_field == project))
            assert count(e.BusinessFactEntity, e.BusinessFactEntity.project_id) == 0
            for scope in ('TENANT', 'PROJECT'):
                definition = metadata.create_definition(kind='MODEL_USAGE_POLICY', code=uuid4().hex, display_name=scope)
                publish_metadata(metadata, metadata.create_version(definition_id=UUID(definition['definition_id']), payload={'scope_type': scope, 'project_id': project if scope == 'PROJECT' else None, 'default_mode': 'INTERNAL_MODEL_ONLY', 'allowed_operations': ['structured_output'], 'allowed_model_ids': [model['model_id']], 'allowed_provider_ids': [provider['provider_id']], 'allowed_trust_levels': ['APPROVED'], 'allowed_data_boundaries': ['TENANT']}), True)
            path = f'/api/v1/projects/{project}/intake'
            saved = c.put(path, json={'expected_version': 1, 'idempotency_key': uuid4().hex, 'facts': facts})
            assert saved.status_code == 200, saved.text
            doc = Document()
            doc.add_paragraph('An unstructured ambiguous document note carrying PROVENANCE_MARKER ' + project)
            doc.core_properties.identifier = project
            buf = io.BytesIO()
            doc.save(buf)
            binary = buf.getvalue()
            upload = c.post(path + '/documents', data={'expected_version': saved.json()['version'], 'idempotency_key': uuid4().hex}, files={'file': ('business-input.docx', binary, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
            assert upload.status_code == 201, upload.text
            attached = upload.json()
            version_id = attached['items'][0]['document_version_id']
            calls.clear()
            parsed = c.post(path + f'/documents/{version_id}/parse', json={'expected_version': attached['intake_version'], 'idempotency_key': uuid4().hex})
            assert parsed.status_code == 200, parsed.text
            native = parsed.json()['items'][0]
            assert native['quality_status'] == 'PASS'
            assert not requests
            try:
                PostgresLLMConfiguration(f['sf'], RepositoryContext.user(tenant, 'author', set(user.permission.scopes) | {f'project:{project}:read'})).authorize(SimpleNamespace(project_id=UUID(project), analysis_snapshot_id=uuid4()))
            except GatewayDenied as exc:
                draft_denial = str(exc)
            else:
                raise AssertionError('unpinned draft unexpectedly authorized')
            confirm_body = {'expected_version': attached['intake_version']}
            confirmed = c.post(path + '/confirm', json=confirm_body)
            assert confirmed.status_code == 200, confirmed.text
            value = confirmed.json()
            with f['sf']() as s:
                formal = s.scalars(select(e.BusinessFactEntity).where(e.BusinessFactEntity.project_id == project, e.BusinessFactEntity.fact_type == note['code'])).all()
                assert len(formal) == 1
                pin = s.scalar(select(d.AnalysisSnapshotParseRunPinEntity).where(d.AnalysisSnapshotParseRunPinEntity.analysis_snapshot_id == value['analysis_snapshot_id']))
                candidate = s.scalar(select(d.BusinessFactCandidateEntity).where(d.BusinessFactCandidateEntity.parse_run_id == pin.parse_run_id, d.BusinessFactCandidateEntity.fact_type == note['code']))
                assert candidate and candidate.extraction_method == 'LLM_STRUCTURED_OUTPUT'
                assert formal[0].validation_status == 'VALIDATED'
                resolution = s.scalar(select(e.CandidateResolutionEntity).where(e.CandidateResolutionEntity.candidate_id == candidate.fact_id, e.CandidateResolutionEntity.formal_object_id == formal[0].fact_id))
                assert resolution and resolution.action == 'ACCEPTED'
                trace_ids = list(resolution.source_trace_ids_json)
                assert trace_ids and resolution.resolved_by_type == 'POLICY'
                result = {'source_sha': sha, 'purpose': 'D0 unchanged-source counterexample, not full acceptance', 'real_postgresql': True, 'real_http': True, 'real_docx': True, 'real_local_http_llm': True, 'system_permission': False, 'project_id': project, 'blank_project_formal_fact_count': 0, 'blank_snapshot_id': None, 'distinct_jurisdictions': facts['source_locations'] != facts['destination_locations'], 'draft_parse_quality': native['quality_status'], 'draft_parse_counts': native['counts'], 'semantic_requests_before_confirmation': 0, 'draft_gateway_denial': draft_denial, 'confirmation_request_fields': list(confirm_body), 'confirmed_snapshot_id': value['analysis_snapshot_id'], 'workflow_run_id': value['workflow_run_id'], 'document_version_id': version_id, 'native_parse_run_id': native['parse_run_id'], 'semantic_parse_run_id': pin.parse_run_id, 'semantic_http_invocations': len(requests), 'candidate_id': candidate.fact_id, 'formal_fact_id': formal[0].fact_id, 'formal_fact_status': formal[0].validation_status, 'formal_fact_source_trace_ids': trace_ids, 'candidate_preview_user_action': None, 'per_candidate_user_confirmation': None, 'formal_flow_nodes': count(b.DataFlowNodeEntity, b.DataFlowNodeEntity.project_id), 'formal_flow_edges': count(b.DataFlowEdgeEntity, b.DataFlowEdgeEntity.project_id), 'paid_internet_llm': 'NOT EXECUTED', 'stage2_started': False}
            assert len(requests) == 1
            (OUT / 'candidate_boundary_probe.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
