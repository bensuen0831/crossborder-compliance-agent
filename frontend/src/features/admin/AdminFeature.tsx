import { useTranslation } from 'react-i18next';
import { useMemo, useState } from 'react';
import { AdminClient } from './client';
import type { AdminHost } from './contracts';
import { resources as defaults } from './resources';
import { ResourceAdmin } from './ResourceAdmin';
import { KnowledgeAdmin } from './KnowledgeAdmin';
import './admin.css';
import { RuleAdmin } from './RuleAdmin';
import { ModelProviders } from '../models/ModelProviders';
import { IntegrationClients } from '../integrations/IntegrationClients';

/** Mount inside Track C's authenticated shell; this feature owns only /admin. */
export function AdminFeature({ host }: { host: AdminHost }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState('jurisdictions');
  const client = useMemo(() => new AdminClient(host.transport), [host.transport]);
  const resources = host.resources ?? defaults;
  const resource = resources.find(r => r.key === selected) ?? resources[0];
  if (!host.session) return <main className={`admin-feature ${host.embedded ? 'admin-embedded' : ''}`}><section className="panel login"><p className="eyebrow">{t('ui.operationsWorkspace')}</p><h1>{t('admin')}</h1><p>{t('ui.signInHint')}</p>{host.onLogin ? <button onClick={host.onLogin}>{t('ui.signIn')}</button> : <p className="muted">{t('ui.hostSessionRequired')}</p>}</section></main>;
  const session = host.session;
  const contextKey = JSON.stringify(session);
  return <main className={`admin-feature ${host.embedded ? 'admin-embedded' : ''}`}>
    <header className="admin-header"><div><p className="eyebrow">{t('ui.governanceOperations')}</p><h1>{t('admin')}</h1><p>{t('adminSubtitle')}</p></div><div className="identity"><strong>{session.actorId}</strong><span>{session.roles.join(', ')}</span><span>{t('ui.tenant')} {session.tenantId}</span>{session.organizationId && <span>{t('ui.organization')} {session.organizationId}</span>}{session.departmentId && <span>{t('ui.department')} {session.departmentId}</span>}{session.projectId && <span>{t('ui.project')} {session.projectId}</span>}</div></header>
    <div className="admin-layout"><nav aria-label={t('ui.adminResources')}>{Array.from(new Set(resources.map(r => r.group))).map(group => <div key={t(group)}><h2>{t(group)}</h2>{resources.filter(r => r.group === group).map(r => <button key={r.key} aria-current={resource?.key === r.key ? 'page' : undefined} onClick={() => setSelected(r.key)}>{t(r.label)}</button>)}</div>)}</nav>
      <div className="admin-content">{resource && (resource.family === 'boundary' ? <section className="panel"><h2>{t(resource.label)}</h2><p>{t(resource.gap ?? 'ui.boundaryGap')}</p></section> : resource.key === 'integrations' ? <IntegrationClients key={contextKey} session={session} transport={host.transport}/> : resource.key === 'models' ? <ModelProviders key={contextKey} session={session} transport={host.transport}/> : resource.key === 'rules' ? <RuleAdmin key={contextKey} resource={resource} client={client} session={session}/> : resource.family === 'knowledge' ? <KnowledgeAdmin key={`${contextKey}:${resource.key}`} resource={resource} client={client} session={session}/> : <ResourceAdmin key={`${contextKey}:${resource.key}`} resource={resource} client={client} session={session}/>)}</div>
    </div><footer>{t('ui.authorizationNote')}</footer>
  </main>;
}
