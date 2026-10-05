import { useMemo, useState } from 'react';
import { AdminClient } from './client';
import type { AdminHost } from './contracts';
import { resources as defaults } from './resources';
import { ResourceAdmin } from './ResourceAdmin';
import { KnowledgeAdmin } from './KnowledgeAdmin';
import './admin.css';

/** Mount inside Track C's authenticated shell; this feature owns only /admin. */
export function AdminFeature({ host }: { host: AdminHost }) {
  const [selected, setSelected] = useState('jurisdictions');
  const client = useMemo(() => new AdminClient(host.transport), [host.transport]);
  const resources = host.resources ?? defaults;
  const resource = resources.find(r => r.key === selected) ?? resources[0];
  if (!host.session) return <main className="admin-feature"><section className="panel login"><p className="eyebrow">OPERATIONS WORKSPACE</p><h1>Admin operations</h1><p>Sign in through the application to access your organization's resources.</p>{host.onLogin ? <button onClick={host.onLogin}>Sign in</button> : <p className="muted">The host application's authenticated session is required.</p>}</section></main>;
  const session = host.session;
  const contextKey = JSON.stringify(session);
  return <main className="admin-feature">
    <header className="admin-header"><div><p className="eyebrow">GOVERNANCE / OPERATIONS</p><h1>Admin operations</h1><p>Create, review and publish versioned business resources.</p></div><div className="identity"><strong>{session.actorId}</strong><span>{session.roles.join(', ')}</span><span>Tenant {session.tenantId}</span>{session.organizationId && <span>Organization {session.organizationId}</span>}{session.departmentId && <span>Department {session.departmentId}</span>}{session.projectId && <span>Project {session.projectId}</span>}</div></header>
    <div className="admin-layout"><nav aria-label="Admin resources">{Array.from(new Set(resources.map(r => r.group))).map(group => <div key={group}><h2>{group}</h2>{resources.filter(r => r.group === group).map(r => <button key={r.key} aria-current={resource?.key === r.key ? 'page' : undefined} onClick={() => setSelected(r.key)}>{r.label}</button>)}</div>)}</nav>
      <div className="admin-content">{resource && (resource.family === 'boundary' ? <section className="panel"><h2>{resource.label}</h2><p>{resource.gap}</p></section> : resource.family === 'knowledge' ? <KnowledgeAdmin key={`${contextKey}:${resource.key}`} resource={resource} client={client} session={session}/> : <ResourceAdmin key={`${contextKey}:${resource.key}`} resource={resource} client={client} session={session}/>)}</div>
    </div><footer>Backend authorization and tenant scoping apply to every operation.</footer>
  </main>;
}
