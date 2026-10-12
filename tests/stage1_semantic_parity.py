"""Test-only identity-aware normalization; no legal/status/support field is dropped."""
import hashlib
import json
from sqlalchemy import select
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import document_models as d
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence import metadata_models as m

SECTIONS = ('classification','applicability','cross_border','obligation','candidate_path','risk',
            'recommendation','final_path','document_requirements','legal_basis')
VOLATILE = frozenset(('request_id','correlation_id','computation_timestamp','created_at','updated_at',
                      'input_digest','pins_digest','actor_ref','generated_by','record_version','claim_hash'))

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def normalize_formal(f, result):
    """Alias actual owned identities; shared jurisdiction/knowledge/rule versions stay exact."""
    aliases = {}
    def alias(ident, meaning):
        if ident is not None:
            key = str(ident)
            assert key not in aliases or aliases[key] == meaning, 'ambiguous semantic identity'
            aliases[key] = meaning
    project = result['project']['project_id'];snapshot = result['analysis_snapshot_id']
    alias(project, 'PROJECT');alias(snapshot, 'SNAPSHOT');alias(result['workflow_run_id'], 'WORKFLOW')
    alias(result['project']['project_version_id'], 'PROJECT_VERSION')
    alias(result['project']['context_resolution_run_id'], 'FORMAL_CONTEXT')
    # Independent project-scoped LLM policies are distinct resources with the
    # same governed payload; retain every policy constraint and version number.
    with f['sf']() as session:
        for envelope in (result.get(k) for k in SECTIONS):
            if not isinstance(envelope,dict):continue
            for pin in envelope.get('pins',[]):
                version=session.get(m.MetadataVersionEntity,pin['version_id'])
                if version is None:continue
                definition=session.get(m.MetadataDefinitionEntity,version.definition_id)
                if definition.kind=='MODEL_USAGE_POLICY' and version.payload_json.get('scope_type')=='PROJECT':
                    assert version.tenant_id==f['tenant'] and version.payload_json['project_id']==project
                    payload={**version.payload_json,'project_id':'PROJECT'}
                    meaning='PROJECT_MODEL_POLICY:'+canonical([payload,version.version_no])
                    alias(definition.definition_id,meaning);alias(version.version_id,meaning+':VERSION')
    for item in result['data_items']:alias(item['data_item_id'], 'DATA_ITEM:' + item['name'])
    for node in result['flow_nodes']:
        alias(node['flow_node_id'], 'FLOW_NODE:' + canonical({k:v for k,v in node.items() if k not in ('flow_node_id','source_trace_ids')}))
    for edge in result['flows']:
        alias(edge['flow_edge_id'], 'FLOW:' + canonical({k:aliases.get(v,v) if isinstance(v,str) else v for k,v in edge.items() if k not in ('flow_edge_id','data_item_ids','source_trace_ids')}))
    for document in result['documents']:
        for field in ('document_id','document_version_id','parse_run_id'):
            alias(document[field], field.upper()+':'+document['name'])
    for item in result['classification']:
        meaning = f"CLASS:{item['jurisdiction_id']}:{item['scheme_version_id']}:{aliases[item['data_item_id']]}"
        alias(item['classification_result_id'], meaning)
        with f['sf']() as session:
            for ident in item['rule_hit_ids']:
                row=session.get(b.RuleHitEntity, ident)
                assert row and row.tenant_id==f['tenant']
                alias(ident,'RULE_HIT:'+meaning+':'+row.rule_version_ref)
    for item in result['applicability']:
        alias(item['applicability_result_id'],f"APPLICABILITY:{item['jurisdiction_id']}:{item['regulation_version_ref']}")
    item_identity = {'obligation':('obligation_id','obligation_code'),
                     'candidate_path':('candidate_path_id','path_code'),
                     'risk':('risk_assessment_id','candidate_path_id'),
                     'recommendation':('recommendation_id','status'),
                     'final_path':('final_path_id','status'),
                     'cross_border':('cross_border_assessment_id','status'),
                     'document_requirements':('document_requirement_id','document_type_code')}
    for section, (identity, semantic) in item_identity.items():
        envelope=result[section]
        if envelope is None:continue
        alias(envelope['result_id'],'RESULT:'+section)
        for item in envelope['items']:
            meaning=str(aliases.get(item.get(semantic),item.get(semantic)))
            if section=='obligation':meaning+=':'+canonical(item['jurisdiction_ids'])
            alias(item[identity],section.upper()+':'+meaning)
        for pin in envelope['pins']:
            with f['sf']() as session:
                row=session.get(m.AnalysisSnapshotRegistryPinEntity,pin['pin_id'])
                assert row and row.tenant_id==f['tenant'] and row.analysis_snapshot_id==snapshot
                obj=aliases.get(row.object_id,row.object_id);version=aliases.get(row.version_id,row.version_id)
                alias(pin['pin_id'], 'PIN:'+canonical([row.pin_type,obj,version,row.version_no]))
    with f['sf']() as session:
        for fact in session.scalars(select(c.BusinessFactEntity).where(c.BusinessFactEntity.project_id==project,c.BusinessFactEntity.tenant_id==f['tenant'],c.BusinessFactEntity.version==result['project']['formal_context_version'])):
            alias(fact.fact_id,'FACT:'+canonical([fact.fact_type,fact.normalized_key,fact.normalized_value_json,fact.resolution_method,sorted(aliases.get(i,i) for i in fact.source_document_ids_json)]))
        for doc in result['documents']:
            details=session.scalars(select(d.SourceTraceDetailEntity).where(d.SourceTraceDetailEntity.document_id==doc['document_id'],d.SourceTraceDetailEntity.parse_run_id==doc['parse_run_id'])).all()
            for detail in details:
                trace=session.get(b.SourceTraceRefEntity,detail.source_trace_ref_id)
                assert trace and trace.tenant_id==f['tenant']
                locator=[trace.page_no,trace.section,trace.table_ref,trace.row_ref,trace.bbox_json,
                         detail.sheet_name,detail.slide_no,detail.section_path,detail.table_id,detail.row_index,detail.column_index]
                alias(trace.source_trace_ref_id,'SOURCE_TRACE:'+canonical([doc['name'],locator,detail.original_text_hash]))
        for pack in session.scalars(select(g.EvidencePackEntity).where(g.EvidencePackEntity.analysis_snapshot_id==snapshot,g.EvidencePackEntity.tenant_id==f['tenant'])):
            run=session.get(g.RetrievalRunEntity,pack.retrieval_run_id)
            items=session.scalars(select(g.EvidencePackItemEntity).where(g.EvidencePackItemEntity.evidence_pack_id==pack.evidence_pack_id)).all()
            meaning=canonical(sorted((i.knowledge_version_id,i.structure_node_id,i.citation_id) for i in items))
            subject=run.query_json.get('subject_type','PROJECT')+':'+str(aliases.get(run.query_json.get('subject_id'),run.query_json.get('subject_id')))
            alias(pack.evidence_pack_id,'EVIDENCE_PACK:'+subject+':'+meaning)
            alias(run.retrieval_run_id,'RETRIEVAL:'+subject+':'+meaning)
            for suff in session.scalars(select(g.KnowledgeSufficiencyResultEntity).where(g.KnowledgeSufficiencyResultEntity.evidence_pack_id==pack.evidence_pack_id)):
                alias(suff.sufficiency_result_id,'SUFFICIENCY:'+subject+':'+meaning)
            for item in items:
                alias(item.evidence_item_id,'EVIDENCE:'+canonical([item.knowledge_version_id,item.structure_node_id,item.citation_id]))
    alias(result['review_id'],'CANONICAL_REVIEW')
    # Result digest refs are verified by canonical result reads before normalization;
    # their differing project-dependent values are represented by their exact owner.
    digests={}
    for section in SECTIONS:
        envelope=result[section]
        if isinstance(envelope,dict):
            for ref in envelope.get('upstream_refs',[]):
                assert ref['result_id'] in aliases
                digests[ref['content_digest']]='VERIFIED_DIGEST:'+aliases[ref['result_id']]
    unordered={'classification','applicability','legal_basis','items','pins','origins','upstream_refs'}
    def walk(value,key=''):
        if isinstance(value,dict):
            return {k:walk(v,k) for k,v in value.items() if k not in VOLATILE}
        if isinstance(value,list):
            values=[walk(v,key) for v in value]
            if key in unordered or key.endswith(('_ids','_refs')):values.sort(key=canonical)
            return values
        if isinstance(value,str):return aliases.get(value,digests.get(value,value))
        return value
    output={key:walk(result[key],key) for key in SECTIONS}
    output.update(status=result['status'],reason_codes=sorted(result['reason_codes']),review_state=bool(result['review_id']),
                  subject_type=result['subject_type'],generation_available=result['generation_available'],
                  evidence=walk(result['retrieval']['evidence_pack']['items'],'items'))
    return output

def formal_difference(left,right,path=''):
    """Bounded non-sensitive path diagnostics, never raw documents/tokens."""
    if type(left) is not type(right):return [path+':type']
    if isinstance(left,dict):
        if left.keys()!=right.keys():return [path+':keys']
        return [p for key in left for p in formal_difference(left[key],right[key],path+'/'+key)]
    if isinstance(left,list):
        if len(left)!=len(right):return [path+':length']
        return [p for i,(a,b) in enumerate(zip(left,right)) for p in formal_difference(a,b,path+'/'+str(i))]
    return [] if left==right else [path]
