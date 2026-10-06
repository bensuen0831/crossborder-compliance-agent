import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import zhCN from '../src/locales/zh-CN.json' with { type: 'json' };
import zhHK from '../src/locales/zh-HK.json' with { type: 'json' };
import enUS from '../src/locales/en-US.json' with { type: 'json' };
const catalogs = { 'zh-CN': zhCN, 'zh-HK': zhHK, 'en-US': enUS };
type Locale = keyof typeof catalogs;
type Persona = { contexts: { project_id: string; display_name: string; analysis_snapshot_id: string }[]; m1: { scenario: string; product: string; jurisdiction: string; item: string; classification: string; applicability: string; retrieval: string; status: string; official_text: string } };
const path = process.env.M1_UAT_MANIFEST;
const manifest: Record<'A' | 'B' | 'C' | 'D', Persona> | undefined = path ? JSON.parse(fs.readFileSync(path, 'utf8')) : undefined;
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
async function intake(page: Page, persona: Persona, locale: Locale) {
    await page.getByLabel(t(locale, 'ui.m1.field.scenario')).selectOption(persona.m1.scenario);
    await page.getByLabel(t(locale, 'ui.m1.field.product')).selectOption(persona.m1.product);
    await page.getByRole('button', { name: t(locale, 'ui.m1.next'), exact: true }).click();
    for (const field of ['source', 'destination', 'processing', 'storage'] as const) await page.getByLabel(t(locale, `ui.m1.field.${field}`)).selectOption(persona.m1.jurisdiction);
    await page.getByLabel(t(locale, 'ui.m1.field.items')).selectOption(persona.m1.item);
    await page.getByLabel(t(locale, 'ui.m1.field.purpose')).fill('Synthetic business purpose');
    await page.getByRole('button', { name: t(locale, 'ui.m1.addFlow') }).click();
    await page.getByLabel(t(locale, 'ui.m1.flow.data_item_id')).selectOption(persona.m1.item);
    for (const field of ['source_location', 'destination_location'] as const) await page.getByLabel(t(locale, `ui.m1.flow.${field}`)).selectOption(persona.m1.jurisdiction);
    await page.getByRole('button', { name: t(locale, 'ui.m1.next'), exact: true }).click();
    await expect(page.getByRole('button', { name: t(locale, 'ui.m1.upload') })).toBeDisabled();
    await page.getByLabel(t(locale, 'ui.m1.field.description')).fill('Untrusted synthetic document description');
    await page.getByRole('button', { name: t(locale, 'ui.m1.next'), exact: true }).click();
    await page.getByRole('checkbox', { name: t(locale, 'ui.m1.confirmFacts') }).check();
}

