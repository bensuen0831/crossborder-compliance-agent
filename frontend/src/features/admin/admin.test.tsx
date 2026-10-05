import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AdminFeature } from './AdminFeature';
import { AdminClient, ApiError } from './client';
import type { AdminSession, FetchPort, Lifecycle, Operation, RuntimeReadiness, Version } from './contracts';
import { actions, allowed, resources } from './resources';
import { ResourceAdmin } from './ResourceAdmin';
import { RuntimeStatus } from './RuntimeStatus';
import { KnowledgeAdmin } from './KnowledgeAdmin';
import { RuleAdmin } from './RuleAdmin';

const scenario = resources.find(r => r.key === 'scenarios')!;
const knowledge = resources.find(r => r.key === 'knowledge-versions')!;
const full: Operation[] = ['VIEW', 'EDIT', 'REVIEW', 'APPROVE', 'PUBLISH', 'ARCHIVE', 'DOWNLOAD', 'EXPORT', 'OPERATIONS'];
const session: AdminSession = {
  actorId: 'author', tenantId: 'tenant-a', roles: ['admin'],
  grants: Object.fromEntries(resources.map(r => [r.key, full])),
  backendScopes: ['metadata:admin', 'metadata:review', 'metadata:publish', 'knowledge:admin'],
};
const draft: Version = { id: 'version-a', definitionId: 'definition-a', number: 1, lifecycle: 'DRAFT', recordVersion: 1, payload: { visible: true } };
const wire = { version_id: 'version-a', definition_id: 'definition-a', version_no: 1, lifecycle_status: 'DRAFT', record_version: 1, payload: { visible: true } };
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
function client() { return new AdminClient(vi.fn<FetchPort>().mockResolvedValue(response({ registry_version: 'v1', health: {}, items: [] }))); }

describe('typed API transport', () => {
  it('uses optimistic record revision, same-origin credentials and no client identity headers', async () => {
    const transport = vi.fn<FetchPort>().mockResolvedValue(response({ ...wire, lifecycle_status: 'ACTIVE', record_version: 2 }));
    const api = new AdminClient(transport);
    expect((await api.transition('scenarios', draft, 'publish')).lifecycle).toBe('ACTIVE');
    const [path, options] = transport.mock.calls[0];
    expect(path).toBe('/api/v1/admin/scenarios/version-a/publish');
    expect(options?.credentials).toBe('same-origin');
    expect(JSON.parse(options?.body as string)).toEqual({ expected_record_version: 1 });
    expect(Object.keys(options?.headers ?? {})).toEqual(['Accept', 'Content-Type']);
  });
  it.each([401, 403, 409, 422])('propagates %i and hides raw server content', async status => {
    const api = new AdminClient(vi.fn<FetchPort>().mockResolvedValue(response({ detail: 'private configuration' }, status)));
    await expect(api.create('scenarios', { code: 'test', display_name: 'Test', payload: {} })).rejects.toMatchObject({ status });
    try { await api.registry('scenarios'); } catch (e) { expect((e as Error).message).not.toContain('private'); }
  });
  it('rejects incomplete lifecycle projections', async () => {
    const api = new AdminClient(vi.fn<FetchPort>().mockResolvedValue(response({ record_version: 1 })));
    await expect(api.create('scenarios', { code: 'a', display_name: 'a', payload: {} })).rejects.toBeInstanceOf(ApiError);
  });
  it('preserves canonical jurisdiction IDs and does not invent missing model version numbers', async () => {
    const api = new AdminClient(vi.fn<FetchPort>().mockResolvedValue(response({ items: [{ ...wire, definition_id: 'config-overlay', version_no: undefined }] })));
    const [row] = await api.history('jurisdictions', 'canonical-jurisdiction');
    expect(row.definitionId).toBe('canonical-jurisdiction');
    expect(row.number).toBeNull();
  });
});

