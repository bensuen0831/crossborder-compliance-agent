import { useEffect, useState } from 'react';
import type { AdminClient } from './client';
import type { AdminSession, KnowledgeVersion, Payload, RegistryItem, Resource, Source } from './contracts';
import { actions, allowed, operationFor } from './resources';
import { itemId, itemLabel, parseObject } from './presentation';
import { RuntimeStatus } from './RuntimeStatus';

export function KnowledgeAdmin({ client, session, resource }: { client: AdminClient; session: AdminSession; resource: Resource }) {
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
  const [error, setError] = useState('');
  const canView = allowed(session, resource, 'VIEW');
  const canEdit = allowed(session, resource, 'EDIT');
  const ingestionAvailable = session.ingestionAvailable === true;
  useEffect(() => {
    if (!canView) return;
    const controller = new AbortController();
    Promise.all(['jurisdictions', 'products', 'scenarios'].map(async key => [key, (await client.registry(key, controller.signal)).items] as const))
      .then(entries => setMetadata(Object.fromEntries(entries))).catch(e => { if (!controller.signal.aborted) setError((e as Error).message); });
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
      } catch (e) { if (active) setError((e as Error).message); }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [client, ingestionId, currentVersionId, canView]);
  async function run(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError('');
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  function remember(v: KnowledgeVersion) {
    if (version?.knowledge_version_id !== v.knowledge_version_id) {
      setBindings([]); setQuality([]); setIngestionId(''); setIngestionStatus(''); setResult(undefined);
    }
    setVersion(v); setVersionId(v.knowledge_version_id); setDocumentId(v.document_id);
  }
  if (!canView) return <p role="status">Knowledge operations are unavailable in your current context.</p>;
  return <div className="knowledge-grid">
    {error && <p role="alert" className="error">{error}</p>}
    <section className="panel">
      <h2>Source & document</h2><p className="muted">Product and country knowledge use scope bindings on the same governed resource.</p>
      <label>Source ID<input value={sourceId} onChange={e => setSourceId(e.target.value)}/></label>
      <button disabled={busy || !sourceId} onClick={() => void run(async () => setSource(await client.getSource(sourceId)))}>Open source</button>
      {canEdit && <>
        <form onSubmit={e => { e.preventDefault(); void run(async () => { const next = await client.source(parseObject(sourceJson)); setSource(next); setSourceId(next.source_id); }); }}>
          <label>Source metadata (JSON)<textarea value={sourceJson} onChange={e => setSourceJson(e.target.value)} rows={7}/></label><button disabled={busy}>Create source</button>
        </form>
        {source && <form onSubmit={e => { e.preventDefault(); void run(async () => setSource(await client.updateSource(source.source_id, source.record_version, parseObject(sourceUpdate)))); }}><label>Source update (enabled / refresh_policy / validation_status)<textarea value={sourceUpdate} onChange={e => setSourceUpdate(e.target.value)}/></label><button disabled={busy}>Update source</button></form>}
      </>}
      {source && <p>Source: {source.code} · revision {source.record_version}</p>}
      <label>Document ID<input value={documentId} onChange={e => setDocumentId(e.target.value)}/></label>
      {canEdit && <form onSubmit={e => { e.preventDefault(); void run(async () => { const doc = await client.document(sourceId, name); setDocumentId(doc.document_id); }); }}><label>Document display name<input required value={name} onChange={e => setName(e.target.value)}/></label><button disabled={busy || !sourceId}>Create document</button></form>}
      <p className="muted">Collection/source/document list APIs are not exposed. Use IDs from an existing resource or the response above.</p>
    </section>
    <section className="panel">
      <h2>Knowledge version</h2>
      <form onSubmit={e => { e.preventDefault(); void run(async () => { remember(await client.getKnowledgeVersion(versionId)); setBindings(await client.bindings(versionId)); }); }}><label>Knowledge version ID<input required value={versionId} onChange={e => setVersionId(e.target.value)}/></label><button disabled={busy}>Open version</button></form>
      {canEdit && <form onSubmit={e => { e.preventDefault(); void run(async () => remember(await client.knowledgeVersion(documentId, { collection_version_id: collectionVersion, language, provenance: parseObject(provenance) }))); }}>
        <label>Collection version ID<input required value={collectionVersion} onChange={e => setCollectionVersion(e.target.value)}/></label>
        <label>Content language<input required value={language} onChange={e => setLanguage(e.target.value)}/></label>
        <label>Provenance (JSON)<textarea value={provenance} onChange={e => setProvenance(e.target.value)}/></label>
        <button disabled={busy || !documentId}>Create version</button>
      </form>}
      {version && <><div className="section-title"><h3>Version {version.version}</h3><span className="badge">{version.lifecycle}</span></div><p>Record revision {version.record_version}</p>
        <div className="actions">{actions(resource, version.lifecycle).filter(action => allowed(session, resource, operationFor[action])).map(action => <button key={action} disabled={busy} onClick={() => void run(async () => { remember(await client.knowledgeTransition(version, action)); if (action === 'validate') setQuality(await client.quality(version.knowledge_version_id)); })}>{action}</button>)}
          <button disabled={busy} onClick={() => void run(async () => remember(await client.getKnowledgeVersion(version.knowledge_version_id)))}>Reload knowledge version</button>
        </div><p className="muted">Approval requires an independent human reviewer. Sign in through the host as the reviewer to continue.</p>
        <details><summary>Version inspection</summary><pre>{JSON.stringify(version, null, 2)}</pre></details>
        <button disabled={busy} onClick={() => void run(async () => setQuality(await client.quality(version.knowledge_version_id)))}>Inspect quality</button>
        {!!quality.length && <details open><summary>Quality gate evidence</summary><pre>{JSON.stringify(quality, null, 2)}</pre></details>}
      </>}
      <p className="muted">Knowledge history, version diff and audit endpoints are not exposed (ADMIN_BACKEND_GAP).</p>
    </section>
    <section className="panel">
      <h2>Import & scope</h2>
      {canEdit && version?.lifecycle === 'DRAFT' && <form onSubmit={e => { e.preventDefault(); void run(async () => {
        const provenanceData = parseObject(provenance);
        const scopes: unknown = JSON.parse(permissionScopes);
        if (!Array.isArray(scopes) || scopes.some(v => typeof v !== 'string')) throw new Error('Permission scopes must be a JSON array of strings.');
        const binding = { scope_type: scopeType, dimensions: Object.fromEntries(Object.entries(dimensions).filter(([, v]) => v).map(([k, v]) => [k, [v]])), permission_scopes: scopes, provenance: provenanceData };
        const input: Payload = url ? { url } : { nodes: [{ node_type: 'OTHER', canonical_locator: 'document/1', original_text: text }] };
        const next = await client.ingest(version.knowledge_version_id, { idempotency_key: requestKey, ...input, bindings: [binding] });
        setIngestionId(next.ingestion_run_id); setIngestionStatus(next.status); remember(await client.getKnowledgeVersion(version.knowledge_version_id)); setBindings(await client.bindings(version.knowledge_version_id));
      }); }}>
        <label>Import UTF-8 text file<input type="file" accept=".txt,text/plain" onChange={e => { const file = e.target.files?.[0]; if (file) void run(async () => { if (file.size > 1_000_000) throw new Error('Text import is limited to 1 MB.'); setText(await file.text()); setUrl(''); }); }}/></label>
        <label>Original text<textarea value={text} onChange={e => { setText(e.target.value); setUrl(''); }} rows={5}/></label>
        <label>Or controlled HTTPS source URL<input type="url" value={url} onChange={e => { setUrl(e.target.value); setText(''); }}/></label>
        <label>Scope type<select value={scopeType} onChange={e => { setScopeType(e.target.value); if (e.target.value === 'GLOBAL') setDimensions(old => ({ ...old, product: '' })); }}>{['GLOBAL', 'PRODUCT_SPECIFIC', 'DOMAIN_SHARED', 'CROSS_PRODUCT'].map(v => <option key={v}>{v}</option>)}</select></label>
        {Object.entries({ jurisdiction: 'jurisdictions', product: 'products', scenario: 'scenarios' }).map(([dimension, registry]) => <label key={dimension}>{dimension}<select disabled={dimension === 'product' && scopeType === 'GLOBAL'} value={dimensions[dimension] || ''} onChange={e => setDimensions({ ...dimensions, [dimension]: e.target.value })}><option value="">No restriction</option>{(metadata[registry] || []).map(item => <option key={itemId(item)} value={itemId(item)}>{itemLabel(item)}</option>)}</select></label>)}
        <p className="muted">Other binding dimensions await metadata list contracts. Non-global scopes must have a supported product dimension.</p>
        <label>Required permission scopes (JSON array)<textarea value={permissionScopes} onChange={e => setPermissionScopes(e.target.value)}/></label>
        <label>Import request key<input required value={requestKey} onChange={e => setRequestKey(e.target.value)}/></label>
        <button type="button" onClick={() => setRequestKey(crypto.randomUUID())}>New import request</button>
        <button disabled={busy || !ingestionAvailable || (!text.trim() && !url)}>Import content</button>
      </form>}
      {!ingestionAvailable && <p className="muted">Content ingestion is unavailable until the trusted deployment confirms artifact storage and the ingestion worker are ready.</p>}
      {!!ingestionId && <><p aria-live="polite">Ingestion: {ingestionStatus}</p><button disabled={busy} onClick={() => void run(async () => { const next = await client.ingestionRun(ingestionId); setIngestionStatus(`${next.status}${next.error_code ? ` · ${next.error_code}` : ''}`); if (version) remember(await client.getKnowledgeVersion(version.knowledge_version_id)); })}>Check import status</button></>}
      {!!bindings.length && <details open><summary>Persisted scope bindings</summary><pre>{JSON.stringify(bindings, null, 2)}</pre></details>}
      <h3>Security profile</h3><p>Scope and required permission scopes are persisted through ingestion and reviewed with the version.</p>
      <p className="muted">Sensitivity, external-model eligibility, download/export policy and retention/legal-hold references have no knowledge-write API contract. They cannot be edited here.</p>
    </section>
    {version?.lifecycle === 'ACTIVE' && <RuntimeStatus client={client} versionId={version.knowledge_version_id}/>}
    {version?.lifecycle === 'ACTIVE' && session.projectId && <section className="panel"><h2>Verify runtime content</h2><form onSubmit={e => { e.preventDefault(); void run(async () => setResult(await client.retrieve(session.projectId!, { ...parseObject(queryContract), query_text: query }))); }}>
      <label>Query text<input required value={query} onChange={e => setQuery(e.target.value)}/></label><label>Retrieval policy and analysis snapshot request (JSON)<textarea value={queryContract} onChange={e => setQueryContract(e.target.value)}/></label><button disabled={busy}>Query runtime</button></form>{result && <pre>{JSON.stringify(result, null, 2)}</pre>}</section>}
  </div>;
}
