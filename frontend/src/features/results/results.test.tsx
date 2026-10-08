import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import i18n, { supportedLocales } from '../../i18n';
import { Stage1View } from './Stage1Workspace';
import { stage1Read, type Stage1Result } from './api';
import { validateContract } from '../../api/client';
import fixture from './pg-fixture.json';

function setup(result = validateContract<Stage1Result>('Stage1ComplianceResult', structuredClone(fixture))) {
  const writes: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options: RequestInit = {}) => {
    if (options.method && options.method !== 'GET') writes.push(url);
    return new Response(JSON.stringify({ items: [], registry_version: 'test', health: { status: 'READY' } }));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Stage1View result={result} identity="pg-test"/></QueryClientProvider>);
  return writes;
}

describe('Stage 1 authority presentation', () => {
  for (const locale of supportedLocales) it(`renders all formal visualizations without a legal write in ${locale}`, async () => {
    await i18n.changeLanguage(locale); const value = validateContract<Stage1Result>('Stage1ComplianceResult', structuredClone(fixture)); const original = JSON.stringify(value); const writes = setup(value);
    for (const key of ['workspace','workflow','risk','path','inventory','documents','requirements']) expect(screen.getAllByText(i18n.t(`ui.m2c.${key}`)).length).toBeGreaterThan(0);
    expect(screen.getByRole('img', { name: i18n.t('ui.m2c.transferMap') })).toBeVisible();
    expect(screen.getAllByText(i18n.t('ui.m2c.codes.DIRECT_TRANSFER_ALLOWED')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2c.chooseDocuments')}));
    expect(screen.getByText(i18n.t('ui.m2c.stage2Unavailable'))).toBeVisible();
    expect(writes).toHaveLength(0); expect(JSON.stringify(value)).toBe(original);
  });
  for (const locale of supportedLocales) it(`preserves an untranslated governed reason code in ${locale}`, async () => {
    await i18n.changeLanguage(locale);
    const value = validateContract<Stage1Result>('Stage1ComplianceResult', structuredClone(fixture));
    value.cross_border!.items[0].reason_codes = ['POLICY_EXTENSION_REASON'];
    const original = JSON.stringify(value);
    const errors = vi.spyOn(console, 'error');
    setup(value);
    expect(screen.getByText('POLICY_EXTENSION_REASON')).toBeVisible();
    expect(errors.mock.calls.filter(([code]) => code === 'I18N_MISSING_KEY')).toHaveLength(0);
    expect(JSON.stringify(value)).toBe(original);
  });
  it('keeps required legal documents when no template is available', async () => {
    setup(); expect(screen.getAllByText(i18n.t('ui.m2c.codes.REQUIRED')).length).toBeGreaterThan(0);
    expect(screen.getAllByText(i18n.t('ui.m2c.unavailable')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:i18n.t('ui.m2c.legalEvidence')}));
    await waitFor(()=>expect(screen.getByRole('dialog')).toBeVisible());
    expect(screen.getByText(fixture.legal_basis[0].official_source)).toBeVisible();
  });
  it('renders the owning blocked status independently of conditional implementation path', () => {
    const value=validateContract<Stage1Result>('Stage1ComplianceResult', structuredClone(fixture));
    value.cross_border!.items[0].status='TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED';
    value.final_path!.items[0].status='CONDITIONAL_PROPOSAL';
    setup(value);
    expect(screen.getAllByText(i18n.t('ui.m2c.codes.TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED')).length).toBeGreaterThan(0);
    expect(screen.queryByText(i18n.t('ui.m2c.codes.CONDITIONAL_TRANSFER_ALLOWED'))).toBeNull();
  });
  it('shows review without fabricating document requirements or future generation', () => {
    const value=validateContract<Stage1Result>('Stage1ComplianceResult', structuredClone(fixture)); value.status='REVIEW_REQUIRED'; value.document_requirements=null; value.final_path=null; value.cross_border=null;
    setup(value); expect(screen.getByRole('button',{name:i18n.t('ui.m2c.chooseDocuments')})).toBeDisabled();
    expect(screen.queryByText(i18n.t('ui.m2c.codes.DIRECT_TRANSFER_ALLOWED'))).toBeNull();
  });
  it('does not assign assessed-subject authority to unassessed inventory', () => {
    const value=validateContract<Stage1Result>('Stage1ComplianceResult', structuredClone(fixture)); value.data_items.push({...value.data_items[0],data_item_id:'11111111-1111-4111-8111-111111111111',name:'Unassessed item'});
    setup(value); const row=screen.getByText('Unassessed item').closest('tr')!;
    expect(row).toHaveTextContent(i18n.t('ui.m2c.unassessed')); expect(row).not.toHaveTextContent(i18n.t('ui.m2c.codes.DIRECT_TRANSFER_ALLOWED'));
  });
  it('runtime-validates the backend contract and rejects invented status', async () => {
    expect(validateContract<Stage1Result>('Stage1ComplianceResult',fixture).generation_available).toBe(false);
    const value=structuredClone(fixture); value.cross_border.items[0].status='ALLOWED';
    expect(()=>validateContract('Stage1ComplianceResult',value)).toThrow('API_CONTRACT_MISMATCH');
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(fixture))));
    expect((await stage1Read(fixture.workflow_run_id)).analysis_snapshot_id).toBe(fixture.analysis_snapshot_id);
  });
});