// Old M0 CI selects knowledge.spec.ts explicitly; this suite requires real M1 fixtures.
for (const locale of Object.keys(catalogs) as Locale[]) test.describe(locale, () => {
  test.beforeEach(async ({ page }) => { await page.addInitScript(value => { if (!localStorage.getItem('stage1-alpha.ui-locale')) localStorage.setItem('stage1-alpha.ui-locale', value); }, locale); });
  test('four-step intake, canonical results, official citation and locale state invariance', async ({ page }) => {
    test.setTimeout(120000);
    expect(manifest, 'M1_UAT_MANIFEST must point to seeded real-backend fixtures').toBeDefined();
    const a = manifest!.A; const writes: string[] = [];
    page.on('request', request => { if (request.method() !== 'GET' && new URL(request.url()).pathname.startsWith('/api/v1/')) writes.push(request.url()); });
    await page.goto('/'); await login(page, 'A', locale);
    await intake(page, a, locale);
    await expect(page.getByRole('button', { name: t(locale, 'ui.m1.execute') })).toBeEnabled();
    await page.getByRole('button', { name: t(locale, 'ui.m1.execute') }).click();
    const run = await page.getByTestId('workflow-run-id').innerText();
    const started = await page.request.get(`/api/v1/workflows/${run}`);
    expect(started.status()).toBe(200);
    const result = await started.json();
    expect(result.status).toBe('COMPLETED');
    expect(result.analysis_snapshot_id).toBe(a.contexts[0].analysis_snapshot_id);
    const applicabilityId = result.result_refs.applicability[0];
    const authoritative = await (await page.request.get(`/api/v1/regulation-applicability/${applicabilityId}`)).json();
    expect(authoritative.analysis_snapshot_id).toBe(a.contexts[0].analysis_snapshot_id);
    expect(authoritative.classification_result_ids).toContain(result.result_refs.classification[0]);
    await expect(page.getByText(applicabilityId, { exact: true })).toBeVisible();
    await expect(page.getByText(a.m1.classification, { exact: true })).toBeVisible();
    await expect(page.getByText(new RegExp(` · ${authoritative.applicability_status}$`))).toBeVisible();
    await page.getByRole('button', { name: "act", exact: true }).first().click();
    const retrieval = await (await page.request.get(`/api/v1/retrieval-runs/${result.result_refs.retrieval[0]}`)).json();
    const officialText = retrieval.rag_context_pack.evidence_pack.items.find((item: { canonical_locator: string }) => item.canonical_locator === 'act').original_text;
    await expect(page.getByText(officialText, { exact: true })).toBeVisible();
    await expect(page.getByText(t(locale, 'ui.m1.sourceLanguage'), { exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
    await page.screenshot({ path: `test-results/m1-${locale}.png`, fullPage: true });
    const next: Locale = locale === 'en-US' ? 'zh-HK' : 'en-US';
    await page.getByRole('combobox', { name: t(locale, 'ui.language') }).click();
    await page.getByTitle(t(locale, next === 'en-US' ? 'ui.localeEN' : 'ui.localeHK'), { exact: true }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', next);
    await expect(page.getByText(applicabilityId, { exact: true })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: t(next, 'ui.m1.confirmFacts') })).toBeChecked();
    await expect(page.getByTestId('workflow-run-id')).toHaveText(run);
    expect(await (await page.request.get(`/api/v1/workflows/${run}`)).json()).toEqual(result);
    expect(writes).toHaveLength(1);
    expect(new URL(writes[0]).pathname).toMatch(/\/snapshots\/[^/]+\/workflow$/);
    await page.screenshot({ path: `test-results/m1-${locale}-switched-${next}.png`, fullPage: true });
    for (const [resource, key] of [['classifications', 'classification'], ['regulation-applicability', 'applicability'], ['retrieval-runs', 'retrieval']] as const) {
      const deniedB = await page.request.get(`/api/v1/${resource}/${manifest!.B.m1[key]}`);
      expect([403, 404]).toContain(deniedB.status());
    }
    // Identity/context change must purge old intake facts, result references and rendered evidence.
    await login(page, 'B', next);
    await expect(page.getByText(applicabilityId, { exact: true })).toHaveCount(0);
    await expect(page.getByLabel(t(next, 'ui.m1.ref.classification'))).toHaveValue('');
    const denied = await page.request.get(`/api/v1/classifications/${a.m1.classification}`);
    expect([403, 404]).toContain(denied.status());
    expect(await denied.text()).not.toContain(a.m1.official_text);
    expect([403,404]).toContain((await page.request.get(`/api/v1/workflows/${run}`)).status());
    expect((await page.request.get('/api/v1/workflows/11111111-1111-4111-8111-111111111111')).status()).toBe(404);
    await intake(page, manifest!.B, next);
    await page.getByRole('button', { name: t(next, 'ui.m1.execute') }).click();
    const partialRun = await page.getByTestId('workflow-run-id').innerText();
    const partial = await (await page.request.get(`/api/v1/workflows/${partialRun}`)).json();
    expect(partial.status).toBe('WARNING');
    expect(partial.fallback_ref).toBeTruthy();
    expect(partial.result_refs.applicability).toBeUndefined();
    await expect(page.getByText(t(next, 'ui.m1.workflowWarning'), { exact: true })).toBeVisible();
    // Original independent authorized-result presentation remains regression-covered.
    await page.reload();
    await page.getByRole('combobox', { name: t(next, 'project') }).click();
    await page.getByRole('combobox', { name: t(next, 'project') }).press('ArrowDown');
    await page.getByRole('combobox', { name: t(next, 'project') }).press('Enter');
    await page.getByRole('link', { name: t(next, 'ui.m1.title'), exact: true }).click();
    await load(page, manifest!.B, next);
    await expect(page.getByText(new RegExp(` · ${manifest!.B.m1.status}$`))).toBeVisible();
    await expect(page.getByText(t(next, 'ui.m1.reviewRequired'), { exact: true })).toBeVisible();
    expect(manifest!.B.m1.status).toBe('INSUFFICIENT_EVIDENCE');
    await page.setViewportSize({ width: 700, height: 1000 });
    await expect(page.getByRole('button', { name: t(next, 'ui.m1.loadResults') })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(writes).toHaveLength(2);
    await page.setViewportSize({ width: 1500, height: 1000 });
    for (const label of ['C','D'] as const) {
      await page.request.post('/m0-demo/login', { data: { persona: label } });
      await page.goto('/');
      await expect(page.getByText(`UAT User ${label}`, { exact: true })).toBeVisible();
      const selector = page.getByRole('combobox', { name: t(next, 'project') });
      await selector.click(); await selector.press('ArrowDown'); await selector.press('Enter');
      await page.getByRole('link', { name: t(next, 'ui.m1.title'), exact: true }).click();
      await intake(page, manifest![label], next);
      await page.getByRole('button', { name: t(next, 'ui.m1.execute') }).click();
      const reviewRun = await page.getByTestId('workflow-run-id').innerText();
      const review = await (await page.request.get(`/api/v1/workflows/${reviewRun}`)).json();
      expect(review.status).toBe('REVIEW_REQUIRED'); expect(review.review_id).toBeTruthy();
      await expect(page.getByText(new RegExp(t(next, 'ui.m1.pendingReview')))).toBeVisible();
      expect(review.result_refs.applicability).toBeUndefined();
      if (label === 'D') {
        const canonical = await (await page.request.get(`/api/v1/projects/${manifest!.D.contexts[0].project_id}/context-resolution`)).json();
        expect(canonical.conflicts.length).toBeGreaterThan(0);
        await expect(page.getByText(t(next, 'ui.m1.conflicted'), { exact: true })).toBeVisible();
      }
    }
    expect(writes).toHaveLength(4);
    expect(writes.every(url => /\/snapshots\/[^/]+\/workflow$/.test(new URL(url).pathname))).toBe(true);
  });
});
