import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Descriptions, Space, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import type { AuthorizedContext } from '../../api/contracts';
import { SourceCitationDrawer, EvidenceTable } from '../../components/Evidence';
import { SufficiencyPanel, FallbackPanel } from '../../components/Sufficiency';
import { ErrorState, LoadingState } from '../../components/States';
import { formatDate, formatNumber } from '../knowledge/formatting';
import { m1Api } from '../intake/api';
import type { WorkflowView } from '../intake/contracts';

const statusKeys: Record<string, string> = {
  CLASSIFIED: 'ui.m1.classified', REVIEW_REQUIRED: 'ui.m1.reviewRequired', APPLICABLE: 'ui.m1.applicable',
  NOT_APPLICABLE: 'ui.m1.notApplicable', CONDITIONALLY_APPLICABLE: 'ui.m1.conditional',
  INSUFFICIENT_EVIDENCE: 'ui.m1.insufficient', CONFLICTED: 'ui.m1.conflicted',
};
export function AnalysisPanel({ context, identity, workflow }: { context: AuthorizedContext; identity: string; workflow?: WorkflowView }) {
  const { t } = useTranslation();
  const [refs, setRefs] = useState({ classification: '', applicability: '', retrieval: '' });
  const [submitted, setSubmitted] = useState<typeof refs>();
  const [selected, setSelected] = useState<string>();
  const canonicalRefs = workflow?.result_refs;
  const complete = canonicalRefs?.classification?.[0] && canonicalRefs?.applicability?.[0] && canonicalRefs?.retrieval?.[0];
  const effectiveRefs = complete ? { classification: canonicalRefs.classification![0], applicability: canonicalRefs.applicability![0], retrieval: canonicalRefs.retrieval![0] } : workflow ? undefined : submitted;
  const result = useQuery({ queryKey: ['m1-results', identity, context.project_id, context.analysis_snapshot_id, effectiveRefs],
    queryFn: ({ signal }) => m1Api.results(context, effectiveRefs!, signal), enabled: !!effectiveRefs, retry: false, staleTime: Infinity, gcTime: 0 });
  const evidence = useQuery({ queryKey: ['m1-workflow-evidence', identity, context.project_id, context.analysis_snapshot_id, canonicalRefs?.retrieval?.[0]],
    queryFn: ({ signal }) => m1Api.workflowEvidence(context, canonicalRefs!.retrieval![0], signal), enabled: !!canonicalRefs?.retrieval?.[0] && !complete, retry: false, staleTime: Infinity, gcTime: 0 });
  const canonical = useQuery({ queryKey: ['m1-formal-context', identity, context.project_id, context.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.context(context, signal), retry: false, gcTime: 0 });
  const flows = useQuery({ queryKey: ['m1-formal-flows', identity, context.project_id, context.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.flows(context, signal), retry: false, gcTime: 0 });
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  const data = result.data;
  const rag = data?.retrieval.rag_context_pack ?? evidence.data?.rag_context_pack;
  const items = rag?.evidence_pack.items ?? [];
  const state = (code: string) => <Tag color={['REVIEW_REQUIRED', 'INSUFFICIENT_EVIDENCE', 'CONFLICTED'].includes(code) ? 'warning' : 'blue'}>{statusKeys[code] ? t(statusKeys[code]) : t('ui.m1.unknownStatus')} · {code}</Tag>;
  const fields = (values: Record<string, string | number | string[] | null | undefined>) => Object.entries(values).map(([label, value]) => ({ key: label, label: t(label), children: Array.isArray(value) ? value.join(' · ') || t('notAvailable') : typeof value === 'number' ? formatNumber(value) : value ?? t('notAvailable') }));
  return <section aria-label={t('ui.m1.results')} className="m1-analysis">
    <Card title={t('ui.m1.results')}><Alert type="info" showIcon title={t('ui.m1.independentRead')} description={t('ui.m1.referenceHint')}/>
      <form className="m1-form" onSubmit={event => { event.preventDefault(); setSelected(undefined); setSubmitted({ ...refs }); }}>
        {(['classification', 'applicability', 'retrieval'] as const).map(key => <label key={key}>{t(`ui.m1.ref.${key}`)}<input value={refs[key]} required pattern={uuid.source} onChange={event => setRefs({ ...refs, [key]: event.target.value })}/></label>)}
        <Button htmlType="submit" disabled={!Object.values(refs).every(value => uuid.test(value))} loading={result.isFetching}>{t('ui.m1.loadResults')}</Button>
      </form>
      {result.isFetching ? <LoadingState/> : result.error ? <ErrorState error={result.error}/> : !data && <p>{t('ui.m1.noResults')}</p>}
    </Card>
    <Card title={t('ui.m1.formalContext')}><p>{t('ui.m1.projectViewNotice')}</p><Descriptions column={1} size="small" items={fields({ 'ui.m1.projectId': context.project_id, snapshot: context.analysis_snapshot_id })}/>
      {Array.isArray(canonical.data?.conflicts) && canonical.data.conflicts.length > 0 && <Alert type="warning" title={t('ui.m1.conflicted')}/>}
      {[canonical, flows].map((query, index) => query.isPending ? <LoadingState key={index}/> : query.error ? <ErrorState key={index} error={query.error}/> : <details key={index}><summary>{t(index === 0 ? 'ui.m1.formalContext' : 'ui.m1.formalFlows')}</summary><pre className="provenance">{JSON.stringify(query.data, null, 2)}</pre></details>)}
    </Card>
    {data && <>
      <div className="m1-result-grid"><Card title={t('ui.m1.classification')}>{state(data.classification.status)}
        <Descriptions column={1} size="small" items={fields({ 'ui.m1.category': data.classification.category_ids, 'ui.m1.level': data.classification.level_id, 'ui.m1.reasons': data.classification.reason_codes, 'ui.m1.rules': data.classification.rule_hit_ids, 'ui.m1.evidenceRefs': data.classification.evidence_ids, 'ui.m1.resultId': data.classification.classification_result_id, 'ui.m1.revision': data.classification.record_version })}/>
        {data.classification.review_required && <Alert type="warning" title={t('ui.m1.reviewRequired')}/>}
      </Card><Card title={t('ui.m1.applicability')}>{state(data.applicability.applicability_status)}
        <Descriptions column={1} size="small" items={fields({ jurisdiction: data.applicability.jurisdiction_id, 'ui.m1.reasons': data.applicability.reason_codes, 'ui.m1.legalBasis': data.applicability.legal_basis_ids, 'ui.m1.regulation': data.applicability.regulation_document_id, 'ui.m1.regulationVersion': data.applicability.regulation_version_ref, 'ui.m1.resultId': data.applicability.applicability_result_id, snapshot: data.applicability.analysis_snapshot_id, 'ui.m1.asOf': formatDate(data.applicability.analysis_as_of_date) })}/>
        <Space>{data.applicability.review_required && <Alert type="warning" title={t('ui.m1.reviewRequired')}/>} {data.applicability.conflict_status === 'CONFLICTED' && <Alert type="warning" title={t('ui.m1.conflicted')}/>}</Space>
      </Card></div>
    </>}
    {evidence.isFetching && <LoadingState/>}{evidence.error && <ErrorState error={evidence.error}/>}
    {rag && <>
      <Card title={t('ui.m1.legalBasis')}><p>{t('ui.m1.officialEvidence')}</p><EvidenceTable items={items} open={item => setSelected(item.evidence_item_id)}/>
        {data && <details><summary>{t('provenance')}</summary><pre className="provenance">{JSON.stringify(data.applicability.provenance, null, 2)}</pre></details>}
      </Card>
      <SufficiencyPanel result={rag.knowledge_sufficiency}/>
      {(data?.applicability.fallback_guidance_context ?? rag.fallback_guidance_context) && <FallbackPanel guidance={(data?.applicability.fallback_guidance_context ?? rag.fallback_guidance_context)!}/>}
      <SourceCitationDrawer item={items.find(item => item.evidence_item_id === selected)} close={() => setSelected(undefined)}/>
    </>}
  </section>;
}
