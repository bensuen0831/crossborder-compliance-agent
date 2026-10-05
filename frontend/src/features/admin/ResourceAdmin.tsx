import { formatNumber } from '../knowledge/formatting';
import { errorLabel } from '../../api/errors';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import type { AdminClient } from './client';
import type { AdminSession, Payload, RegistryItem, Resource, Version } from './contracts';
import { itemId, itemLabel, parseObject } from './presentation';
import { actions, allowed, operationFor } from './resources';


export function ResourceAdmin({ resource, client, session }: { resource: Resource; client: AdminClient; session: AdminSession }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<RegistryItem[]>([]);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('ALL');
  const [definitionId, setDefinitionId] = useState('');
  const [versions, setVersions] = useState<Version[]>([]);
  const [selected, setSelected] = useState<Version>();
  const [compare, setCompare] = useState<string>('');
  const [impact, setImpact] = useState<Payload>();
  const [creating, setCreating] = useState(false);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [fieldOptions, setFieldOptions] = useState<Record<string, RegistryItem[]>>({});
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);

  const canView = allowed(session, resource, 'VIEW');
  useEffect(() => {
    if (!canView || !resource.registry) return;
    const controller = new AbortController();
    client.registry(resource.registry, controller.signal).then(result => setItems(result.items)).catch(e => {
      if (!controller.signal.aborted) setError(e as Error);
    });
    return () => controller.abort();
  }, [client, resource, canView]);
  useEffect(() => {
    if (!canView) return;
    const controller = new AbortController();
    Promise.all(resource.fields.filter(field => field.type === 'metadata' && field.registry).map(async field => [field.name, (await client.registry(field.registry!, controller.signal)).items] as const))
      .then(entries => setFieldOptions(Object.fromEntries(entries))).catch(e => { if (!controller.signal.aborted) setError(e as Error); });
    return () => controller.abort();
  }, [client, resource, canView]);

  function choose(row: Version) {
    setSelected(row); setCreating(false); setImpact(undefined);
    const next: Record<string, string> = {};
    for (const field of resource.fields) {
      const value = field.name === 'payload' ? row.payload : row.payload?.[field.name];
      next[field.name] = value === undefined ? '' : field.type === 'json' ? JSON.stringify(value, null, 2) : String(value);
    }
    setFields(next);
  }
  async function run(task: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(null);
    try { await task(); } catch (e) { setError(e as Error); } finally { setBusy(false); }
  }
  function remember(row: Version) {
    setDefinitionId(row.definitionId);
    setVersions(old => [row, ...old.filter(v => v.id !== row.id && v.definitionId === row.definitionId)]);
    choose(row);
  }
  function payload(): Payload {
    if (resource.fields.some(field => field.name === 'payload')) return parseObject(fields.payload || '{}');
    return Object.fromEntries(resource.fields.map(field => [field.name, field.type === 'json' ? JSON.parse(fields[field.name] || (field.name === 'capability_requirement' ? '[]' : '{}')) : (fields[field.name] || null)])) as Payload;
  }
  if (!canView) return <p role="status">{t('ui.resourceUnavailable')}</p>;
  const canEdit = allowed(session, resource, 'EDIT');
  const editable = canEdit && (creating || (selected?.lifecycle === 'DRAFT' && selected.payload !== undefined));
  const comparison = versions.find(v => v.id === compare);
  return <div className="resource-grid">
    <section className="panel">
      <div className="section-title"><h2>{t(resource.label)}</h2>{canEdit && <button onClick={() => { setCreating(true); setSelected(undefined); setFields({}); setCode(''); setName(''); }}>{t('ui.createDraft')}</button>}</div>
      <p className="muted">{resource.registry ? t('ui.activeRegistryNote') : t('ui.noListNote')}</p>
      <label>{t('ui.searchResources')}<input value={query} onChange={e => setQuery(e.target.value)} placeholder={t('ui.searchPlaceholder')}/></label>
      <label>{t('ui.lifecycleFilter')}<select value={status} onChange={e => setStatus(e.target.value)}>{['ALL', 'DRAFT', 'PENDING_REVIEW', 'APPROVED', 'ACTIVE', 'SUPERSEDED', 'EXPIRED', 'ARCHIVED'].map(v => <option key={v} value={v}>{v === 'ALL' ? t('ui.allLifecycles') : v}</option>)}</select></label>
      <ul className="resource-list">{items.filter(item => itemLabel(item).toLowerCase().includes(query.toLowerCase())).map((item, i) => <li key={itemId(item) || i}><button disabled={busy || !itemId(item)} onClick={() => { const id = itemId(item); setDefinitionId(id); void run(async () => { const rows = await client.history(resource.key, id); setVersions(rows); if (rows[0]) choose(rows[0]); }); }}>{itemLabel(item)}</button></li>)}</ul>
      <form onSubmit={e => { e.preventDefault(); void run(async () => { const rows = await client.history(resource.key, definitionId.trim()); setVersions(rows); if (rows[0]) choose(rows[0]); else { setSelected(undefined); setError(new Error('ui.noVisibleVersions')); } }); }}>
        <label>{t('ui.definitionId')}<input required value={definitionId} onChange={e => setDefinitionId(e.target.value)}/></label><button disabled={busy}>{t('ui.openHistory')}</button>
      </form>
      <h3>{t('ui.versionHistory')}</h3>
      <ul className="resource-list">{versions.filter(v => status === 'ALL' || v.lifecycle === status).map(v => <li key={v.id}><button onClick={() => choose(v)} aria-pressed={selected?.id === v.id}>{t('ui.versionSymbol')}{v.number === null ? t('ui.notReported') : formatNumber(v.number)} · {v.lifecycle} {t('ui.revisionPrefix')} {formatNumber(v.recordVersion)}</button></li>)}</ul>
      <p className="muted">{t('ui.historyProjection')}</p>
    </section>
    <section className="panel">
      {error && <p role="alert" className="error">{errorLabel(error)}</p>}
      {!creating && !selected ? <div className="empty"><h3>{t('ui.selectResource')}</h3><p>{t('ui.selectResourceHint')}</p></div> : <>
        <div className="section-title"><h2>{creating ? t('ui.newDraft') : t('ui.versionLabel', { number: selected?.number === null || selected?.number === undefined ? t('ui.notReported') : formatNumber(selected.number) })}</h2>{selected && <span className="badge">{selected.lifecycle}</span>}</div>
        <form onSubmit={e => { e.preventDefault(); if (!editable) return; void run(async () => { const data = payload(); const row = creating ? await client.create(resource.key, { code, display_name: name, payload: data }) : await client.update(resource.key, selected!, data); remember({ ...row, definitionId: creating ? row.definitionId : selected!.definitionId, payload: data }); }); }}>
          {creating && <><label>{t('ui.code')}<input required maxLength={160} value={code} onChange={e => setCode(e.target.value)}/></label><label>{t('ui.displayName')}<input required maxLength={250} value={name} onChange={e => setName(e.target.value)}/></label></>}
          {resource.fields.map(field => <label key={field.name}>{t(field.label)}{field.type === 'metadata' ? <select required={field.required} disabled={!editable || busy} value={fields[field.name] || ''} onChange={e => setFields({ ...fields, [field.name]: e.target.value })}><option value="">{t('ui.chooseRegistered')}</option>{(fieldOptions[field.name] || []).map(item => <option key={itemId(item)} value={itemId(item)}>{itemLabel(item)}</option>)}</select> : <textarea required={field.required} disabled={!editable || busy} value={fields[field.name] || ''} onChange={e => setFields({ ...fields, [field.name]: e.target.value })} rows={field.type === 'json' ? 8 : 3}/>}</label>)}
          {editable && <button disabled={busy}>{creating ? t('ui.saveDraft') : t('ui.saveChanges')}</button>}
          {!creating && selected?.lifecycle === 'DRAFT' && selected.payload === undefined && <p className="muted">{t('ui.payloadGap')}</p>}
        </form>
        {selected && <>
          <p className="muted">{t('ui.versionIdPrefix')} {selected.id} {t('ui.recordRevisionPrefix')} {formatNumber(selected.recordVersion)}</p>
          <div className="actions">{actions(resource, selected.lifecycle).filter(action => allowed(session, resource, operationFor[action])).map(action => <button key={action} disabled={busy} onClick={() => void run(async () => { const row = await client.transition(resource.key, selected, action); remember({ ...row, definitionId: selected.definitionId, payload: selected.payload }); })}>{t(`ui.action.${action}`)}</button>)}
            <button disabled={busy} onClick={() => void run(async () => { const rows = await client.history(resource.key, selected.definitionId); setVersions(rows); const fresh = rows.find(v => v.id === selected.id); if (fresh) choose(fresh); })}>{t('ui.reloadVersion')}</button>
            <button disabled={busy} onClick={() => void run(async () => setImpact(await client.impact(resource.key, selected.definitionId)))}>{t('ui.impactPreview')}</button>
          </div>
          {impact && <pre aria-label={t('ui.impactPreview')}>{JSON.stringify(impact, null, 2)}</pre>}
          <label>{t('ui.compareVersion')}<select value={compare} onChange={e => setCompare(e.target.value)}><option value="">{t('ui.chooseVersion')}</option>{versions.filter(v => v.id !== selected.id).map(v => <option value={v.id} key={v.id}>{t('ui.versionSymbol')}{v.number === null ? t('ui.notReported') : formatNumber(v.number)} · {v.lifecycle}</option>)}</select></label>
          {comparison && <div><p>{t('ui.lifecyclePrefix')} {comparison.lifecycle} → {selected.lifecycle}{t('ui.compareRevisionPrefix')} {formatNumber(comparison.recordVersion)} → {formatNumber(selected.recordVersion)}</p>{comparison.payload && selected.payload ? <div className="comparison"><pre>{JSON.stringify(comparison.payload, null, 2)}</pre><pre>{JSON.stringify(selected.payload, null, 2)}</pre></div> : <p>{t('ui.comparisonGap')}</p>}</div>}
        </>}
      </>}
    </section>
  </div>;
}
