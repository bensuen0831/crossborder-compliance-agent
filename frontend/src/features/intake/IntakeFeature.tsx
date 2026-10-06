import { useState, type CSSProperties } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Steps, theme } from 'antd';
import { useTranslation } from 'react-i18next';
import type { AuthorizedContext, Session } from '../../api/contracts';
import { currentLocale } from '../../i18n';
import { ErrorState, LoadingState } from '../../components/States';
import { AnalysisPanel } from '../analysis/AnalysisPanel';
import { m1Api } from './api';
import { emptyDraft, optionId, optionLabel, type Draft, type GovernedOption } from './contracts';
import './intake.css';

export function IntakeFeature({ session, context }: { session: Session; context: AuthorizedContext }) {
  const { t } = useTranslation();
  const locale = currentLocale();
  const { token } = theme.useToken();
  const themeStyle = { '--text-primary': token.colorText, '--text-secondary': token.colorTextSecondary, '--surface-panel': token.colorBgContainer, '--border-color': token.colorBorder, '--accent': token.colorPrimary } as CSSProperties;
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState(emptyDraft);
  const [confirmed, setConfirmed] = useState(false);
  const metadata = useQuery({ queryKey: ['m1-metadata', session.identity_key, context.project_id, locale],
    queryFn: async ({ signal }): Promise<Record<string, GovernedOption[]>> => Object.fromEntries(await Promise.all(['scenarios', 'products', 'jurisdictions', 'data-types'].map(async key => [key, (await m1Api.metadata(key, locale, signal)).items]))), retry: false, gcTime: 0 });
  const items = useQuery({ queryKey: ['m1-items', session.identity_key, context.project_id, context.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.items(context, signal), retry: false, gcTime: 0 });
  const parties = useQuery({ queryKey: ['m1-parties', session.identity_key, context.project_id, context.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.parties(context, signal), retry: false, gcTime: 0 });
  const documents = useQuery({ queryKey: ['m1-documents', session.identity_key, context.project_id, context.analysis_snapshot_id], queryFn: ({ signal }) => m1Api.documents(context, signal), enabled: step === 2, retry: false, gcTime: 0 });
  function update<K extends keyof Draft>(key: K, value: Draft[K]) { setDraft(previous => ({ ...previous, [key]: value })); setConfirmed(false); }
  const options = (resource: string) => (metadata.data?.[resource] ?? []).map(row => <option key={optionId(row)} value={optionId(row)}>{optionLabel(row)}</option>);
  const select = (key: 'scenario' | 'product', resource: string, label: string) => <label>{t(label)}<select required value={draft[key]} disabled={metadata.isPending || !!metadata.error} onChange={event => update(key, event.target.value)}><option value="">{t('ui.m1.choose')}</option>{options(resource)}</select></label>;
  const multi = (key: 'source' | 'destination' | 'processing' | 'storage' | 'categories' | 'dataTypes', resource: string, label: string) => <label>{t(label)}<select multiple value={draft[key]} disabled={metadata.isPending || !!metadata.error || !metadata.data?.[resource]?.length} onChange={event => update(key, Array.from(event.target.selectedOptions, option => option.value))}>{options(resource)}</select></label>;
  const party = (key: 'organizations' | 'thirdParties', label: string) => <label>{t(label)}<select multiple value={draft[key]} disabled={!parties.data?.length} onChange={event => update(key, Array.from(event.target.selectedOptions, option => option.value))}>{parties.data?.map(row => <option key={row.project_party_id} value={row.project_party_id}>{row.display_name}</option>)}</select></label>;
  const valid = draft.scenario && draft.product && draft.source.length && draft.destination.length && draft.purpose.trim() && draft.description.trim() && draft.flows.length > 0 && draft.flows.every(row => row.data_item_id && row.source_location && row.destination_location);
  const scenario = metadata.data?.scenarios.find(row => optionId(row) === draft.scenario);
  const summary = Object.entries(draft).map(([key, value]) => <div key={key}><dt>{t(`ui.m1.field.${key}`)}</dt><dd>{typeof value === 'string' ? (Object.values(metadata.data ?? {}).flat().find(row => optionId(row) === value)?.presentation?.display_name ?? Object.values(metadata.data ?? {}).flat().find(row => optionId(row) === value)?.display_name ?? value) || t('notAvailable') : key === 'flows' ? draft.flows.map(row => <p key={row.id}>{row.data_item_id} → {row.source_location} → {row.destination_location}</p>) : (value as string[]).map(id => {
    const metadataRow = Object.values(metadata.data ?? {}).flat().find(row => optionId(row) === id);
    return <span className="m1-value" key={id}>{metadataRow ? optionLabel(metadataRow) : items.data?.find(row => row.data_item_id === id)?.display_name ?? parties.data?.find(row => row.project_party_id === id)?.display_name ?? id}</span>;
  })}</dd></div>);
  return <section style={themeStyle} className="m1-feature" aria-label={t('ui.m1.title')}>
    <Alert type="info" showIcon title={t('ui.m1.localDraft')} description={t('ui.m1.workflowPending')}/>
    <Steps current={step} items={['ui.m1.step1', 'ui.m1.step2', 'ui.m1.step3', 'ui.m1.step4'].map(key => ({ title: t(key) }))}/>
    {[metadata, items, parties].map((query, index) => query.isPending ? <LoadingState key={index}/> : query.error && <ErrorState key={index} error={query.error}/>)}
    <Card title={t(['ui.m1.step1', 'ui.m1.step2', 'ui.m1.step3', 'ui.m1.step4'][step])}>
      <form className="m1-form" onSubmit={event => { event.preventDefault(); setStep(value => Math.min(value + 1, 3)); }}>
        {step === 0 && <>{select('scenario', 'scenarios', 'ui.m1.field.scenario')}{select('product', 'products', 'ui.m1.field.product')}
          {scenario && <dl><dt>{t('ui.m1.scenarioMetadata')}</dt><dd>{optionLabel(scenario)}</dd><dd>{String(scenario.payload?.description ?? t('ui.m1.noDescription'))}</dd><dd>{scenario.presentation?.fallback_used ? t('ui.m1.metadataFallback') : scenario.code}</dd></dl>}
          <p>{t('ui.m1.capabilityGap')}</p></>}
        {step === 1 && <>
          <div className="m1-input-grid">{multi('source', 'jurisdictions', 'ui.m1.field.source')}{multi('destination', 'jurisdictions', 'ui.m1.field.destination')}{multi('processing', 'jurisdictions', 'ui.m1.field.processing')}{multi('storage', 'jurisdictions', 'ui.m1.field.storage')}{multi('dataTypes', 'data-types', 'ui.m1.field.dataTypes')}{multi('categories', 'unavailable-category-catalog', 'ui.m1.field.categories')}
            <label>{t('ui.m1.field.items')}<select multiple value={draft.items} disabled={!items.data?.length} onChange={event => update('items', Array.from(event.target.selectedOptions, option => option.value))}>{items.data?.map(row => <option key={row.data_item_id} value={row.data_item_id}>{row.display_name ?? row.canonical_name ?? row.data_item_id}</option>)}</select></label>
            {party('organizations', 'ui.m1.field.organizations')}{party('thirdParties', 'ui.m1.field.thirdParties')}
            <label>{t('ui.m1.field.purpose')}<textarea value={draft.purpose} maxLength={2000} onChange={event => update('purpose', event.target.value)}/></label>
          </div>
          <fieldset><legend>{t('ui.m1.field.flows')}</legend>{draft.flows.map((row, index) => <div className="m1-flow" key={row.id}>
            {(['data_item_id', 'source_location', 'destination_location'] as const).map(field => <label key={field}>{t(`ui.m1.flow.${field}`)}<select value={row[field]} onChange={event => update('flows', draft.flows.map((value, position) => position === index ? { ...value, [field]: event.target.value } : value))}><option value="">{t('ui.m1.choose')}</option>{field === 'data_item_id' ? items.data?.map(item => <option key={item.data_item_id} value={item.data_item_id}>{item.display_name ?? item.canonical_name ?? item.data_item_id}</option>) : options('jurisdictions')}</select></label>)}
            <Button onClick={() => update('flows', draft.flows.filter(value => value.id !== row.id))}>{t('ui.m1.removeFlow')}</Button>
          </div>)}<Button onClick={() => update('flows', [...draft.flows, { id: crypto.randomUUID(), data_item_id: '', source_location: '', destination_location: '' }])}>{t('ui.m1.addFlow')}</Button></fieldset>
          <p>{t('ui.m1.categoryGap')}</p>
          {!parties.data?.length && <p>{t('ui.m1.noParties')}</p>}
        </>}
        {step === 2 && <><label>{t('ui.m1.field.description')}<textarea required maxLength={4000} value={draft.description} onChange={event => update('description', event.target.value)}/></label>
          <label>{t('ui.m1.field.documents')}<textarea value={draft.documents} maxLength={2000} onChange={event => update('documents', event.target.value)}/></label>
          {documents.isPending ? <LoadingState/> : documents.error ? <ErrorState error={documents.error}/> : <details><summary>{t('ui.m1.documentsSummary')}</summary><pre className="provenance">{JSON.stringify(documents.data, null, 2)}</pre></details>}
          <Alert type="warning" title={t('ui.m1.documentGap')}/><Button disabled>{t('ui.m1.upload')}</Button><p>{t('ui.m1.untrusted')}</p></>}
        {step === 3 && <><dl className="m1-summary">{summary}</dl>{!valid && <Alert type="warning" title={t('ui.m1.missingInputs')}/>}
          <label className="m1-confirm"><input type="checkbox" checked={confirmed} disabled={!valid} onChange={event => setConfirmed(event.target.checked)}/>{t('ui.m1.confirmFacts')}</label>
          {confirmed && <Alert type="info" title={t('ui.m1.factsOnly')}/>}<Button disabled>{t('ui.m1.execute')}</Button><p>{t('ui.m1.workflowPending')}</p></>}
        <div className="m1-actions">{step > 0 && <Button onClick={() => setStep(value => value - 1)}>{t('ui.m1.back')}</Button>}{step < 3 && <Button htmlType="submit" disabled={step === 0 && (!draft.scenario || !draft.product)}>{t('ui.m1.next')}</Button>}</div>
      </form>
    </Card>
    <AnalysisPanel context={context} identity={session.identity_key}/>
  </section>;
}
