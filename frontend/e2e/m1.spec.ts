import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import zhCN from '../src/locales/zh-CN.json' with { type: 'json' };
import zhHK from '../src/locales/zh-HK.json' with { type: 'json' };
import enUS from '../src/locales/en-US.json' with { type: 'json' };
const catalogs = { 'zh-CN': zhCN, 'zh-HK': zhHK, 'en-US': enUS };
type Locale = keyof typeof catalogs;
type Persona = { contexts: { project_id: string; display_name: string; analysis_snapshot_id: string }[]; m1: { scenario: string; product: string; jurisdiction: string; item: string; classification: string; applicability: string; retrieval: string; status: string; official_text: string } };
const path = process.env.M1_UAT_MANIFEST;
const manifest: Record<'A' | 'B', Persona> | undefined = path ? JSON.parse(fs.readFileSync(path, 'utf8')) : undefined;
const t = (locale: Locale, key: keyof typeof enUS) => catalogs[locale][key];
async function login(page: Page, persona: 'A' | 'B', locale: Locale) {
  await page.getByRole('button', { name: t(locale, persona === 'A' ? 'loginA' : 'loginB'), exact: true }).click();
  await expect(page.getByText(`UAT User ${persona}`, { exact: true })).toBeVisible();
  const select = page.getByRole('combobox', { name: t(locale, 'project') });
  await select.click(); await select.press('ArrowDown'); await select.press('Enter');
  await page.getByRole('link', { name: t(locale, 'ui.m1.title'), exact: true }).click();
  await expect(page.getByLabel(t(locale, 'ui.m1.field.scenario'))).toBeEnabled();
}
async function load(page: Page, persona: Persona, locale: Locale) {
  for (const key of ['classification', 'applicability', 'retrieval'] as const) await page.getByLabel(t(locale, `ui.m1.ref.${key}`)).fill(persona.m1[key]);
  await page.getByRole('button', { name: t(locale, 'ui.m1.loadResults'), exact: true }).click();
  await expect(page.getByText(persona.m1.applicability, { exact: true })).toBeVisible();
}
// Old M0 CI selects knowledge.spec.ts explicitly; this suite requires real M1 fixtures.
for (const locale of Object.keys(catalogs) as Locale[]) test.describe(locale, () => {
  test.beforeEach(async ({ page }) => { await page.addInitScript(value => localStorage.setItem('stage1-alpha.ui-locale', value), locale); });
  test('four-step intake, canonical results, official citation and locale state invariance', async ({ page }) => {
    test.setTimeout(60000);
    expect(manifest, 'M1_UAT_MANIFEST must point to seeded real-backend fixtures').toBeDefined();
    const a = manifest!.A; const writes: string[] = [];
    page.on('request', request => { if (request.method() !== 'GET' && new URL(request.url()).pathname.startsWith('/api/v1/')) writes.push(request.url()); });
    await page.goto('/'); await login(page, 'A', locale);
    await page.getByLabel(t(locale, 'ui.m1.field.scenario')).selectOption(a.m1.scenario);
    await page.getByLabel(t(locale, 'ui.m1.field.product')).selectOption(a.m1.product);
    await page.getByRole('button', { name: t(locale, 'ui.m1.next'), exact: true }).click();
    for (const field of ['source', 'destination', 'processing', 'storage'] as const) await page.getByLabel(t(locale, `ui.m1.field.${field}`)).selectOption(a.m1.jurisdiction);
    await page.getByLabel(t(locale, 'ui.m1.field.items')).selectOption(a.m1.item);
    await page.getByLabel(t(locale, 'ui.m1.field.purpose')).fill('Synthetic business purpose');
    await page.getByRole('button', { name: t(locale, 'ui.m1.addFlow') }).click();
    await page.getByLabel(t(locale, 'ui.m1.flow.data_item_id')).selectOption(a.m1.item);
    for (const field of ['source_location', 'destination_location'] as const) await page.getByLabel(t(locale, `ui.m1.flow.${field}`)).selectOption(a.m1.jurisdiction);
    await page.getByRole('button', { name: t(locale, 'ui.m1.next'), exact: true }).click();
    await expect(page.getByRole('button', { name: t(locale, 'ui.m1.upload') })).toBeDisabled();
    await page.getByLabel(t(locale, 'ui.m1.field.description')).fill('Untrusted synthetic document description');
    await page.getByRole('button', { name: t(locale, 'ui.m1.next'), exact: true }).click();
    await page.getByRole('checkbox', { name: t(locale, 'ui.m1.confirmFacts') }).check();
    await expect(page.getByRole('button', { name: t(locale, 'ui.m1.execute') })).toBeDisabled();
    await load(page, a, locale);
    await expect(page.getByText(a.m1.classification, { exact: true })).toBeVisible();
    await expect(page.getByText(new RegExp(` · ${a.m1.status}$`))).toBeVisible();
    await page.getByRole('button', { name: "act", exact: true }).first().click();
    await expect(page.getByText(a.m1.official_text, { exact: true })).toBeVisible();
    await expect(page.getByText(t(locale, 'ui.m1.sourceLanguage'), { exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
    await page.screenshot({ path: `test-results/m1-${locale}.png`, fullPage: true });
    const next: Locale = locale === 'en-US' ? 'zh-HK' : 'en-US';
    await page.getByRole('combobox', { name: t(locale, 'ui.language') }).click();
    await page.getByTitle(t(locale, next === 'en-US' ? 'ui.localeEN' : 'ui.localeHK'), { exact: true }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', next);
    await expect(page.getByText(a.m1.applicability, { exact: true })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: t(next, 'ui.m1.confirmFacts') })).toBeChecked();
    expect(writes).toEqual([]);
    await page.screenshot({ path: `test-results/m1-${locale}-switched-${next}.png`, fullPage: true });
    for (const [resource, key] of [['classifications', 'classification'], ['regulation-applicability', 'applicability'], ['retrieval-runs', 'retrieval']] as const) {
      const deniedB = await page.request.get(`/api/v1/${resource}/${manifest!.B.m1[key]}`);
      expect([403, 404]).toContain(deniedB.status());
    }
    // Identity/context change must purge old intake facts, result references and rendered evidence.
    await login(page, 'B', next);
    await expect(page.getByText(a.m1.applicability, { exact: true })).toHaveCount(0);
    await expect(page.getByLabel(t(next, 'ui.m1.ref.classification'))).toHaveValue('');
    const denied = await page.request.get(`/api/v1/classifications/${a.m1.classification}`);
    expect([403, 404]).toContain(denied.status());
    expect(await denied.text()).not.toContain(a.m1.official_text);
    await load(page, manifest!.B, next);
    await expect(page.getByText(new RegExp(` · ${manifest!.B.m1.status}$`))).toBeVisible();
    await expect(page.getByText(t(next, 'ui.m1.reviewRequired'), { exact: true })).toBeVisible();
    expect(manifest!.B.m1.status).toBe('INSUFFICIENT_EVIDENCE');
    await page.setViewportSize({ width: 700, height: 1000 });
    await expect(page.getByRole('button', { name: t(next, 'ui.m1.loadResults') })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(writes).toEqual([]);
  });
});
