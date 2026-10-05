import { errorLabel } from '../../api/errors';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import type { AdminClient } from './client';
import type { AdminSession, Payload, Resource } from './contracts';
import { allowed } from './resources';

/** Phase 1H owns these contracts and their legal semantics. */
export function RuleAdmin({ client, session, resource }: { client: AdminClient; session: AdminSession; resource: Resource }) {
  const { t } = useTranslation();
  const [id, setId] = useState('');
  const [detail, setDetail] = useState<Payload>();
  const [validation, setValidation] = useState<Payload>();
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  if (!allowed(session, resource, 'VIEW')) return <p role="status">{t('ui.resourceUnavailable')}</p>;
  async function inspect(validate = false) {
    setBusy(true); setError(null); setValidation(undefined);
    try {
      if (validate) setValidation(await client.validateRule(id.trim()));
      setDetail(await client.ruleDetail(id.trim()));
    } catch (e) { setDetail(undefined); setError(e as Error); }
    finally { setBusy(false); }
  }
  return <section className="panel"><h2>{t('ui.rules')}</h2>
    <form onSubmit={e => { e.preventDefault(); void inspect(); }}>
      <label>{t('ui.ruleVersionId')}<input required value={id} onChange={e => { setId(e.target.value); setDetail(undefined); setValidation(undefined); }}/></label>
      <button disabled={busy}>{t('ui.inspectRule')}</button>
    </form>
    {error && <p role="alert">{errorLabel(error)}</p>}
    {detail && <><pre aria-label={t('ui.ruleContract')}>{JSON.stringify(detail, null, 2)}</pre>
      <button disabled={busy || detail.lifecycle_status !== 'DRAFT' || !allowed(session, resource, 'REVIEW')} onClick={() => void inspect(true)}>{t('ui.validateRule')}</button>
    </>}
    {validation && <pre aria-label={t('ui.ruleValidation')}>{JSON.stringify(validation, null, 2)}</pre>}
    <p>{t('ui.ruleScreenGap')}</p>
    <button disabled>{t('ui.ruleAuthoringUnavailable')}</button>
  </section>;
}
