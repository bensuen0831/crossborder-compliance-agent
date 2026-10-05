import { useState } from 'react';
import type { AdminClient } from './client';
import type { AdminSession, Payload, Resource } from './contracts';
import { allowed } from './resources';

/** Phase 1H owns these contracts and their legal semantics. */
export function RuleAdmin({ client, session, resource }: { client: AdminClient; session: AdminSession; resource: Resource }) {
  const [id, setId] = useState('');
  const [detail, setDetail] = useState<Payload>();
  const [validation, setValidation] = useState<Payload>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (!allowed(session, resource, 'VIEW')) return <p role="status">This resource is not available in your current context.</p>;
  async function inspect(validate = false) {
    setBusy(true); setError(''); setValidation(undefined);
    try {
      if (validate) setValidation(await client.validateRule(id.trim()));
      setDetail(await client.ruleDetail(id.trim()));
    } catch (e) { setDetail(undefined); setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="panel"><h2>Rules · Phase 1H</h2>
    <form onSubmit={e => { e.preventDefault(); void inspect(); }}>
      <label>Rule version ID<input required value={id} onChange={e => { setId(e.target.value); setDetail(undefined); setValidation(undefined); }}/></label>
      <button disabled={busy}>Inspect Rule version</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {detail && <><pre aria-label="Phase 1H Rule contract">{JSON.stringify(detail, null, 2)}</pre>
      <button disabled={busy || detail.lifecycle_status !== 'DRAFT' || !allowed(session, resource, 'REVIEW')} onClick={() => void inspect(true)}>Validate persisted Rule tests</button>
    </>}
    {validation && <pre aria-label="Rule validation result">{JSON.stringify(validation, null, 2)}</pre>}
    <p>Rule inspection and validation use the existing Phase 1H backend. Rule authoring and classification execution are unavailable in this Admin screen.</p>
    <button disabled>Rule authoring unavailable</button>
  </section>;
}
