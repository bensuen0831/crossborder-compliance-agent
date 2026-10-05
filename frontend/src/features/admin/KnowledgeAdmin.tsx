import { formatNumber } from '../knowledge/formatting';
import { errorLabel } from '../../api/errors';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import type { AdminClient } from './client';
import type { AdminSession, KnowledgeVersion, Payload, RegistryItem, Resource, Source } from './contracts';
import { actions, allowed, operationFor } from './resources';
import { itemId, itemLabel, parseObject } from './presentation';
import { RuntimeStatus } from './RuntimeStatus';

export function KnowledgeAdmin({ client, session, resource }: { client: AdminClient; session: AdminSession; resource: Resource }) {
  const { t } = useTranslation();
  const [metadata, setMetadata] = useState<Record<string, RegistryItem[]>>({});
  const [source, setSource] = useState<Source>();
  const [sourceId, setSourceId] = useState('');
  const [sourceJson, setSourceJson] = useState('{"collection_id":"","code":"","source_type":"APPROVED_INTERNAL","language":"en","provenance":{}}');
  const [sourceUpdate, setSourceUpdate] = useState('{"enabled":true}');
  const [documentId, setDocumentId] = useState('');
  const [name, setName] = useState('');
  const [collectionVersion, setCollectionVersion] = useState('');
  const [language, setLanguage] = useState('en');
  const [provenance, setProvenance] = useState('{}');
  const [versionId, setVersionId] = useState('');
  const [version, setVersion] = useState<KnowledgeVersion>();
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [scopeType, setScopeType] = useState('GLOBAL');
  const [dimensions, setDimensions] = useState<Record<string, string>>({});
  const [permissionScopes, setPermissionScopes] = useState('[]');
  const [bindings, setBindings] = useState<Payload[]>([]);
  const [quality, setQuality] = useState<Payload[]>([]);
  const [ingestionId, setIngestionId] = useState('');
  const [ingestionStatus, setIngestionStatus] = useState('');
  const [requestKey, setRequestKey] = useState<string>(() => crypto.randomUUID());
  const [query, setQuery] = useState('');
  const [queryContract, setQueryContract] = useState('{}');
  const [result, setResult] = useState<Payload>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const canView = allowed(session, resource, 'VIEW');
  const canEdit = allowed(session, resource, 'EDIT');
  const ingestionAvailable = session.ingestionAvailable === true;
  useEffect(() => {
    if (!canView) return;
    const controller = new AbortController();
    Promise.all(['jurisdictions', 'products', 'scenarios'].map(async key => [key, (await client.registry(key, controller.signal)).items] as const))
      .then(entries => setMetadata(Object.fromEntries(entries))).catch(e => { if (!controller.signal.aborted) setError(e as Error); });
    return () => controller.abort();
  }, [client, canView]);
  const currentVersionId = version?.knowledge_version_id;
  useEffect(() => {
    if (!ingestionId || !currentVersionId || !canView) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await client.ingestionRun(ingestionId);
        if (!active) return;
        setIngestionStatus(`${next.status}${next.error_code ? ` · ${next.error_code}` : ''}`);
        if (next.status === 'COMPLETED') {
          const fresh = await client.getKnowledgeVersion(currentVersionId!);
          const scope = await client.bindings(currentVersionId!);
          if (active) { setVersion(fresh); setBindings(scope); }
        } else if (next.status !== 'FAILED') timer = setTimeout(poll, 1000);
      } catch (e) { if (active) setError(e as Error); }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [client, ingestionId, currentVersionId, canView]);
  async function run(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e as Error); } finally { setBusy(false); }
  }
  function remember(v: KnowledgeVersion) {
    if (version?.knowledge_version_id !== v.knowledge_version_id) {
      setBindings([]); setQuality([]); setIngestionId(''); setIngestionStatus(''); setResult(undefined);
    }
    setVersion(v); setVersionId(v.knowledge_version_id); setDocumentId(v.document_id);
  }
  if (!canView) return <p role="status">{t('ui.knowledgeUnavailable')}</p>;
  return <div className="knowledge-grid">
    {error && <p role="alert" className="error">{errorLabel(error)}</p>}
    <section className="panel">
      <h2>{t('ui.sourceDocument')}</h2><p className="muted">{t('ui.sharedKnowledgeNote')}</p>
      <label>{t('ui.sourceId')}<input value={sourceId} onChange={e => setSourceId(e.target.value)}/></label>
      <button disabled={busy || !sourceId} onClick={() => void run(async () => setSource(await client.getSource(sourceId)))}>{t('ui.openSource')}</button>
      {canEdit && <>
        <form onSubmit={e => { e.preventDefault(); void run(async () => { const next = await client.source(parseObject(sourceJson)); setSource(next); setSourceId(next.source_id); }); }}>
          <label>{t('ui.sourceMetadata')}<textarea value={sourceJson} onChange={e => setSourceJson(e.target.value)} rows={7}/></label><button disabled={busy}>{t('ui.createSource')}</button>
        </form>
        {source && <form onSubmit={e => { e.preventDefault(); void run(async () => setSource(await client.updateSource(source.source_id, source.record_version, parseObject(sourceUpdate)))); }}><label>{t('ui.sourceUpdate')}<textarea value={sourceUpdate} onChange={e => setSourceUpdate(e.target.value)}/></label><button disabled={busy}>{t('ui.updateSource')}</button></form>}
      </>}
      {source && <p>{t('ui.sourcePrefix')} {source.code} {t('ui.revisionPrefix')} {formatNumber(source.record_version)}</p>}
      <label>{t('ui.documentId')}<input value={documentId} onChange={e => setDocumentId(e.target.value)}/></label>
      {canEdit && <form onSubmit={e => { e.preventDefault(); void run(async () => { const doc = await client.document(sourceId, name); setDocumentId(doc.document_id); }); }}><label>{t('ui.documentName')}<input required value={name} onChange={e => setName(e.target.value)}/></label><button disabled={busy || !sourceId}>{t('ui.createDocument')}</button></form>}
      <p className="muted">{t('ui.knowledgeListGap')}</p>
    </section>
    <section className="panel">
      <h2>{t('ui.knowledgeVersion')}</h2>
      <form onSubmit={e => { e.preventDefault(); void run(async () => { remember(await client.getKnowledgeVersion(versionId)); setBindings(await client.bindings(versionId)); }); }}><label>{t('ui.knowledgeVersionId')}<input required value={versionId} onChange={e => setVersionId(e.target.value)}/></label><button disabled={busy}>{t('ui.openVersion')}</button></form>
      {canEdit && <form onSubmit={e => { e.preventDefault(); void run(async () => remember(await client.knowledgeVersion(documentId, { collection_version_id: collectionVersion, language, provenance: parseObject(provenance) }))); }}>
        <label>{t('ui.collectionVersionId')}<input required value={collectionVersion} onChange={e => setCollectionVersion(e.target.value)}/></label>
        <label>{t('ui.contentLanguage')}<input required value={language} onChange={e => setLanguage(e.target.value)}/></label>
        <label>{t('ui.provenanceJson')}<textarea value={provenance} onChange={e => setProvenance(e.target.value)}/></label>
        <button disabled={busy || !documentId}>{t('ui.createVersion')}</button>
      </form>}
      {version && <><div className="section-title"><h3>{t('ui.versionPrefix')} {formatNumber(version.version)}</h3><span className="badge">{version.lifecycle}</span></div><p>{t('ui.recordRevision')} {formatNumber(version.record_version)}</p>
        <div className="actions">{actions(resource, version.lifecycle).filter(action => allowed(session, resource, operationFor[action])).map(action => <button key={action} disabled={busy} onClick={() => void run(async () => { remember(await client.knowledgeTransition(version, action)); if (action === 'validate') setQuality(await client.quality(version.knowledge_version_id)); })}>{t(`ui.action.${action}`)}</button>)}
          <button disabled={busy} onClick={() => void run(async () => remember(await client.getKnowledgeVersion(version.knowledge_version_id)))}>{t('ui.reloadKnowledge')}</button>
        </div><p className="muted">{t('ui.independentReview')}</p>
        <details><summary>{t('ui.versionInspection')}</summary><pre>{JSON.stringify(version, null, 2)}</pre></details>
        <button disabled={busy} onClick={() => void run(async () => setQuality(await client.quality(version.knowledge_version_id)))}>{t('ui.inspectQuality')}</button>
        {!!quality.length && <details open><summary>{t('ui.qualityEvidence')}</summary><pre>{JSON.stringify(quality, null, 2)}</pre></details>}
      </>}
      <p className="muted">{t('ui.knowledgeHistoryGap')}</p>
    </section>
    <section className="panel">
      <h2>{t('ui.importScope')}</h2>
      {canEdit && version?.lifecycle === 'DRAFT' && <form onSubmit={e => { e.preventDefault(); void run(async () => {
        const provenanceData = parseObject(provenance);
        const scopes: unknown = JSON.parse(permissionScopes);
        if (!Array.isArray(scopes) || scopes.some(v => typeof v !== 'string')) throw new Error('ui.permissionArrayError');
        const binding = { scope_type: scopeType, dimensions: Object.fromEntries(Object.entries(dimensions).filter(([, v]) => v).map(([k, v]) => [k, [v]])), permission_scopes: scopes, provenance: provenanceData };
        const input: Payload = url ? { url } : { nodes: [{ node_type: 'OTHER', canonical_locator: 'document/1', original_text: text }] };
        const next = await client.ingest(version.knowledge_version_id, { idempotency_key: requestKey, ...input, bindings: [binding] });
        setIngestionId(next.ingestion_run_id); setIngestionStatus(next.status); remember(await client.getKnowledgeVersion(version.knowledge_version_id)); setBindings(await client.bindings(version.knowledge_version_id));
      }); }}>
        <label>{t('ui.importFile')}<input type="file" accept=".txt,text/plain" onChange={e => { const file = e.target.files?.[0]; if (file) void run(async () => { if (file.size > 1_000_000) throw new Error('ui.textLimitError'); setText(await file.text()); setUrl(''); }); }}/></label>
        <label>{t('ui.originalText')}<textarea value={text} onChange={e => { setText(e.target.value); setUrl(''); }} rows={5}/></label>
        <label>{t('ui.controlledUrl')}<input type="url" value={url} onChange={e => { setUrl(e.target.value); setText(''); }}/></label>
        <label>{t('ui.scopeType')}<select value={scopeType} onChange={e => { setScopeType(e.target.value); if (e.target.value === 'GLOBAL') setDimensions(old => ({ ...old, product: '' })); }}>{['GLOBAL', 'PRODUCT_SPECIFIC', 'DOMAIN_SHARED', 'CROSS_PRODUCT'].map(v => <option key={v}>{v}</option>)}</select></label>
        {Object.entries({ jurisdiction: 'jurisdictions', product: 'products', scenario: 'scenarios' }).map(([dimension, registry]) => <label key={dimension}>{t({ jurisdiction: 'jurisdiction', product: 'product', scenario: 'scenario' }[dimension as 'jurisdiction' | 'product' | 'scenario'])}<select disabled={dimension === 'product' && scopeType === 'GLOBAL'} value={dimensions[dimension] || ''} onChange={e => setDimensions({ ...dimensions, [dimension]: e.target.value })}><option value="">{t('ui.noRestriction')}</option>{(metadata[registry] || []).map(item => <option key={itemId(item)} value={itemId(item)}>{itemLabel(item)}</option>)}</select></label>)}
        <p className="muted">{t('ui.bindingMetadataGap')}</p>
        <label>{t('ui.permissionScopes')}<textarea value={permissionScopes} onChange={e => setPermissionScopes(e.target.value)}/></label>
        <label>{t('ui.importRequestKey')}<input required value={requestKey} onChange={e => setRequestKey(e.target.value)}/></label>
        <button type="button" onClick={() => setRequestKey(crypto.randomUUID())}>{t('ui.newImport')}</button>
        <button disabled={busy || !ingestionAvailable || (!text.trim() && !url)}>{t('ui.importContent')}</button>
      </form>}
      {!ingestionAvailable && <p className="muted">{t('ui.ingestionUnavailable')}</p>}
      {!!ingestionId && <><p aria-live="polite">{t('ui.ingestionPrefix')} {ingestionStatus}</p><button disabled={busy} onClick={() => void run(async () => { const next = await client.ingestionRun(ingestionId); setIngestionStatus(`${next.status}${next.error_code ? ` · ${next.error_code}` : ''}`); if (version) remember(await client.getKnowledgeVersion(version.knowledge_version_id)); })}>{t('ui.checkImport')}</button></>}
      {!!bindings.length && <details open><summary>{t('ui.scopeBindings')}</summary><pre>{JSON.stringify(bindings, null, 2)}</pre></details>}
      <h3>{t('ui.securityProfile')}</h3><p>{t('ui.scopeReviewNote')}</p>
      <p className="muted">{t('ui.securityWriteGap')}</p>
    </section>
    {version?.lifecycle === 'ACTIVE' && <RuntimeStatus client={client} versionId={version.knowledge_version_id}/>}
    {version?.lifecycle === 'ACTIVE' && session.projectId && <section className="panel"><h2>{t('ui.verifyRuntime')}</h2><form onSubmit={e => { e.preventDefault(); void run(async () => setResult(await client.retrieve(session.projectId!, { ...parseObject(queryContract), query_text: query }))); }}>
      <label>{t('ui.queryText')}<input required value={query} onChange={e => setQuery(e.target.value)}/></label><label>{t('ui.retrievalRequest')}<textarea value={queryContract} onChange={e => setQueryContract(e.target.value)}/></label><button disabled={busy}>{t('ui.queryRuntime')}</button></form>{result && <pre>{JSON.stringify(result, null, 2)}</pre>}</section>}
  </div>;
}
