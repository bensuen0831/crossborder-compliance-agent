import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import i18n, { supportedLocales } from '../../i18n';
import { IntakeFeature } from './IntakeFeature';
import { AnalysisPanel } from '../analysis/AnalysisPanel';
import { m1Api } from './api';
import { ApiError } from '../../api/client';
import fixture from './uat-fixture.json';
import type { Session } from '../../api/contracts';
import type { Locale } from '../../i18n';
const session = fixture.session as Session;
const context = session.contexts[0];
const refs = fixture.refs;
function mockFetch(status?: string) {
  const writes: string[] = [];
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string, options: RequestInit = {}) => {
    if (options.method && options.method !== 'GET') writes.push(url);
    const path = new URL(url, 'http://localhost');
    const last = path.pathname.split('/').at(-1);
    const resource = path.pathname.split('/').at(-2);
    let body: unknown = {};
    if (path.pathname.includes('/metadata/')) body = fixture.metadata[(path.searchParams.get('locale') ?? 'en-US') as Locale][last as keyof typeof fixture.metadata['en-US']];
    else if (resource === 'classifications') body = fixture.classification;
    else if (resource === 'regulation-applicability') body = { ...fixture.applicability, applicability_status: status ?? fixture.applicability.applicability_status, review_required: status === 'REVIEW_REQUIRED', conflict_status: status === 'CONFLICTED' ? 'CONFLICTED' : 'CLEAR' };
    else if (resource === 'retrieval-runs') body = fixture.retrieval;
    else body = ({ 'context-resolution': fixture.context, 'data-items': fixture.items, parties: fixture.parties, 'data-flows': fixture.flows, 'document-analysis-summary': fixture.documents } as Record<string, unknown>)[last!] ?? {};
    return new Response(JSON.stringify(body), { status: 200 });
  }));
  return writes;
}
function host(element: React.ReactNode) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } })}>{element}</QueryClientProvider>); }
async function loadResults() {
  for (const key of ['classification', 'applicability', 'retrieval'] as const) fireEvent.change(screen.getByLabelText(i18n.t(`ui.m1.ref.${key}`)), { target: { value: refs[key] } });
  await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.loadResults') }));
  await screen.findByText(fixture.applicability.applicability_result_id);
}
describe('M1 presentation and intake', () => {
  for (const locale of supportedLocales) it(`four-step structured intake in ${locale} confirms facts without backend writes`, async () => {
    await i18n.changeLanguage(locale); const writes = mockFetch();
    host(<IntakeFeature session={session} context={context}/>);
    await waitFor(() => expect(screen.getByLabelText(i18n.t('ui.m1.field.scenario'))).toBeEnabled());
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m1.field.scenario')), { target: { value: refs.scenario } });
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m1.field.product')), { target: { value: refs.product } });
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.next') }));
    for (const key of ['source', 'destination']) await userEvent.selectOptions(screen.getByLabelText(i18n.t(`ui.m1.field.${key}`)), refs.jurisdiction);
    await userEvent.type(screen.getByLabelText(i18n.t('ui.m1.field.purpose')), 'Synthetic purpose');
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.addFlow') }));
    for (const [key, value] of [['data_item_id', refs.item], ['source_location', refs.jurisdiction], ['destination_location', refs.jurisdiction]]) fireEvent.change(screen.getByLabelText(i18n.t(`ui.m1.flow.${key}`)), { target: { value } });
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.next') }));
    expect(screen.getByRole('button', { name: i18n.t('ui.m1.upload') })).toBeDisabled();
    await userEvent.type(screen.getByLabelText(i18n.t('ui.m1.field.description')), 'Untrusted description');
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.next') }));
    const confirm = screen.getByRole('checkbox', { name: i18n.t('ui.m1.confirmFacts') });
    expect(confirm).toBeEnabled(); await userEvent.click(confirm);
    expect(screen.getByText(i18n.t('ui.m1.factsOnly'))).toBeVisible();
    expect(screen.getByRole('button', { name: i18n.t('ui.m1.execute') })).toBeDisabled();
    expect(writes).toEqual([]);
    await i18n.changeLanguage(locale === 'en-US' ? 'zh-HK' : 'en-US');
    expect(screen.getByRole('checkbox', { name: i18n.t('ui.m1.confirmFacts') })).toBeChecked();
    expect(writes).toEqual([]);
  }, 15000);
  for (const status of ['APPLICABLE', 'NOT_APPLICABLE', 'CONDITIONALLY_APPLICABLE', 'INSUFFICIENT_EVIDENCE', 'CONFLICTED', 'REVIEW_REQUIRED']) it(`renders canonical ${status} without inferring it`, async () => {
    const writes = mockFetch(status); host(<AnalysisPanel context={context} identity={session.identity_key}/>); await loadResults();
    expect(screen.getByText(new RegExp(` · ${status}$`))).toBeVisible();
    expect(screen.getByText(fixture.classification.classification_result_id)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: fixture.retrieval.rag_context_pack.evidence_pack.items[0].canonical_locator }));
    expect(screen.getByText(fixture.retrieval.rag_context_pack.evidence_pack.items[0].original_text)).toBeVisible();
    expect(writes).toEqual([]);
  }, 10000);
  it('incomplete intake cannot confirm facts', async () => {
    mockFetch(); host(<IntakeFeature session={session} context={context}/>);
    await waitFor(() => expect(screen.getByLabelText(i18n.t('ui.m1.field.scenario'))).toBeEnabled());
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m1.field.scenario')), { target: { value: refs.scenario } });
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m1.field.product')), { target: { value: refs.product } });
    for (let i = 0; i < 2; i++) await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.next') }));
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m1.field.description')), { target: { value: 'description' } });
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.next') }));
    expect(screen.getByRole('checkbox')).toBeDisabled();
  });
  it('rejects canonical results for a different snapshot before presentation', async () => {
    mockFetch(); await expect(m1Api.results({ ...context, analysis_snapshot_id: crypto.randomUUID() }, refs)).rejects.toBeInstanceOf(ApiError);
  });
  it('rejects evidence-pack/classification mismatches', async () => {
    const body = { ...fixture.applicability, evidence_pack_ids: [crypto.randomUUID()] };
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('regulation-applicability') ? body : url.includes('classifications') ? fixture.classification : fixture.retrieval))));
    await expect(m1Api.results(context, refs)).rejects.toMatchObject({ status: 404 });
  });
  it('remounts intake presentation on a trusted snapshot context change', async () => {
    mockFetch(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { rerender } = render(<QueryClientProvider client={client}><IntakeFeature key={context.analysis_snapshot_id} session={session} context={context}/></QueryClientProvider>);
    await waitFor(() => expect(screen.getByLabelText(i18n.t('ui.m1.field.scenario'))).toBeEnabled());
    fireEvent.change(screen.getByLabelText(i18n.t('ui.m1.ref.classification')), { target: { value: refs.classification } });
    const next = { ...context, analysis_snapshot_id: crypto.randomUUID() };
    rerender(<QueryClientProvider client={client}><IntakeFeature key={next.analysis_snapshot_id} session={session} context={next}/></QueryClientProvider>);
    expect(screen.getByLabelText(i18n.t('ui.m1.ref.classification'))).toHaveValue('');
  });

});
