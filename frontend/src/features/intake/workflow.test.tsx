import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import i18n, { supportedLocales } from '../../i18n';
import { IntakeFeature } from './IntakeFeature';
import { m1Api } from './api';
import type { Session } from '../../api/contracts';
import type { WorkflowView } from './contracts';
import fixture from './uat-fixture.json';

const session = fixture.session as Session;
const context = session.contexts[0];
const run = '11111111-1111-4111-8111-111111111111';
function setup(status: WorkflowView['status'] = 'COMPLETED', error = false) {
  const writes: RequestInit[] = [];
  const response: WorkflowView = { workflow_run_id: run, project_id: context.project_id, analysis_snapshot_id: context.analysis_snapshot_id, status, current_step: 'report', reason_codes: [], result_refs: { classification: [fixture.refs.classification], applicability: [fixture.refs.applicability], retrieval: [fixture.refs.retrieval] }, review_id: status === 'REVIEW_REQUIRED' ? run : null, fallback_ref: null };
  vi.stubGlobal('fetch', vi.fn(async (url: string, options: RequestInit = {}) => {
    if (options.method === 'POST') writes.push(options);
    const path = new URL(url, 'http://localhost'); const last = path.pathname.split('/').at(-1)!;
    if (last === 'workflow' || path.pathname.includes('/workflows/')) return new Response(JSON.stringify(response), { status: error ? 503 : 200 });
    const resources: Record<string, unknown> = { 'context-resolution': fixture.context, 'data-items': fixture.items, parties: fixture.parties, 'data-flows': fixture.flows, 'document-analysis-summary': fixture.documents };
    const body = path.pathname.includes('/metadata/') ? fixture.metadata['en-US'][last as keyof typeof fixture.metadata['en-US']] : path.pathname.includes('/classifications/') ? fixture.classification : path.pathname.includes('/regulation-applicability/') ? fixture.applicability : path.pathname.includes('/retrieval-runs/') ? fixture.retrieval : resources[last];
    return new Response(JSON.stringify(body));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendered = render(<QueryClientProvider client={client}><IntakeFeature key={context.analysis_snapshot_id} session={session} context={context}/></QueryClientProvider>);
  return { writes, response, client, ...rendered };
}
async function confirm() {
  const change = (key: string, value: string) => fireEvent.change(screen.getByLabelText(i18n.t(key)), { target: { value } });
  await waitFor(() => expect(screen.getByLabelText(i18n.t('ui.m1.field.scenario'))).toBeEnabled());
  change('ui.m1.field.scenario', fixture.refs.scenario); change('ui.m1.field.product', fixture.refs.product);
  const next = () => fireEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.next') })); next();
  for (const key of ['source','destination']) {
    const select = screen.getByLabelText(i18n.t(`ui.m1.field.${key}`)) as HTMLSelectElement;
    select.options[0].selected = true; fireEvent.change(select);
  }
  change('ui.m1.field.purpose', 'Synthetic purpose'); fireEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.addFlow') }));
  change('ui.m1.flow.data_item_id', fixture.refs.item);
  for (const key of ['source_location','destination_location']) change(`ui.m1.flow.${key}`, fixture.refs.jurisdiction);
  next(); change('ui.m1.field.description', 'Untrusted draft'); next();
  fireEvent.click(screen.getByRole('checkbox'));
  expect(screen.getByRole('button', { name: i18n.t('ui.m1.execute') })).toBeEnabled();
}
describe('M1 canonical workflow binding', () => {
  for (const locale of supportedLocales) it(`starts only canonical workflow and retains identities in ${locale}`, async () => {
    await i18n.changeLanguage(locale); const view = setup(); await confirm();
    fireEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.execute') }));
    expect(await screen.findByTestId('workflow-run-id')).toHaveTextContent(run);
    await screen.findByText(fixture.applicability.applicability_result_id);
    expect(view.writes).toHaveLength(1); expect(view.writes[0].body).toBe('{}');
    await i18n.changeLanguage(locale === 'en-US' ? 'zh-HK' : 'en-US');
    expect(screen.getByTestId('workflow-run-id')).toHaveTextContent(run);
    expect(screen.getByTestId('workflow-snapshot-id')).toHaveTextContent(context.analysis_snapshot_id);
    expect(view.writes).toHaveLength(1);
    view.rerender(<QueryClientProvider client={view.client}><IntakeFeature key="new-context" session={session} context={{ ...context, analysis_snapshot_id: run }}/></QueryClientProvider>);
    expect(screen.queryByTestId('workflow-run-id')).toBeNull();
  });
  for (const status of ['RUNNING','COMPLETED','REVIEW_REQUIRED','WARNING','FAILED'] as const) it(`presents server ${status} without synthesizing approval`, async () => {
    const view = setup(status); await confirm(); fireEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.execute') }));
    await screen.findByTestId('workflow-run-id');
    expect(view.response.status).toBe(status);
    if (status === 'REVIEW_REQUIRED') expect(screen.getByText(new RegExp(i18n.t('ui.m1.pendingReview')))).toBeVisible();
    if (status === 'WARNING') expect(screen.getByText(i18n.t('ui.m1.workflowWarning'))).toBeVisible();
    expect(view.writes).toHaveLength(1);
  });
  it('preserves transport error without fabricating a run', async () => {
    setup('FAILED', true); await confirm(); fireEvent.click(screen.getByRole('button', { name: i18n.t('ui.m1.execute') }));
    await waitFor(() => expect(screen.getByRole('button', { name: i18n.t('ui.m1.execute') })).not.toHaveClass('ant-btn-loading'));
    expect(screen.queryByTestId('workflow-run-id')).toBeNull();
  });
  it('rejects malformed public result references', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ workflow_run_id: 'not-a-reference' }))));
    await expect(m1Api.workflowStart(context)).rejects.toMatchObject({ status: 502 });
  });
});
