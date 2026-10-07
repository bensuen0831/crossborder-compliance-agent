import { useState, type CSSProperties } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Steps, theme } from 'antd';
import { useTranslation } from 'react-i18next';
import type { AuthorizedContext, Session } from '../../api/contracts';
import { currentLocale } from '../../i18n';
import { ErrorState, LoadingState } from '../../components/States';
import { AnalysisPanel } from '../analysis/AnalysisPanel';
import { m1Api } from './api';
import { emptyDraft, optionId, optionLabel, type Draft, type GovernedOption, type WorkflowView } from './contracts';
import { restoreDraft, type IntakePersistence } from './persistence';
import { DocumentInputs } from './DocumentInputs';
import './intake.css';

export function IntakeFeature({ session, context: existingContext, persistence, initialStep = 0, onStepChange }: { session: Session; context?: AuthorizedContext; persistence?: IntakePersistence; initialStep?: number; onStepChange?: (step: number) => void }) {
  const context: AuthorizedContext | undefined = persistence ? (persistence.record.analysis_snapshot_id && persistence.record.retrieval_policy_id ? { project_id: persistence.record.project_id, analysis_snapshot_id: persistence.record.analysis_snapshot_id, policy_id: persistence.record.retrieval_policy_id, display_name: persistence.record.intake.project_name } : undefined) : existingContext;
  const projectId = persistence?.record.project_id ?? context?.project_id;
  const [dirty, setDirty] = useState(false);
  const { t } = useTranslation();
  const locale = currentLocale();
  const { token } = theme.useToken();
  const themeStyle = { '--text-primary': token.colorText, '--text-secondary': token.colorTextSecondary, '--surface-panel': token.colorBgContainer, '--border-color': token.colorBorder, '--accent': token.colorPrimary } as CSSProperties;
  const [step, setLocalStep] = useState(initialStep);
  function setStep(value: number | ((previous: number) => number)) { const next = typeof value === 'function' ? value(step) : value; setLocalStep(next); onStepChange?.(next); }
  const [draft, setDraft] = useState(() => persistence ? restoreDraft(persistence.record) : emptyDraft());
  const [confirmed, setConfirmed] = useState(persistence?.record.status === 'CONFIRMED');
  const [workflow, setWorkflow] = useState<WorkflowView>();
  const save = useMutation({ mutationFn: async () => { await persistence!.save(draft); setDirty(false); }, retry: false });
  const execute = useMutation({ mutationFn: async () => { if (persistence) { const value = await persistence.confirm(); if (!value.analysis_snapshot_id || !value.retrieval_policy_id) throw new Error('CONFIRMED_SNAPSHOT_REQUIRED'); return m1Api.workflowStart({ project_id: value.project_id, analysis_snapshot_id: value.analysis_snapshot_id, policy_id: value.retrieval_policy_id, display_name: value.intake.project_name }); } return m1Api.workflowStart(context!); }, onSuccess: setWorkflow, retry: false });
  const refresh = useMutation({ mutationFn: () => m1Api.workflowRead(workflow!.workflow_run_id), onSuccess: setWorkflow, retry: false });
  const workflowStatus: Record<string, string> = { RUNNING: 'ui.m1.workflowRunning', COMPLETED: 'ui.m1.workflowCompleted', REVIEW_REQUIRED: 'ui.m1.reviewRequired', WARNING: 'ui.m1.workflowWarning', FAILED: 'ui.m1.workflowFailed', CANCELLED: 'ui.m1.workflowFailed' };
  const metadata = useQuery({ queryKey: ['m1-metadata', session.identity_key, projectId, locale],
    queryFn: async ({ signal }): Promise<Record<string, GovernedOption[]>> => Object.fromEntries(await Promise.all(['scenarios', 'products', 'jurisdictions', 'data-types', ...(persistence ? ['data-categories'] : [])].map(async key => [key, (await m1Api.metadata(key, locale, signal)).items]))), retry: false, gcTime: 0 });
  const items = useQuery({ queryKey: ['m1-items', session.identity_key, projectId, context?.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.items({ project_id: projectId! }, signal), enabled: !!projectId, retry: false, gcTime: 0 });
  const parties = useQuery({ queryKey: ['m1-parties', session.identity_key, projectId, context?.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.parties({ project_id: projectId! }, signal), enabled: !!projectId, retry: false, gcTime: 0 });
  const documents = useQuery({ queryKey: ['m1-documents', session.identity_key, projectId, context?.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.documents(context!, signal), enabled: step === 2 && !!context, retry: false, gcTime: 0 });
  function update<K extends keyof Draft>(key: K, value: Draft[K]) { if (persistence?.record.status === 'CONFIRMED') return; setDirty(true); setDraft(previous => ({ ...previous, [key]: value })); setConfirmed(false); }
  const options = (resource: string) => (metadata.data?.[resource] ?? []).map(row => <option key={optionId(row)} value={optionId(row)}>{optionLabel(row)}</option>);
  const select = (key: 'scenario' | 'product', resource: string, label: string) => <label>{t(label)}<select required value={draft[key]} disabled={metadata.isPending || !!metadata.error || persistence?.record.status === 'CONFIRMED'} onChange={event => update(key, event.target.value)}><option value="">{t('ui.m1.choose')}</option>{options(resource)}</select></label>;
  const multi = (key: 'source' | 'destination' | 'processing' | 'storage' | 'categories' | 'dataTypes', resource: string, label: string) => <label>{t(label)}<select multiple value={draft[key]} disabled={persistence?.record.status === 'CONFIRMED' || metadata.isPending || !!metadata.error || !metadata.data?.[resource]?.length || (!!persistence && key === 'dataTypes')} onChange={event => update(key, Array.from(event.target.selectedOptions, option => option.value))}>{options(resource)}</select></label>;
  const party = (key: 'organizations' | 'thirdParties', label: string) => <label>{t(label)}<select multiple value={draft[key]} disabled={persistence?.record.status === 'CONFIRMED' || !parties.data?.length} onChange={event => update(key, Array.from(event.target.selectedOptions, option => option.value))}>{parties.data?.map(row => <option key={row.project_party_id} value={row.project_party_id}>{row.display_name}</option>)}</select></label>;
  const valid = draft.scenario && draft.product && draft.source.length && draft.destination.length && draft.purpose.trim() && draft.description.trim() && (persistence || (draft.flows.length > 0 && draft.flows.every(row => row.data_item_id && row.source_location && row.destination_location)));
  const scenario = metadata.data?.scenarios.find(row => optionId(row) === draft.scenario);
  const summary = Object.entries(draft).map(([key, value]) => <div key={key}><dt>{t(`ui.m1.field.${key}`)}</dt><dd>{typeof value === 'string' ? (Object.values(metadata.data ?? {}).flat().find(row => optionId(row) === value)?.presentation?.display_name ?? Object.values(metadata.data ?? {}).flat().find(row => optionId(row) === value)?.display_name ?? value) || t('notAvailable') : key === 'flows' ? draft.flows.map(row => <p key={row.id}>{row.data_item_id} → {row.source_location} → {row.destination_location}</p>) : (value as string[]).map(id => {
    const metadataRow = Object.values(metadata.data ?? {}).flat().find(row => optionId(row) === id);
    return <span className="m1-value" key={id}>{metadataRow ? optionLabel(metadataRow) : items.data?.find(row => row.data_item_id === id)?.display_name ?? parties.data?.find(row => row.project_party_id === id)?.display_name ?? id}</span>;
  })}</dd></div>);
  return <section style={themeStyle} className="m1-feature" aria-label={t('ui.m1.title')}>
    <Alert type="info" showIcon title={t(persistence ? 'ui.m2a.authoritative' : 'ui.m1.localDraft')} description={t(persistence ? 'ui.m2a.scenarioBoundary' : 'ui.m1.workflowPrepared')}/>
    <Steps current={step} items={['ui.m1.step1', 'ui.m1.step2', 'ui.m1.step3', 'ui.m1.step4'].map(key => ({ title: t(key) }))}/>
    {[metadata, items, parties].map((query, index) => query.isPending ? <LoadingState key={index}/> : query.error && <ErrorState key={index} error={query.error}/>)}
    <Card title={t(['ui.m1.step1', 'ui.m1.step2', 'ui.m1.step3', 'ui.m1.step4'][step])}>
      <form className="m1-form" onSubmit={event => { event.preventDefault(); setStep(value => Math.min(value + 1, 3)); }}>
        {step === 0 && <>{select('scenario', 'scenarios', 'ui.m1.field.scenario')}{select('product', 'products', 'ui.m1.field.product')}
          {scenario && <dl><dt>{t('ui.m1.scenarioMetadata')}</dt><dd>{optionLabel(scenario)}</dd><dd>{String(scenario.payload?.description ?? t('ui.m1.noDescription'))}</dd><dd>{scenario.presentation?.fallback_used ? t('ui.m1.metadataFallback') : scenario.code}</dd></dl>}
          <p>{t('ui.m1.capabilityGap')}</p></>}
        {step === 1 && <>
          <div className="m1-input-grid">{multi('source', 'jurisdictions', 'ui.m1.field.source')}{multi('destination', 'jurisdictions', 'ui.m1.field.destination')}{multi('processing', 'jurisdictions', 'ui.m1.field.processing')}{multi('storage', 'jurisdictions', 'ui.m1.field.storage')}{multi('dataTypes', 'data-types', 'ui.m1.field.dataTypes')}{multi('categories', persistence ? 'data-categories' : 'unavailable-category-catalog', 'ui.m1.field.categories')}
            <label>{t('ui.m1.field.items')}<select multiple value={draft.items} disabled={!items.data?.length} onChange={event => update('items', Array.from(event.target.selectedOptions, option => option.value))}>{items.data?.map(row => <option key={row.data_item_id} value={row.data_item_id}>{row.display_name ?? row.canonical_name ?? row.data_item_id}</option>)}</select></label>
            {party('organizations', 'ui.m1.field.organizations')}{party('thirdParties', 'ui.m1.field.thirdParties')}
            {persistence && <><label>{t('ui.m1.field.dataVolume')}<input value={draft.dataVolume} maxLength={256} disabled={persistence.record.status === 'CONFIRMED'} onChange={event => update('dataVolume', event.target.value)}/></label><label>{t('ui.m1.field.flowDescription')}<textarea value={draft.flowDescription} maxLength={4000} disabled={persistence.record.status === 'CONFIRMED'} onChange={event => update('flowDescription', event.target.value)}/></label></>}
            <label>{t('ui.m1.field.purpose')}<textarea value={draft.purpose} maxLength={2000} onChange={event => update('purpose', event.target.value)}/></label>
          </div>
          <fieldset disabled={!!persistence}><legend>{t('ui.m1.field.flows')}</legend>{draft.flows.map((row, index) => <div className="m1-flow" key={row.id}>
            {(['data_item_id', 'source_location', 'destination_location'] as const).map(field => <label key={field}>{t(`ui.m1.flow.${field}`)}<select value={row[field]} onChange={event => update('flows', draft.flows.map((value, position) => position === index ? { ...value, [field]: event.target.value } : value))}><option value="">{t('ui.m1.choose')}</option>{field === 'data_item_id' ? items.data?.map(item => <option key={item.data_item_id} value={item.data_item_id}>{item.display_name ?? item.canonical_name ?? item.data_item_id}</option>) : options('jurisdictions')}</select></label>)}
            <Button onClick={() => update('flows', draft.flows.filter(value => value.id !== row.id))}>{t('ui.m1.removeFlow')}</Button>
          </div>)}<Button onClick={() => update('flows', [...draft.flows, { id: crypto.randomUUID(), data_item_id: '', source_location: '', destination_location: '' }])}>{t('ui.m1.addFlow')}</Button></fieldset>
          <p>{t('ui.m1.categoryGap')}</p>
          {!parties.data?.length && <p>{t('ui.m1.noParties')}</p>}
        </>}
        {step === 2 && <><label>{t('ui.m1.field.description')}<textarea required maxLength={4000} value={draft.description} onChange={event => update('description', event.target.value)}/></label>
          {persistence ? <DocumentInputs persistence={persistence} identity={session.identity_key} dirty={dirty}/> : <>
          <label>{t('ui.m1.field.documents')}<textarea value={draft.documents} maxLength={2000} onChange={event => update('documents', event.target.value)}/></label>
          {!context ? <p>{t('ui.m1.documentGap')}</p> : documents.isPending ? <LoadingState/> : documents.error ? <ErrorState error={documents.error}/> : <details><summary>{t('ui.m1.documentsSummary')}</summary><pre className="provenance">{JSON.stringify(documents.data, null, 2)}</pre></details>}
          <Alert type="warning" title={t('ui.m1.documentGap')}/><Button disabled>{t('ui.m1.upload')}</Button><p>{t('ui.m1.untrusted')}</p></>}</>}
        {step === 3 && <><dl className="m1-summary">{summary}</dl>{persistence && <DocumentInputs persistence={persistence} identity={session.identity_key} dirty={dirty}/>} {!valid && <Alert type="warning" title={t('ui.m1.missingInputs')}/>}
          <label className="m1-confirm"><input type="checkbox" checked={confirmed} disabled={!valid} onChange={event => setConfirmed(event.target.checked)}/>{t('ui.m1.confirmFacts')}</label>
          {confirmed && <Alert type="info" title={t('ui.m1.factsOnly')}/>}<Button disabled={!confirmed || !valid || !!workflow || (!!persistence && dirty)} loading={execute.isPending} onClick={() => execute.mutate()}>{t(persistence ? 'ui.m2a.confirmStart' : 'ui.m1.execute')}</Button><p>{t('ui.m1.workflowPrepared')}</p></>}
        <div className="m1-actions">{persistence && <Button disabled={!dirty || persistence.record.status !== 'DRAFT'} loading={save.isPending} onClick={() => save.mutate()}>{t('ui.m2a.save')}</Button>}{step > 0 && <Button onClick={() => setStep(value => value - 1)}>{t('ui.m1.back')}</Button>}{step < 3 && <Button htmlType="submit" disabled={step === 0 && (!draft.scenario || !draft.product)}>{t('ui.m1.next')}</Button>}</div>
      </form>
    </Card>
    {(execute.isPending || refresh.isPending) && <LoadingState/>}
    {(save.error || execute.error || refresh.error) && <ErrorState error={save.error ?? execute.error ?? refresh.error!}/>}
    {workflow && <Card title={t('ui.m1.workflowExecution')}>
      <Alert type={workflow.status === 'COMPLETED' ? 'info' : 'warning'} title={t(workflowStatus[workflow.status] ?? 'ui.m1.unknownStatus')}/>
      <dl><dt>{t('ui.m1.workflowRun')}</dt><dd data-testid="workflow-run-id">{workflow.workflow_run_id}</dd><dt>{t('snapshot')}</dt><dd data-testid="workflow-snapshot-id">{workflow.analysis_snapshot_id}</dd></dl>
      {workflow.reason_codes.length > 0 && <p>{workflow.reason_codes.join(' · ')}</p>}
      {workflow.review_id && <p>{t('ui.m1.pendingReview')} · {workflow.review_id}</p>}
      <Button loading={refresh.isPending} onClick={() => refresh.mutate()}>{t('ui.m1.workflowRefresh')}</Button>
    </Card>}
    {context && <AnalysisPanel context={context} identity={session.identity_key} workflow={workflow}/>}
  </section>;
}
