import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import i18n, { supportedLocales } from '../../i18n';
import { DocumentInputs } from './DocumentInputs';
import { documentApi, type DocumentInputs as View } from './documentApi';
import type { IntakeView } from './persistence';
import fixture from './m2a-fixture.json';
const record = fixture as IntakeView;
const documents: View = { project_id: record.project_id, project_version_id: record.project_version_id, intake_version: record.version, intake_status: 'DRAFT', items: [{ document_id: '11111111-1111-4111-8111-111111111111', document_version_id: '22222222-2222-4222-8222-222222222222', document_version: 1, filename: 'actual.txt', size_bytes: 10, media_type: 'text/plain', content_hash: 'a'.repeat(64), parse_status: 'STORED', parse_run_id: null, quality_status: null, error_code: null, counts: {} }] };
function backend() {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => new Response(JSON.stringify(path.endsWith('/policy') ? { project_id: record.project_id, status: 'AVAILABLE', policy_version: 'v1', max_size_bytes: 100, allowed_types: [{ extension: '.txt', media_type: 'text/plain', signature: 'text' }], scan_required: false } : documents))));
}
function host(dirty = false) { const refresh = vi.fn(async () => {}); render(<QueryClientProvider client={new QueryClient()}><DocumentInputs persistence={{ record, refresh, save: vi.fn(), confirm: vi.fn() }} identity="authorized" dirty={dirty}/></QueryClientProvider>); return refresh; }
describe('M2B existing Step3 integration', () => {
  for (const locale of supportedLocales) it(`typed document status and source refs in ${locale}`, async () => {
    await i18n.changeLanguage(locale); backend(); const refresh = host();
    await screen.findByText('actual.txt');
    expect(screen.getByTestId('document-input')).toHaveTextContent(i18n.t('ui.m2b.stored'));
    expect(screen.getByLabelText(i18n.t('ui.m2b.select'))).toHaveAttribute('accept', '.txt');
    fireEvent.click(screen.getByRole('button', { name: i18n.t('ui.m2b.parse') }));
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    const calls = vi.mocked(fetch).mock.calls;
    const command = calls.find(([, options]) => options?.method === 'POST');
    expect(JSON.parse(command![1]!.body as string)).toEqual({ expected_version: record.version, idempotency_key: expect.any(String) });
  }, 15000);
  it('dirty browser draft cannot change authoritative attachments', async () => {
    backend(); host(true); await screen.findByText('actual.txt');
    expect(screen.getByRole('button', { name: i18n.t('ui.m2b.remove') })).toBeDisabled();
    expect(screen.getByLabelText(i18n.t('ui.m2b.select'))).toBeDisabled();
  });
  it('document read rejects mismatched project identity', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ...documents, project_id: '33333333-3333-4333-8333-333333333333' }))));
    await expect(documentApi.list(record.project_id)).rejects.toThrow('DOCUMENT_PROJECT_MISMATCH');
  });
});
