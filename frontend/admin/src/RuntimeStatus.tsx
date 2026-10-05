import { useEffect, useState } from 'react';
import type { AdminClient } from './client';
import type { RuntimeReadiness } from './contracts';

export function RuntimeStatus({ client, versionId }: { client: AdminClient; versionId: string }) {
  const [state, setState] = useState<RuntimeReadiness>();
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const next = await client.readiness(versionId, controller.signal);
        if (!active) return;
        setState(next); setError('');
        // Failures remain visible while the existing outbox retries automatically.
        if (next.status !== 'READY') timer = setTimeout(poll, 2000);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    setState(undefined); setError(''); void poll();
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [client, versionId]);
  return <section className="runtime" aria-label="Runtime publication" aria-live="polite">
    <h3>Runtime publication</h3>
    {error ? <p role="alert">{error}</p> : !state ? <p>Checking publication…</p> : <>
      <span className={`badge ${state.status.toLowerCase()}`}>{state.status}</span>
      <p>Publication automatically updates runtime assets. READY is reported by the backend.</p>
      <dl className="checks">{['registry', 'fts', 'vector', 'graph', 'cache'].map(key => <div key={key}>
        <dt>{key === 'vector' ? 'Embedding / vector' : key.toUpperCase()}</dt>
        <dd>{Object.hasOwn(state.checks, key) ? (state.checks[key] ? 'Verified' : 'Incomplete') : 'Not reported'}</dd>
      </div>)}</dl>
      <p>Registry projection: {state.registry_projection_version ?? 'Not reported'} · Cache generation: {state.cache_generation ?? 'Not reported'}</p>
      {!!state.reason_codes.length && <p role="alert">{state.reason_codes.join(', ')}</p>}
      {state.status === 'FAILED' && <p>The publication worker retries through the existing outbox. No manual reindex endpoint is exposed.</p>}
      <details><summary>Runtime asset evidence</summary><pre>{JSON.stringify(state.assets, null, 2)}</pre></details>
    </>}
  </section>;
}
