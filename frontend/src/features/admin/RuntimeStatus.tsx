import { errorLabel } from '../../api/errors';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import type { AdminClient } from './client';
import type { RuntimeReadiness } from './contracts';

export function RuntimeStatus(props: { client: AdminClient; versionId: string }) {
  return <RuntimeStatusView key={props.versionId} {...props}/>;
}

function RuntimeStatusView({ client, versionId }: { client: AdminClient; versionId: string }) {
  const { t } = useTranslation();
  const [state, setState] = useState<RuntimeReadiness>();
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const next = await client.readiness(versionId, controller.signal);
        if (!active) return;
        setState(next); setError(null);
        // Failures remain visible while the existing outbox retries automatically.
        if (next.status !== 'READY') timer = setTimeout(poll, 2000);
      } catch (e) {
        if (active) setError(e as Error);
      }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [client, versionId]);
  return <section className="runtime" aria-label={t('ui.runtimePublication')} aria-live="polite">
    <h3>{t('ui.runtimePublication')}</h3>
    {error ? <p role="alert">{errorLabel(error)}</p> : !state ? <p>{t('ui.checkingPublication')}</p> : <>
      <span className={`badge ${state.status.toLowerCase()}`}>{state.status}</span>
      <p>{t('ui.publicationNote')}</p>
      <dl className="checks">{['registry', 'fts', 'vector', 'graph', 'cache'].map(key => <div key={key}>
        <dt>{key === 'vector' ? t('ui.embeddingVector') : key.toUpperCase()}</dt>
        <dd>{Object.hasOwn(state.checks, key) ? (state.checks[key] ? t('ui.verified') : t('ui.incomplete')) : t('ui.notReported')}</dd>
      </div>)}</dl>
      <p>{t('ui.registryProjectionPrefix')} {state.registry_projection_version ?? t('ui.notReported')} {t('ui.cacheGenerationPrefix')} {state.cache_generation ?? t('ui.notReported')}</p>
      {!!state.reason_codes.length && <p role="alert">{state.reason_codes.join(', ')}</p>}
      {state.status === 'FAILED' && <p>{t('ui.recoveryGap')}</p>}
      <details><summary>{t('ui.runtimeAssets')}</summary><pre>{JSON.stringify(state.assets, null, 2)}</pre></details>
    </>}
  </section>;
}