describe('lifecycle and contextual grants', () => {
  it.each(['DRAFT', 'PENDING_REVIEW', 'APPROVED', 'ACTIVE', 'SUPERSEDED', 'EXPIRED', 'ARCHIVED'] as Lifecycle[])('renders %s from history', async lifecycle => {
    const api = client(); vi.spyOn(api, 'history').mockResolvedValue([{ ...draft, lifecycle }]);
    render(<ResourceAdmin resource={scenario} session={session} client={api}/>);
    await userEvent.type(screen.getByLabelText('Definition ID'), 'definition-a');
    await userEvent.click(screen.getByRole('button', { name: 'Open history' }));
    expect(await screen.findByText(lifecycle, { selector: '.badge' })).toBeVisible();
    if (lifecycle === 'ARCHIVED') expect(screen.queryByRole('button', { name: 'publish' })).not.toBeInTheDocument();
  });
  it('requires both effective resource grants and backend scope', () => {
    expect(allowed({ ...session, roles: ['superadmin'], grants: {} }, scenario, 'PUBLISH')).toBe(false);
    expect(allowed({ ...session, backendScopes: [] }, scenario, 'PUBLISH')).toBe(false);
    expect(actions(knowledge, 'DRAFT')).toEqual([]);
    expect(actions(knowledge, 'EXPIRED')).toEqual(['archive']);
    expect(allowed(session, resources.find(r => r.key === 'rules')!, 'VIEW')).toBe(true);
  });
  it('hides privileged publish controls from a project user with view access', async () => {
    const api = client(); const transition = vi.spyOn(api, 'transition');
    vi.spyOn(api, 'history').mockResolvedValue([{ ...draft, lifecycle: 'APPROVED' }]);
    render(<ResourceAdmin resource={scenario} session={{ ...session, roles: ['project-user'], grants: { scenarios: ['VIEW'] } }} client={api}/>);
    await userEvent.type(screen.getByLabelText('Definition ID'), 'definition-a');
    await userEvent.click(screen.getByRole('button', { name: 'Open history' }));
    await screen.findByText('APPROVED', { selector: '.badge' });
    expect(screen.queryByRole('button', { name: 'publish' })).not.toBeInTheDocument();
    expect(transition).not.toHaveBeenCalled();
  });
  it('creates, edits, reviews, approves and publishes using fresh revisions', async () => {
    const api = client();
    const create = vi.spyOn(api, 'create').mockResolvedValue(draft);
    vi.spyOn(api, 'update').mockResolvedValue({ ...draft, recordVersion: 2 });
    const transition = vi.spyOn(api, 'transition').mockImplementation(async (_key, current, action) => ({ ...current, recordVersion: current.recordVersion + 1, lifecycle: ({ 'submit-review': 'PENDING_REVIEW', approve: 'APPROVED', publish: 'ACTIVE' } as Record<string, Lifecycle>)[action] }));
    render(<ResourceAdmin resource={scenario} session={session} client={api}/>);
    await userEvent.click(screen.getByRole('button', { name: 'Create draft' }));
    await userEvent.type(screen.getByLabelText('Code'), 'scenario-new');
    await userEvent.type(screen.getByLabelText('Display name'), 'New scenario');
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    await screen.findByRole('button', { name: 'Save changes' });
    expect(create).toHaveBeenCalledWith('scenarios', { code: 'scenario-new', display_name: 'New scenario', payload: {} });
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(screen.getByText(/Record revision: 2/)).toBeVisible());
    for (const action of ['submit-review', 'approve', 'publish']) await userEvent.click(await screen.findByRole('button', { name: action }));
    await screen.findByText('ACTIVE', { selector: '.badge' });
    expect(transition.mock.calls.map(call => call[1].recordVersion)).toEqual([2, 3, 4]);
  });
  it('retains edit text on conflict and disables payload-less external drafts', async () => {
    const api = client(); vi.spyOn(api, 'history').mockResolvedValue([draft]);
    vi.spyOn(api, 'update').mockRejectedValue(new ApiError(409, 'Reload required'));
    render(<ResourceAdmin resource={scenario} session={session} client={api}/>);
    await userEvent.type(screen.getByLabelText('Definition ID'), 'definition-a');
    await userEvent.click(screen.getByRole('button', { name: 'Open history' }));
    await screen.findByRole('button', { name: 'Save changes' });
    await userEvent.clear(screen.getByLabelText('Version metadata (JSON)'));
    await userEvent.type(screen.getByLabelText('Version metadata (JSON)'), '{{"updated":true}');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Reload required');
    expect(screen.getByLabelText('Version metadata (JSON)')).toHaveValue('{"updated":true}');
  });
  it('uses metadata values supplied by the backend for scope controls', async () => {
    const api = client(); vi.spyOn(api, 'registry').mockImplementation(async key => ({ registry_version: 'v2', health: {}, items: [{ definition_id: `${key}-dynamic`, display_name: `New ${key} from API` }] }));
    vi.spyOn(api, 'getKnowledgeVersion').mockResolvedValue({ knowledge_version_id: 'k1', document_id: 'd1', collection_version_id: 'c1', record_version: 1, version: 1, lifecycle: 'DRAFT', language: 'en', provenance_json: {} });
    vi.spyOn(api, 'bindings').mockResolvedValue([]);
    render(<KnowledgeAdmin resource={knowledge} session={session} client={api}/>);
    await userEvent.type(screen.getByLabelText('Knowledge version ID'), 'k1');
    await userEvent.click(screen.getByRole('button', { name: 'Open version' }));
    expect(await screen.findByRole('option', { name: 'New jurisdictions from API' })).toHaveValue('jurisdictions-dynamic');
    expect(screen.getByRole('option', { name: 'New products from API' })).toHaveValue('products-dynamic');
    expect(screen.getByRole('option', { name: 'New scenarios from API' })).toHaveValue('scenarios-dynamic');
    await userEvent.type(screen.getByLabelText('Original text'), 'synthetic import');
    expect(screen.getByRole('button', { name: 'Import content' })).toBeDisabled();
  });
  it('disables editing of payload-less versions and compares only available projections', async () => {
    const api = client();
    vi.spyOn(api, 'history').mockResolvedValue([{ ...draft, payload: undefined }, { ...draft, id: 'v2', number: 2, payload: undefined, lifecycle: 'ACTIVE' }]);
    render(<ResourceAdmin resource={scenario} session={session} client={api}/>);
    await userEvent.type(screen.getByLabelText('Definition ID'), 'definition-a');
    await userEvent.click(screen.getByRole('button', { name: 'Open history' }));
    expect(await screen.findByLabelText('Version metadata (JSON)')).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Compare with version'), 'v2');
    expect(screen.getByText(/Content comparison is unavailable/)).toBeVisible();
  });
  it('clears selected data when tenant context changes', async () => {
    const transport = vi.fn<FetchPort>().mockImplementation(async path => response(String(path).endsWith('/versions') ? { items: [wire] } : { registry_version: 'v1', health: {}, items: [] }));
    const view = render(<AdminFeature host={{ session, transport }}/>);
    await userEvent.click(screen.getByRole('button', { name: 'Business scenarios' }));
    await userEvent.type(screen.getByLabelText('Definition ID'), 'definition-a');
    await userEvent.click(screen.getByRole('button', { name: 'Open history' }));
    await screen.findByText('DRAFT', { selector: '.badge' });
    view.rerender(<AdminFeature host={{ session: { ...session, tenantId: 'tenant-b', organizationId: 'other-org' }, transport }}/>);
    expect(screen.queryByText('DRAFT', { selector: '.badge' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Definition ID')).toHaveValue('');
  });
  it('requires a host login and consumes the Phase 1H Rule inspection contract', async () => {
    const login = vi.fn(); const view = render(<AdminFeature host={{ session: null, onLogin: login }}/>);
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' })); expect(login).toHaveBeenCalled();
    view.rerender(<AdminFeature host={{ session }}/>);
    await userEvent.click(screen.getByRole('button', { name: 'Rules · Phase 1H' }));
    expect(screen.getByLabelText('Rule version ID')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Create draft' })).not.toBeInTheDocument();
  });
});

describe('publication evidence', () => {
  const readiness: RuntimeReadiness = { knowledge_version_id: 'k1', tenant_id: 't1', status: 'READY', checks: { fts: true, vector: true, graph: true }, reason_codes: [], assets: {}, registry_projection_version: 'projection-2', cache_generation: 'k1', embedding_config_id: null };
  it('renders READY and absent check values honestly', async () => {
    const api = client(); vi.spyOn(api, 'readiness').mockResolvedValue(readiness);
    render(<RuntimeStatus client={api} versionId="k1"/>);
    expect(await screen.findByText('READY')).toBeVisible();
    expect(screen.getAllByText('Not reported')).toHaveLength(2);
    expect(screen.getAllByText('Verified')).toHaveLength(3);
  });
  it('shows a failed materialization without offering invented recovery operations', async () => {
    const api = client(); vi.spyOn(api, 'readiness').mockResolvedValue({ ...readiness, status: 'FAILED', reason_codes: ['RUNTIME_ASSET_BUILD_FAILED'] });
    render(<RuntimeStatus client={api} versionId="k1"/>);
    expect(await screen.findByText('FAILED')).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('RUNTIME_ASSET_BUILD_FAILED');
    expect(screen.queryByRole('button', { name: /reindex|retry/i })).not.toBeInTheDocument();
  });
});

describe('Phase 1H Rule integration', () => {
  it('uses the existing detail and persisted validation endpoints without classification writes', async () => {
    const transport = vi.fn<FetchPort>().mockImplementation(async () => response({ version_id: 'rule-a', lifecycle_status: 'DRAFT', runtime_contract: {}, tests: [] }));
    render(<RuleAdmin resource={resources.find(r => r.key === 'rules')!} session={session} client={new AdminClient(transport)}/>);
    await userEvent.type(screen.getByLabelText('Rule version ID'), 'rule-a');
    await userEvent.click(screen.getByRole('button', { name: 'Inspect Rule version' }));
    await screen.findByLabelText('Phase 1H Rule contract');
    await userEvent.click(screen.getByRole('button', { name: 'Validate persisted Rule tests' }));
    await screen.findByLabelText('Rule validation result');
    expect(transport.mock.calls.map(([path]) => path)).toEqual([
      '/api/v1/admin/rules/rule-a', '/api/v1/admin/rules/rule-a/validate', '/api/v1/admin/rules/rule-a',
    ]);
    expect(screen.getByRole('button', { name: 'Rule authoring unavailable' })).toBeDisabled();
  });
});
