import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18n from '../../i18n';
import { IntegrationClients } from './IntegrationClients';
import { IntegrationAdminClient, type Client } from './api';
import type { AdminSession, FetchPort } from '../admin/contracts';

const session: AdminSession = { tenantId: 'ae31a4fe-8b1f-4f50-9e77-f083349d623a', actorId: 'admin', roles: ['admin'], grants: {}, backendScopes: ['integration:manage'] };
const client: Client = { client_id: '70f406cc-8473-442d-b839-4f7ef4554f49', display_name: 'ERP', allowed_scopes: ['project:read'], status: 'ACTIVE', credential_type: 'OAUTH2', credential_configured: true, record_version: 1, created_at: '2026-10-10T00:00:00Z', updated_at: '2026-10-10T00:00:00Z' };
const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
function view(transport: FetchPort, permission = session) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return { ...render(<QueryClientProvider client={cache}><IntegrationClients session={permission} transport={transport}/></QueryClientProvider>), cache };
}

describe('canonical integration Admin control plane', () => {
  it('does not issue management requests without host permission', async () => {
    const transport = vi.fn<FetchPort>();
    view(transport, { ...session, backendScopes: [] });
    expect(transport).not.toHaveBeenCalled();
  });

  it('rejects secret injection in GET metadata at runtime', async () => {
    const api = new IntegrationAdminClient(vi.fn<FetchPort>().mockResolvedValue(response([{ ...client, credential: 'must-not-render' }])));
    await expect(api.clients()).rejects.toMatchObject({ status: 502, message: 'API_CONTRACT_MISMATCH' });
  });

  for (const locale of ['zh-CN', 'zh-HK', 'en-US']) {
    it(`server-owned configuration, one-time credential, safe cache/storage ${locale}`, async () => {
      await i18n.changeLanguage(locale);
      let created = false;
      const transport = vi.fn<FetchPort>().mockImplementation(async (input, init) => {
        const path = String(input);
        if (path.endsWith('/options')) return response({ scopes: ['project:read'], webhook_events: ['WORKFLOW_COMPLETED'], credential_types: ['OAUTH2', 'SERVICE_ACCOUNT'], deployment_classes: ['EXTERNAL', 'INTERNAL'] });
        if (init?.method === 'POST') { created = true; return response({ client, credential_id: '168ece48-bccb-4c6a-8977-c9d65f11d579', credential: 'unit-one-time-only' }); }
        if (path.endsWith('/integration-clients')) return response(created ? [client] : []);
        return response([]);
      });
      const rendered = view(transport);
      await userEvent.type(screen.getByLabelText(i18n.t('ui.m2e.name')), 'ERP');
      await userEvent.click(await screen.findByLabelText('project:read'));
      await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m2e.createClient') }));
      expect(await screen.findByTestId('one-time-secret')).toHaveTextContent('unit-one-time-only');
      const creation = transport.mock.calls.find(([, init]) => init?.method === 'POST')!;
      const payload = JSON.parse(String(creation[1]?.body));
      expect(payload).toEqual({ display_name: 'ERP', credential_type: 'OAUTH2', allowed_scopes: ['project:read'] });
      expect(creation[1]?.credentials).toBe('same-origin');
      expect(creation[1]?.headers).toHaveProperty('Idempotency-Key');
      expect(JSON.stringify(rendered.cache.getQueryCache().getAll().map(q => q.state.data))).not.toContain('unit-one-time-only');
      expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain('unit-one-time-only');
      await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.m2e.dismiss') }));
      await waitFor(() => expect(screen.queryByTestId('one-time-secret')).not.toBeInTheDocument());
      expect(screen.getByText(i18n.t('ui.m2e.configured'))).toBeVisible();
    });
  }
});
