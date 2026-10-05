import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import enAnt from 'antd/locale/en_US';
import cnAnt from 'antd/locale/zh_CN';
import hkAnt from 'antd/locale/zh_HK';
import i18n, { supportedLocales } from '../i18n';
import { formatDate, formatNumber } from '../features/knowledge/formatting';
import { QueryPanel } from '../components/QueryPanel';
import { SourceCitationDrawer } from '../components/Evidence';
import { SufficiencyPanel } from '../components/Sufficiency';
import { RuntimeStatus } from '../components/RuntimeStatus';
import { AdminFeature } from '../features/admin/AdminFeature';
import { ResourceAdmin } from '../features/admin/ResourceAdmin';
import { AdminClient } from '../features/admin/client';
import { resources, actions } from '../features/admin/resources';
import type { AdminSession, FetchPort } from '../features/admin/contracts';
import type { EvidenceItem, Session, Sufficiency } from '../api/contracts';
import retrieval from '../test/fixtures/retrieval.json';
import readiness from '../test/fixtures/readiness.json';
import session from '../test/fixtures/session.json';
import metadata from '../test/fixtures/products.json';
import { metadataLabel } from '../features/knowledge/presentation';

const admin: AdminSession = {
  actorId: 'actor', tenantId: '23715c5d-b86b-4d09-94a9-930124e467b0', roles: ['admin'],
  grants: Object.fromEntries(resources.map(resource => [resource.key, ['VIEW', 'EDIT', 'REVIEW', 'APPROVE', 'PUBLISH', 'ARCHIVE']])),
  backendScopes: ['metadata:admin', 'metadata:review', 'metadata:publish', 'knowledge:admin'],
};
const response = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });

for (const locale of supportedLocales) describe(locale, () => {
  it('covers M0 Knowledge, official Evidence, Sufficiency, Runtime and Admin', async () => {
    await i18n.changeLanguage(locale);
    const submit = vi.fn();
    const item = retrieval.rag_context_pack.evidence_pack.items[0] as EvidenceItem;
    const t = i18n.t.bind(i18n);
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async path => response(String(path).includes('runtime-readiness') ? readiness : { items: [], registry_version: 'v1', health: { status: 'ok' } })));
    render(<ConfigProvider locale={{ 'zh-CN': cnAnt, 'zh-HK': hkAnt, 'en-US': enAnt }[locale]}>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <QueryPanel disabled={false} busy={false} submit={submit}/>
        <SourceCitationDrawer close={vi.fn()}/>
        <SufficiencyPanel result={retrieval.rag_context_pack.knowledge_sufficiency as Sufficiency}/>
        <RuntimeStatus session={session as Session} versions={[item.knowledge_version_id!]}/>
        <AdminFeature host={{ session: admin }}/>
      </QueryClientProvider>
    </ConfigProvider>);
    await userEvent.type(screen.getByLabelText(t('query')), 'Original query');
    await userEvent.click(screen.getByRole('button', { name: t('search') }));
    expect(submit).toHaveBeenCalledWith('Original query');
    expect(await screen.findByText('READY', { exact: true })).toBeVisible();
    expect(screen.getByRole('button', { name: t('ui.knowledgeOperations') })).toBeInTheDocument();
    render(<ConfigProvider locale={{ 'zh-CN': cnAnt, 'zh-HK': hkAnt, 'en-US': enAnt }[locale]}><SourceCitationDrawer item={item} close={vi.fn()}/></ConfigProvider>);
    expect(await screen.findByRole('dialog')).toBeVisible();
    expect(screen.getByText(item.original_text, { exact: true })).toBeVisible();
    expect(screen.getByText(item.citation_id, { exact: true })).toBeVisible();
    expect(screen.getByText(/INSUFFICIENT/)).toBeVisible();
    expect(document.documentElement.lang).toBe(locale);
  }, 15000);

  it('formats presentation dates/numbers without translating backend metadata or codes', async () => {
    await i18n.changeLanguage(locale);
    expect(formatNumber(1234567)).toBe(new Intl.NumberFormat(locale).format(1234567));
    expect(formatDate('2025-01-23')).toBe(new Intl.DateTimeFormat(locale, { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC' }).format(new Date('2025-01-23')));
    const row = metadata.items[0];
    expect(metadataLabel(row.definition_id, metadata)).toBe(row.display_name);
    expect(actions(resources.find(resource => resource.key === 'knowledge-versions')!, 'EXPIRED')).toEqual(['archive']);
    expect(localStorage.getItem('stage1-alpha.ui-locale')).toBe(locale);
  });

  it('keeps lifecycle/action request codes and optimistic revision language-neutral', async () => {
    await i18n.changeLanguage(locale);
    const transport = vi.fn<FetchPort>().mockImplementation(async path => response(String(path).includes('/metadata/') ? { items: [], registry_version: 'v1', health: { status: 'ok' } } : String(path).endsWith('/versions') ? { items: [{ version_id: 'version-a', definition_id: 'definition-a', version_no: 1, lifecycle_status: 'APPROVED', record_version: 7 }] } : { version_id: 'version-a', definition_id: 'definition-a', version_no: 1, lifecycle_status: 'ACTIVE', record_version: 8 }));
    render(<ResourceAdmin resource={resources.find(resource => resource.key === 'scenarios')!} session={admin} client={new AdminClient(transport)}/>);
    await userEvent.type(screen.getByLabelText(i18n.t('ui.definitionId')), 'definition-a');
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.openHistory') }));
    await screen.findByText('APPROVED', { selector: '.badge' });
    await userEvent.click(screen.getByRole('button', { name: i18n.t('ui.action.publish') }));
    await screen.findByText('ACTIVE', { selector: '.badge' });
    expect(transport.mock.calls.some(([path, options]) => path === '/api/v1/admin/scenarios/version-a/publish' && JSON.parse(options!.body as string).expected_record_version === 7)).toBe(true);
  });
});

it('reports missing keys and never exposes a raw translation key', () => {
  const diagnostic = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  expect(i18n.t('nonexistent.production.label')).toBe(i18n.t('ui.translationUnavailable'));
  expect(diagnostic).toHaveBeenCalledWith('I18N_MISSING_KEY', 'nonexistent.production.label');
});
