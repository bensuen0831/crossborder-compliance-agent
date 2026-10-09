import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18n from '../../i18n';
import type { AdminSession, FetchPort } from '../admin/contracts';
import { ModelProviders } from './ModelProviders';
import { ModelControlClient } from './api';

const session: AdminSession = { actorId: 'admin', tenantId: '00000000-0000-0000-0000-000000000001', roles: ['admin'], grants: { models: ['VIEW', 'EDIT'] }, backendScopes: ['metadata:admin'] };
const version = { provider_id: '00000000-0000-0000-0000-000000000002', provider_version_id: '00000000-0000-0000-0000-000000000003', provider_version: 1, display_name: 'Instance A', vendor_preset: 'OTHER_OPENAI_COMPATIBLE', protocol: 'OPENAI_COMPATIBLE', base_url: 'https://provider.example/v1', deployment_class: 'EXTERNAL', trust_level: 'APPROVED', data_boundary: 'TENANT', secret_configured: true, enabled: true, lifecycle_status: 'DRAFT', record_version: 1, effective_from: '2026-10-08', effective_to: null };
const provider = { provider_id: version.provider_id, code: 'instance-a', display_name: 'Instance A', enabled: true, record_version: 1, active_version_id: null, versions: [version] };
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
function renderPanel(transport: FetchPort, permissions = session) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ModelProviders session={permissions} transport={transport}/></QueryClientProvider>);
}

describe('canonical model control plane', () => {
  it.each(['zh-CN', 'zh-HK', 'en-US'])('renders owned provider UI in %s without secrets', async locale => {
    await i18n.changeLanguage(locale);
    const transport = vi.fn<FetchPort>().mockImplementation(async input => response(String(input).includes('/metadata/') ? { items: [], registry_version: 'v1', health: { status: 'AVAILABLE' } } : { providers: [provider] }));
    renderPanel(transport);
    expect(await screen.findByText('Instance A')).toBeVisible();
    expect(screen.getByRole('heading', { name: i18n.t('ui.phase1kb.providers') })).toBeVisible();
    expect(screen.getByText(i18n.t('ui.phase1kb.configured'))).toBeVisible();
    expect(screen.getByLabelText(i18n.t('ui.phase1kb.credential'))).toHaveAttribute('type', 'password');
    expect(document.body.textContent).not.toContain('secret://');
    await i18n.changeLanguage('en-US');
  });

  it('saves write-only secret once and clears the credential field after success', async () => {
    await i18n.changeLanguage('en-US');
    const transport = vi.fn<FetchPort>().mockImplementation(async (input, options) => response(options?.method === 'POST' ? version : String(input).includes('/metadata/') ? { items: [], registry_version: 'v1', health: { status: 'AVAILABLE' } } : { providers: [] }));
    renderPanel(transport);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Stable code'), 'instance-a');
    await user.type(screen.getByLabelText('Display name'), 'Instance A');
    await user.type(screen.getByLabelText('Base URL'), 'https://provider.example/v1');
    await user.type(screen.getByLabelText('API key / Credential'), 'write-only-fixture-value');
    await user.type(screen.getByLabelText('Trust level'), 'APPROVED');
    await user.type(screen.getByLabelText('Data boundary'), 'TENANT');
    await user.click(screen.getByRole('button', { name: 'Save provider draft' }));
    await waitFor(() => expect(screen.getByLabelText('API key / Credential')).toHaveValue(''));
    const [, options] = transport.mock.calls.find(([, options]) => options?.method === 'POST')!;
    expect(JSON.parse(options!.body as string).credential).toBe('write-only-fixture-value');
    expect(options!.credentials).toBe('same-origin');
    for (const storage of [localStorage, sessionStorage]) {
      expect(Object.values(storage).join(' ')).not.toContain('write-only-fixture-value');
      expect(Object.keys(storage).join(' ')).not.toMatch(/credential|secret|api.?key/i);
    }
  });

  it('blocks provider administration for an ordinary user', () => {
    const transport = vi.fn<FetchPort>();
    renderPanel(transport, { ...session, backendScopes: [] });
    expect(screen.queryByRole('button', { name: 'Save provider draft' })).not.toBeInTheDocument();
    expect(transport).not.toHaveBeenCalled();
  });

  it('runtime-validates views and rejects unexpected secret fields', async () => {
    const client = new ModelControlClient(vi.fn<FetchPort>().mockResolvedValue(response({ providers: [{ ...provider, api_key: 'must-not-be-a-response' }] })));
    await expect(client.providers()).rejects.toMatchObject({ status: 502, message: 'API_CONTRACT_MISMATCH' });
  });
});
