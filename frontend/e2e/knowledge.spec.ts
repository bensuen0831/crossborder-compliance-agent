import { expect, test, type Page } from '@playwright/test';

import zhCN from '../src/locales/zh-CN.json' with { type: 'json' };
import zhHK from '../src/locales/zh-HK.json' with { type: 'json' };
import enUS from '../src/locales/en-US.json' with { type: 'json' };
type Locale = 'zh-CN' | 'zh-HK' | 'en-US';
const catalogs = { 'zh-CN': zhCN, 'zh-HK': zhHK, 'en-US': enUS };
const locales = Object.keys(catalogs) as Locale[];
const t = (locale: Locale, key: keyof typeof enUS) => catalogs[locale][key];
async function signIn(page: Page, persona: 'A' | 'B', locale: Locale) {
  const login = page.waitForResponse(r => r.url().includes('/m0-demo/login') && r.request().method() === 'POST');
  await page.getByRole('button', { name: t(locale, persona === 'A' ? 'loginA' : 'loginB'), exact: true }).click();
  const trusted = await (await login).json();
  await expect(page.getByText(trusted.display_name, { exact: true })).toBeVisible();
  const context = trusted.contexts[0];
  const scope = page.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/projects/${context.project_id}/knowledge-scope`, { timeout: 15000 });
  const project = page.getByRole('combobox', { name: t(locale, 'project') });
  await project.click();
  await project.press('ArrowDown');
  await project.press('Enter');
  expect((await scope).status()).toBe(200);
  await expect(page.getByRole('textbox', { name: t(locale, 'query') })).toBeEnabled();
}
async function switchLocale(page: Page, from: Locale, to: Locale) {
  await page.getByRole('combobox', { name: t(from, 'ui.language') }).click();
  const key = { 'zh-CN': 'ui.localeCN', 'zh-HK': 'ui.localeHK', 'en-US': 'ui.localeEN' }[to] as keyof typeof enUS;
  await page.getByTitle(t(from, key), { exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', to);
}
for (const locale of locales) test.describe(locale, () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(selected => localStorage.setItem('stage1-alpha.ui-locale', selected), locale);
  });

test('real multilingual Knowledge/Evidence/Sufficiency/Runtime and presentation-only locale switching', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', request => { if (request.method() !== 'GET' && new URL(request.url()).pathname.startsWith('/api/v1/')) writes.push(new URL(request.url()).pathname); });
  await page.goto('/');
  await signIn(page, 'A', locale);
  await page.getByRole('textbox', { name: t(locale, 'query') }).fill('Generic');
  const result = page.waitForResponse((r) => r.url().includes('/knowledge/retrieve') && r.status() === 200);
  await page.getByRole('button', { name: t(locale, 'search'), exact: true }).click();
  const actual = await (await result).json();
  expect(actual.rag_context_pack.evidence_pack.items.length).toBeGreaterThan(0);
  await expect(page.getByText(`${t(locale, 'INSUFFICIENT')} · INSUFFICIENT`)).toBeVisible();
  await expect(page.getByText(t(locale, 'fallback'), { exact: true })).toBeVisible();
  await page.screenshot({ path: `test-results/knowledge-evidence-${locale}.png`, fullPage: true });
  await page.getByRole('button', { name: t(locale, 'source') }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText(actual.rag_context_pack.evidence_pack.items[0].citation_id, { exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  const writesBeforeSwitch = [...writes];
  let current = locale;
  const official = actual.rag_context_pack.evidence_pack.items[0];
  for (const next of locales.filter(value => value !== locale)) {
    await switchLocale(page, current, next); current = next;
    await expect(page.getByRole('textbox', { name: t(current, 'query') })).toHaveValue('Generic');
    await expect(page.getByRole('textbox', { name: t(current, 'query') })).toBeEnabled();
    await expect(page.getByText(`${t(current, 'INSUFFICIENT')} · INSUFFICIENT`, { exact: true })).toBeVisible();
    await page.getByRole('button', { name: t(current, 'source') }).first().click();
    await expect(page.getByText(official.citation_id, { exact: true })).toBeVisible();
    await expect(page.getByText(official.original_text, { exact: true })).toBeVisible();
    await expect(page.getByText(official.analysis_snapshot_id, { exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
    expect(writes).toEqual(writesBeforeSwitch);
    expect(await page.evaluate(() => localStorage.getItem('stage1-alpha.ui-locale'))).toBe(current);
  }
  await switchLocale(page, current, locale);
  expect(writes).toEqual(writesBeforeSwitch);
  expect(writes).toHaveLength(1);
  expect(writes[0]).toContain('/knowledge/retrieve');
  await page.getByRole('button', { name: t(locale, 'operational'), exact: true }).click();
  await expect(page.getByText('READY', { exact: true })).toBeVisible();
});

test('identity switch purges evidence, isolates tenant B, and rejects A resource guessing server-side', async ({ page }) => {
  await page.goto('/'); await signIn(page, 'A', locale);
  await page.getByRole('textbox', { name: t(locale, 'query') }).fill('Generic');
  const response = page.waitForResponse((r) => r.url().includes('/knowledge/retrieve') && r.status() === 200);
  await page.getByRole('button', { name: t(locale, 'search'), exact: true }).click();
  const a = await (await response).json();
  await expect(page.getByText(`${t(locale, 'INSUFFICIENT')} · INSUFFICIENT`)).toBeVisible();
  await signIn(page, 'B', locale);
  await expect(page.getByRole('button', { name: t(locale, 'source') })).toHaveCount(0);
  const denied = await page.request.get(`/api/v1/retrieval-runs/${a.retrieval_run_id}`);
  expect(denied.status()).toBe(404);
  expect(await denied.text()).not.toContain(a.rag_context_pack.evidence_pack.items[0].original_text);
  await page.getByRole('textbox', { name: t(locale, 'query') }).fill('Generic');
  const bResponse = page.waitForResponse((r) => r.url().includes('/knowledge/retrieve') && r.status() === 200);
  await page.getByRole('button', { name: t(locale, 'search'), exact: true }).click();
  const b = await (await bResponse).json();
  expect(b.rag_context_pack.scope.tenant_id).not.toBe(a.rag_context_pack.scope.tenant_id);
  const aVersions = a.rag_context_pack.evidence_pack.items.map((item: { knowledge_version_id: string }) => item.knowledge_version_id);
  for (const item of b.rag_context_pack.evidence_pack.items) expect(aVersions).not.toContain(item.knowledge_version_id);
  await expect(page.getByText(`${t(locale, 'INSUFFICIENT')} · INSUFFICIENT`)).toBeVisible();
});

test('no-match query renders empty evidence and actionable backend guidance on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 1000 });
  await page.goto('/'); await signIn(page, 'A', locale);
  await page.getByRole('textbox', { name: t(locale, 'query') }).fill('zzznomatchtokenzzz');
  await page.getByRole('button', { name: t(locale, 'search'), exact: true }).click();
  await expect(page.getByText(t(locale, 'evidenceEmpty'))).toBeVisible();
  await expect(page.getByText(t(locale, 'fallback'), { exact: true })).toBeVisible();
  await expect(page.getByRole('progressbar')).toHaveCount(0);
});

test('canonical Admin route inspects real Knowledge version and denies the normal project user', async ({ page }) => {
  await page.goto('/'); await signIn(page, 'A', locale);
  await page.getByRole('textbox', { name: t(locale, 'query') }).fill('Generic');
  const response = page.waitForResponse(r => r.url().includes('/knowledge/retrieve') && r.status() === 200);
  await page.getByRole('button', { name: t(locale, 'search'), exact: true }).click();
  const evidence = (await (await response).json()).rag_context_pack.evidence_pack.items[0];
  await page.getByRole('link', { name: t(locale, 'admin'), exact: true }).click();
  await page.getByRole('button', { name: t(locale, 'ui.knowledgeOperations'), exact: true }).click();
  await page.getByLabel(t(locale, 'ui.knowledgeVersionId'), { exact: true }).fill(evidence.knowledge_version_id);
  await page.getByRole('button', { name: t(locale, 'ui.openVersion'), exact: true }).click();
  await expect(page.getByText('ACTIVE', { exact: true })).toBeVisible();
  await expect(page.getByText('READY', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /recovery|reindex/i })).toHaveCount(0);
  await page.screenshot({ path: `test-results/integrated-admin-${locale}.png`, fullPage: true });
  await page.getByRole('button', { name: t(locale, 'ui.rules'), exact: true }).click();
  await expect(page.getByLabel(t(locale, 'ui.ruleVersionId'))).toBeVisible();
  await expect(page.getByRole('button', { name: t(locale, 'ui.ruleAuthoringUnavailable') })).toBeDisabled();
  await page.getByRole('button', { name: t(locale, 'loginProject') }).click();
  await expect(page.getByText('UAT Project User', { exact: true })).toBeVisible();
  await expect(page.getByLabel(t(locale, 'ui.knowledgeVersionId'), { exact: true })).toHaveCount(0);
  for (const action of ['approve', 'publish', 'archive']) {
    const denied = await page.request.post(`/api/v1/admin/knowledge-versions/${evidence.knowledge_version_id}/${action}`, { data: { expected_record_version: 1 } });
    expect(denied.status()).toBe(403);
  }
  expect((await page.request.post(`/api/v1/admin/knowledge-versions/${evidence.knowledge_version_id}/recovery`)).status()).toBe(404);
});

});
