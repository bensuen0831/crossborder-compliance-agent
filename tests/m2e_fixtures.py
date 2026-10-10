"""Governed two-jurisdiction fixture through existing publication owners only."""
from uuid import UUID,uuid4
from sqlalchemy import select
from phase1g_fixtures import publish as publish_knowledge
from phase1h_fixtures import contract
from test_phase1f_postgres import binding
from test_phase1h_postgres import payload,publish as publish_rule
from test_phase1i_postgres import publish_config

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import models as b,metadata_models as m,knowledge_models as k
from crossborder_compliance.infrastructure.persistence.rule_admin_repository import PostgresRuleAdminRepository
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import PostgresClassificationAdminRepository


def destination_configuration(f):
    destination=str(uuid4())
    with f['sf']() as s,s.begin():
        s.add(b.JurisdictionEntity(jurisdiction_id=destination,tenant_id=f['tenant'],code='DST-'+destination,name='Governed destination',status='ACTIVE'))
    source=f['repo'].get_source(f['source'])
    source_id=f['repo'].create_source({k:v for k,v in {
        **source,'code':uuid4().hex,'jurisdiction_refs':[destination]}.items()
        if k not in {'source_id','source_hash','record_version'}})['source_id']
    second=dict(f,juri=destination,source=source_id)
    version=publish_knowledge(second,[binding(second,dimensions={'product':[f['a']],'jurisdiction':[destination]})])
    # Same genuine Knowledge ingestion/publication/index foundation as existing
    # regressions; no external-specific retrieval or precomputed result.
    second['repo'].build_index(version['knowledge_version_id'])
    with f['sf']() as s,s.begin():
        node=s.scalar(select(k.KnowledgeStructureNodeEntity).where(
            k.KnowledgeStructureNodeEntity.tenant_id==f['tenant'],k.KnowledgeStructureNodeEntity.knowledge_version_id==version['knowledge_version_id'],k.KnowledgeStructureNodeEntity.node_type=='ARTICLE'))
        legal=s.get(b.RegulatoryStructureNodeEntity,node.regulatory_structure_node_id)
        basis=str(uuid4())
        s.add(b.LegalBasisItemEntity(legal_basis_id=basis,tenant_id=f['tenant'],jurisdiction_id=destination,
            regulatory_structure_node_id=legal.regulatory_structure_node_id,legal_basis_summary='Destination governed fixture authority',
            applicability_reason='Published rule',official_source=legal.official_source,citation_locator=node.canonical_locator))
        old=s.get(m.ClassificationSchemeVersionEntity,f['scheme_version'])
        scheme_id=old.scheme_id
        node_id=legal.regulatory_structure_node_id
    schemes=PostgresClassificationAdminRepository(f['sf'],f['ctx'])
    reviewer=RepositoryContext.user(UUID(f['tenant']),'independent-reviewer',set(f['ctx'].permission.scopes))
    draft=schemes.create_version(UUID(scheme_id),payload={'applicability':{'phase1h':{
        'jurisdiction_ids':[f['juri'],destination],'categories':[{'code':'CATEGORY'}],'levels':[]}}})
    publish_rule(schemes,draft,PostgresClassificationAdminRepository(f['sf'],reviewer))
    detail=schemes.get_detail(UUID(draft['version_id']))
    category=detail['applicability']['phase1h']['categories'][0]['category_id']
    con=contract(draft['version_id'],f['juri'],category,
        scope={'jurisdiction_ids':[f['juri'],destination]},evidence_required=['KNOWLEDGE_ORIGINAL'],legal_basis_ids=[f['basis'],basis])
    rules=PostgresRuleAdminRepository(f['sf'],f['ctx'])
    rule=rules.create_version(UUID(f['rule']['definition_id']),payload(con))
    publish_rule(rules,rule,PostgresRuleAdminRepository(f['sf'],reviewer))
    cfg=publish_config(f,'APPLICABILITY_CONFIG',dict(jurisdiction_id=destination,
        knowledge_version_id=version['knowledge_version_id'],regulatory_structure_node_ids=[node_id],legal_basis_ids=[basis],
        required_rule_ids=[f['rule']['definition_id']],reason_code='CONFIGURED_APPLICABILITY',requires_classification=False))
    publish_config(f,'COUNTRY_PROFILE',dict(jurisdiction_id=destination,capability_ids=[f['capability']['definition_id']],
        rule_pack_ids=[f['pack']['definition_id']],knowledge_collection_ids=[f['col']],applicability_config_ids=[cfg['definition_id']]))
    # Expand the existing generic owning policies via their ordinary review /
    # publication lifecycle. Old foundation snapshots retain their v1 pins.
    with f['sf']() as session:
        configs=[]
        kinds={'OBLIGATION_POLICY','COMPLIANCE_PATH_POLICY','RISK_POLICY','RECOMMENDATION_POLICY',
               'CROSS_BORDER_ASSESSMENT_POLICY','DOCUMENT_REQUIREMENT_POLICY'}
        for definition in session.scalars(select(m.MetadataDefinitionEntity).where(
            m.MetadataDefinitionEntity.tenant_id==f['tenant'],m.MetadataDefinitionEntity.kind.in_(kinds))):
            row=session.get(m.MetadataVersionEntity,definition.active_version_id)
            configs.append((definition.kind,definition.definition_id,row.payload_json))
    destination_obligation=str(uuid4())
    order=['OBLIGATION_POLICY','COMPLIANCE_PATH_POLICY','RISK_POLICY','RECOMMENDATION_POLICY',
           'CROSS_BORDER_ASSESSMENT_POLICY','DOCUMENT_REQUIREMENT_POLICY']
    for kind,identity,original in sorted(configs,key=lambda row:order.index(row[0])):
        import copy
        config_payload=copy.deepcopy(original)
        config_payload['jurisdiction_ids']=[f['juri'],destination]
        if kind=='OBLIGATION_POLICY':
            config_payload['entries'].append(dict(entry_id=destination_obligation,code='DESTINATION_REQUIREMENT',
                jurisdiction_id=destination,applicability_config_id=cfg['definition_id'],
                required_rule_ids=[f['rule']['definition_id']],legal_basis_ids=[basis]))
        if kind=='COMPLIANCE_PATH_POLICY':
            for template in config_payload['templates']:
                template['obligation_entry_ids'].append(destination_obligation)
        publish_config(f,kind,config_payload,definition_id=identity)
    return destination
