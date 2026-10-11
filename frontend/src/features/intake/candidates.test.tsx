import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18n from '../../i18n';
import { CandidateReview } from './CandidateReview';
import { useDocumentCandidates } from './candidateApi';
import type { IntakeView } from './persistence';

const project = '00000000-0000-0000-0000-000000000001';
const preparation = '00000000-0000-0000-0000-000000000002';
const member = '00000000-0000-0000-0000-000000000003';
const candidate = '00000000-0000-0000-0000-000000000004';
const version = '00000000-0000-0000-0000-000000000005';
const trace = '00000000-0000-0000-0000-000000000006';
const preview = { candidate_preparation_id: preparation, project_version_id: version, status: 'COMPLETED', candidate_universe_digest: 'a'.repeat(64), stale: false, candidate_decision_set_id: null, candidates: [{ preparation_candidate_id: member, candidate_id: candidate, candidate_type: 'BUSINESS_FACT', candidate_origin: 'LLM_STRUCTURED_OUTPUT', candidate_digest: 'b'.repeat(64), requires_confirmation: true, confidence: 1, proposed_payload: { normalized_value_json: 'Original proposal' }, sources: [{ source_trace_ref_id: trace, parse_run_id: trace, document_version_id: trace, section: 'Paragraph 1', source_excerpt: 'Genuine source excerpt' }], decision_status: 'UNRESOLVED', edited_payload: null, llm_provenance: null }] };

function Harness({ dirty = false }: { dirty?: boolean }) {
  const state = useDocumentCandidates({ project_id: project, version: 3, status: 'DRAFT' } as IntakeView, 'test-user', true);
  return <CandidateReview state={state} dirty={dirty}/>;
}
function host(dirty = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Harness dirty={dirty}/></QueryClientProvider>);
}

describe('pre-formal candidate consent', () => {
  it.each(['zh-CN', 'zh-HK', 'en-US'])('requires explicit action despite confidence1 in %s', async locale => {
    await i18n.changeLanguage(locale);
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(preview)));
    vi.stubGlobal('fetch', fetcher); host();
    const user = userEvent.setup();
    const select = await screen.findByRole('combobox');
    expect(select).toHaveValue('UNRESOLVED');
    expect(screen.getByRole('button', { name: i18n.t('ui.candidates.submit') })).toBeDisabled();
    await user.click(screen.getByText(i18n.t('ui.candidates.source')));
    expect(screen.getByText('Genuine source excerpt')).toBeVisible();
    await user.selectOptions(select, 'ACCEPT');
    expect(screen.getByRole('button', { name: i18n.t('ui.candidates.submit') })).toBeEnabled();
    expect(fetcher.mock.calls.every(([, request]) => !request?.method)).toBe(true);
    vi.unstubAllGlobals();
  });
  it.each(['REJECT', 'EDIT'])('submits %s with exact universe, original stays intact', async action => {
    await i18n.changeLanguage('en-US');
    const fetcher = vi.fn().mockImplementation((_url, request) => Promise.resolve(new Response(JSON.stringify(request?.method === 'POST' ? { candidate_preparation_id: preparation, candidate_decision_set_id: trace, submitted_by: 'server-user', submitted_at: '2026-10-11T00:00:00Z' } : preview))));
    vi.stubGlobal('fetch', fetcher); host(); const user = userEvent.setup();
    await user.selectOptions(await screen.findByRole('combobox'), action);
    if (action === 'EDIT') { const input = screen.getByLabelText(i18n.t('ui.candidates.editedValue')); await user.clear(input); await user.type(input, 'Authorized correction'); }
    await user.click(screen.getByRole('button', { name: i18n.t('ui.candidates.submit') }));
    await waitFor(() => expect(fetcher.mock.calls.some(([, request]) => request?.method === 'POST')).toBe(true));
    const request = fetcher.mock.calls.find(([, request]) => request?.method === 'POST')![1];
    const body = JSON.parse(request.body);
    expect(body).toMatchObject({ expected_version: 3, candidate_preparation_id: preparation, candidate_universe_digest: 'a'.repeat(64), decisions: [{ preparation_candidate_id: member, action }] });
    expect(body.actor_id).toBeUndefined(); expect(body.tenant_id).toBeUndefined();
    expect(body.decisions[0].edited_payload).toEqual(action === 'EDIT' ? { normalized_value: 'Authorized correction' } : undefined);
    expect(preview.candidates[0].proposed_payload.normalized_value_json).toBe('Original proposal');
    vi.unstubAllGlobals();
  });
  it('draft edits invalidate preparation actions', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(preview))));
    host(true); expect(await screen.findByRole('combobox')).toBeDisabled();
    expect(screen.getByRole('button', { name: i18n.t('ui.candidates.prepare') })).toBeDisabled();
    vi.unstubAllGlobals();
  });
});
