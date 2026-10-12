"""Actual prior-source rows must remain readable, immutable and read-only."""
from uuid import UUID
import pytest
from stage1_legacy_history import prior_source,produce_decisions
from test_phase1c_model_registry import _sf
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.domain.decision_contracts import result_digest
from crossborder_compliance.infrastructure.persistence.country_compliance_repository import PostgresCountryComplianceRepository
from crossborder_compliance.infrastructure.persistence.decision_models import MODELS
from crossborder_compliance.application.decision_services import DecisionRequest
from copy import deepcopy
from types import SimpleNamespace
pytestmark=pytest.mark.runtime_smoke

def test_prior_source_result_reads_without_rewriting_history_and_cannot_execute_again(tmp_path):
    old=produce_decisions(prior_source(tmp_path/'prior'))
    assert old['engine_version']=='FORMAL_DECISION_V2'
    sf=_sf();ctx=RepositoryContext.user(UUID(old['tenant']),old['actor'],set(old['scopes']))
    repo=PostgresCountryComplianceRepository(sf,ctx)
    with sf() as s:
        before={kind:s.get(MODELS[kind],ident).result_json for kind,ident in old['results'].items()}
        request=DecisionRequest.model_validate(s.get(MODELS['OBLIGATION'],old['results']['OBLIGATION']).request_json)
    for kind,ident in old['results'].items():
        first=repo.read_decision(kind,UUID(ident));second=repo.read_decision(kind,UUID(ident))
        assert first.engine_version==first.provenance.engine_version=='FORMAL_DECISION_V2'
        assert result_digest(first)==result_digest(second)
    with pytest.raises(ValueError,match='LEGACY_DECISION_SNAPSHOT_READ_ONLY'):
        repo.prepare_decision(request.model_copy(update={'idempotency_key':'different-new-key'}))
    with sf() as s:
        assert all(s.get(MODELS[kind],ident).result_json==before[kind] for kind,ident in old['results'].items())

@pytest.mark.parametrize('attack',['unknown','row_version','json_version','column_provenance','support','mixed_chain'])
def test_adversarial_persisted_version_support_and_mixed_chain_are_rejected(tmp_path,monkeypatch,attack):
    old=produce_decisions(prior_source(tmp_path/'prior'))
    sf=_sf();repo=PostgresCountryComplianceRepository(sf,RepositoryContext.user(UUID(old['tenant']),old['actor'],set(old['scopes'])))
    identity=old['results']['CANDIDATE_PATH'];get=repo.get
    def attacked(session,model,ident):
        row=get(session,model,ident)
        if model is MODELS['CANDIDATE_PATH'] and str(ident)==identity:
            fake=SimpleNamespace(**{column.name:deepcopy(getattr(row,column.name)) for column in model.__table__.columns})
            if attack=='unknown':fake.engine_version='UNTRUSTED_VERSION'
            if attack=='row_version':fake.engine_version='FORMAL_DECISION_V2_1'
            if attack=='json_version':fake.result_json['engine_version']='FORMAL_DECISION_V2_1'
            if attack=='column_provenance':fake.provenance_json['engine_version']='FORMAL_DECISION_V2_1'
            if attack=='support':fake.result_json['items'][0]['support']['applicability_result_ids']=[]
            if attack=='mixed_chain':
                fake.engine_version='FORMAL_DECISION_V2_1';fake.provenance_json['engine_version']='FORMAL_DECISION_V2_1'
                fake.result_json['engine_version']='FORMAL_DECISION_V2_1';fake.result_json['provenance']['engine_version']='FORMAL_DECISION_V2_1'
            return fake
        return row
    # Adversarial persisted-row read injection only; no algorithm monkeypatch,
    # database mutation, version inference or successful legacy execution.
    monkeypatch.setattr(repo,'get',attacked)
    with pytest.raises(ValueError):repo.read_decision('CANDIDATE_PATH',UUID(identity))
