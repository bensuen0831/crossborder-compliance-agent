import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ErrorState, LoadingState, PermissionDenied } from '../../components/States';
import type { AdminSession, FetchPort } from '../admin/contracts';
import { IntegrationAdminClient, type Client, type Delivery, type Subscription } from './api';

export function IntegrationClients({ session, transport }: { session: AdminSession; transport?: FetchPort }) {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const api = useMemo(() => new IntegrationAdminClient(transport), [transport]);
  const access = session.backendScopes.includes('integration:manage');
  const key = ['m2e-integrations', session.tenantId, session.actorId];
  const [selected, select] = useState<string>();
  const [secret, reveal] = useState<string>();
  const [error, setError] = useState<Error>();
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<Delivery[]>();
  const clients = useQuery({ queryKey: key, queryFn: () => api.clients(), enabled: access, retry: false });
  const options = useQuery({ queryKey: [...key, 'options'], queryFn: () => api.options(), enabled: access, retry: false });
  const subscriptions = useQuery({ queryKey: [...key, selected, 'webhooks'], queryFn: () => api.subscriptions(selected!), enabled: access && !!selected, retry: false });
  const bindings = useQuery({ queryKey: [...key, selected, 'bindings'], queryFn: () => api.bindings(selected!), enabled: access && !!selected, retry: false });
  const client = clients.data?.find(value => value.client_id === selected);
  async function act(operation: () => Promise<void>) {
    setBusy(true); setError(undefined); reveal(undefined);
    try { await operation(); await cache.invalidateQueries({ queryKey: key }); }
    catch (cause) { setError(cause instanceof Error ? cause : new Error('INTEGRATION_UNAVAILABLE')); }
    finally { setBusy(false); }
  }
  const mutate = (c: Client, status: string) => void act(async () => { await api.update(c, status); });
  const test = (sub: Subscription) => void act(async () => { await api.testWebhook(selected!, sub); setHistory(await api.deliveries(selected!, sub)); });
  if (!access) return <PermissionDenied />;
  return <section className="panel integration-clients">
    <h2>{t('ui.m2e.integrations')}</h2>
    {error && <ErrorState error={error} />}
    {[clients.error, options.error, subscriptions.error, bindings.error].filter(Boolean).map((value, i) => <ErrorState key={i} error={value!} />)}
    {secret && <div role="dialog" aria-label={t('ui.m2e.secretOnce')}><p>{t('ui.m2e.secretOnce')}</p><output data-testid="one-time-secret">{secret}</output><button onClick={() => reveal(undefined)}>{t('ui.m2e.dismiss')}</button></div>}
    {clients.isPending ? <LoadingState /> : <ul>{clients.data?.map(c => <li key={c.client_id}>
      <button onClick={() => { select(c.client_id); reveal(undefined); setHistory(undefined); }}>{c.display_name}</button>
      <span>{c.status}</span><span>{t('ui.m2e.configured')}</span><span>{c.last_used_at ?? t('ui.m2e.neverUsed')}</span>
      <button disabled={busy || c.status === 'REVOKED'} onClick={() => mutate(c, c.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE')}>{t(c.status === 'ACTIVE' ? 'ui.m2e.disable' : 'ui.m2e.enable')}</button>
      <button disabled={busy || c.status !== 'ACTIVE'} onClick={() => void act(async () => { const value = await api.rotate(c); reveal(value.credential ?? undefined); })}>{t('ui.m2e.rotate')}</button>
      <button disabled={busy || c.status === 'REVOKED'} onClick={() => mutate(c, 'REVOKED')}>{t('ui.m2e.revoke')}</button>
    </li>)}</ul>}
    <form aria-label={t('ui.m2e.createClient')} onSubmit={event => {
      event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
      void act(async () => { const value = await api.create({ display_name: String(data.get('name')), credential_type: String(data.get('type')), allowed_scopes: data.getAll('scopes') as Client['allowed_scopes'] }); select(value.client.client_id); reveal(value.credential ?? undefined); form.reset(); });
    }}>
      <label>{t('ui.m2e.name')}<input name="name" required maxLength={200} /></label>
      <label>{t('ui.m2e.credentialType')}<select name="type">{options.data?.credential_types.map(value => <option key={value}>{value}</option>)}</select></label>
      <fieldset><legend>{t('ui.m2e.scopes')}</legend>{options.data?.scopes.map(value => <label key={value}><input name="scopes" type="checkbox" value={value} />{value}</label>)}</fieldset>
      <button disabled={busy || !options.data} type="submit">{t('ui.m2e.createClient')}</button>
    </form>
    {client && <section>
      <h3>{client.display_name}</h3><p>{client.allowed_scopes.join(', ')}</p>
      <form key={client.record_version} aria-label={t('ui.m2e.saveScopes')} onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); void act(async () => { await api.update(client, client.status, data.getAll('scopes') as Client['allowed_scopes']); }); }}>
        <fieldset><legend>{t('ui.m2e.scopes')}</legend>{options.data?.scopes.map(value => <label key={value}><input name="scopes" type="checkbox" value={value} defaultChecked={client.allowed_scopes.includes(value)} />{value}</label>)}</fieldset><button disabled={busy}>{t('ui.m2e.saveScopes')}</button>
      </form>
      <form aria-label={t('ui.m2e.bindProject')} onSubmit={event => { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); void act(async () => { await api.bind(client, String(data.get('project'))); form.reset(); }); }}>
        <label>{t('ui.m2e.projectId')}<input name="project" required /></label><button disabled={busy}>{t('ui.m2e.bindProject')}</button>
      </form>
      <ul>{bindings.data?.map(value => <li key={value.project_id}>{value.project_id} {value.binding_type} {value.status}<button disabled={busy} onClick={() => void act(async () => { await api.bind(client, value.project_id, value.status === 'ACTIVE' ? 'REVOKED' : 'ACTIVE'); })}>{t(value.status === 'ACTIVE' ? 'ui.m2e.revokeBinding' : 'ui.m2e.bindProject')}</button></li>)}</ul>
      <h3>{t('ui.m2e.webhooks')}</h3>
      <form aria-label={t('ui.m2e.createWebhook')} onSubmit={event => { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); void act(async () => { const value = await api.createWebhook(selected!, { callback_url: String(data.get('callback')), deployment_class: String(data.get('deployment')), event_codes: data.getAll('events').map(String) }); reveal(value.secret ?? undefined); form.reset(); }); }}>
        <label>{t('ui.m2e.callback')}<input name="callback" type="url" required /></label>
        <label>{t('ui.m2e.deployment')}<select name="deployment">{options.data?.deployment_classes.map(value => <option key={value}>{value}</option>)}</select></label>
        <fieldset><legend>{t('ui.m2e.events')}</legend>{options.data?.webhook_events.map(value => <label key={value}><input name="events" type="checkbox" value={value} />{value}</label>)}</fieldset>
        <button disabled={busy}>{t('ui.m2e.createWebhook')}</button>
      </form>
      <ul>{subscriptions.data?.map(sub => <li key={sub.subscription_id}>
        <span>{sub.callback_url} {sub.event_codes.join(', ')} {t('ui.m2e.configured')}</span>
        <button disabled={busy} onClick={() => void act(async () => { await api.updateWebhook(selected!, sub, !sub.enabled); })}>{t(sub.enabled ? 'ui.m2e.disable' : 'ui.m2e.enable')}</button>
        <button disabled={busy} onClick={() => void act(async () => { const value = await api.rotateWebhook(selected!, sub); reveal(value.secret ?? undefined); })}>{t('ui.m2e.rotateWebhook')}</button>
        <button disabled={busy || !sub.enabled || client.status !== 'ACTIVE'} onClick={() => test(sub)}>{t('ui.m2e.testDelivery')}</button>
        <button disabled={busy} onClick={() => void act(async () => { setHistory(await api.deliveries(selected!, sub)); })}>{t('ui.m2e.history')}</button>
      </li>)}</ul>
      {history && <ul aria-label={t('ui.m2e.history')}>{history.map(value => <li key={value.delivery_id}>{value.delivery_id} {value.status} {value.attempts} {value.last_status_code} {value.error_code}</li>)}</ul>}
    </section>}
  </section>;
}
