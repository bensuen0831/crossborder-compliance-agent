import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import i18n, { supportedLocales } from '../../i18n';
import { ApiError } from '../../api/client';
import { ProductionIntake } from './ProductionIntake';
import { draftFacts, restoreDraft, intakeApi, type IntakeView } from './persistence';
import fixture from './m2a-fixture.json';
import m1 from './uat-fixture.json';
import type { Locale } from '../../i18n';
import type { Session } from '../../api/contracts';
const record = fixture as IntakeView;
const session = { ...m1.session, contexts: [] } as Session;
const facts = { ...record.intake, business_scenario: m1.refs.scenario, selected_products: [m1.refs.product], source_locations: [m1.refs.jurisdiction], destination_locations: [m1.refs.jurisdiction], business_purpose: 'Real user purpose', scenario_description: 'Manual scenario', data_volume: '3' };
function backend(current: IntakeView) {
  const writes: { path: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options: RequestInit = {}) => {
    const path = new URL(url, 'http://localhost');
    let value: unknown = [];
    if (path.pathname.includes('/metadata/')) value = m1.metadata[(path.searchParams.get('locale') ?? 'en-US') as Locale][path.pathname.split('/').at(-1) as keyof typeof m1.metadata['en-US']] ?? { ...m1.metadata['en-US']['data-types'], items: [] };
    else if (path.pathname.endsWith('/intake')) {
      if (options.method === 'PUT') { const body = JSON.parse(options.body as string); writes.push({ path: path.pathname, body }); current = { ...current, version: current.version + 1, intake: { ...current.intake, ...body.facts, record_version: current.version + 1 } }; }
      value = current;
    } else if (path.pathname === '/api/v1/projects') { writes.push({ path: path.pathname, body: JSON.parse(options.body as string) }); value = current; }
    return new Response(JSON.stringify(value), { status: 200 });
  }));
  return writes;
}
function host(path = '/intake') { return render(<MemoryRouter initialEntries={[path]}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProductionIntake session={session}/></QueryClientProvider></MemoryRouter>); }
describe('M2A existing H5 persistence', () => {
  for (const locale of supportedLocales) it(`new session creates and restores a server draft in ${locale}`, async () => {
    await i18n.changeLanguage(locale); const writes = backend({ ...record, intake: facts });
    host(); await userEvent.type(screen.getByLabelText(i18n.t('ui.m2a.projectName')), 'New user project');
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m2a.create') }));
    await screen.findByTestId('intake-project-id');
    await waitFor(() => expect(screen.getByLabelText(i18n.t('ui.m1.field.scenario'))).toHaveValue(m1.refs.scenario));
    expect(writes).toHaveLength(1); expect(writes[0].body).toEqual({ name: 'New user project', facts: { analysis_as_of_date: expect.any(String) }, idempotency_key: expect.any(String) });
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.next') }));
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m1.field.purpose')), { target: { value: 'Updated user value' } });
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m2a.save') }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1].body.expected_version).toBe(1);
    expect(writes[1].body.facts).toHaveProperty('business_purpose', 'Updated user value');
    expect(writes[1].body.facts).not.toHaveProperty('provenance');
  }, 15000);
  it('restored canonical facts preserve exact manual values without authority fields', () => {
    const saved = { ...record, intake: facts }; const draft = restoreDraft(saved);
    expect(draft.dataVolume).toBe('3'); expect(draftFacts(saved, draft)).toMatchObject({ data_volume: '3', business_purpose: facts.business_purpose });
    for (const field of ['tenant_id', 'project_id', 'analysis_snapshot_id', 'policy_id', 'workflow_run_id', 'provenance', 'record_version']) expect(draftFacts(saved, draft)).not.toHaveProperty(field);
  });
  it('restore route reads backend state without creating a second project', async () => {
    const writes = backend(record); host(`/intake?project_id=${record.project_id}`);
    await expect(screen.findByTestId('intake-project-id')).resolves.toHaveTextContent(record.project_id); expect(writes).toEqual([]);
  });
  it('typed transport fails closed for malformed stable status', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ...record, status: '適用' }))));
    await expect(intakeApi.read(record.project_id)).rejects.toBeInstanceOf(ApiError);
  });
});
