import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import fs from 'node:fs';
import zhCN from '../src/locales/zh-CN.json' with { type: 'json' };
import zhHK from '../src/locales/zh-HK.json' with { type: 'json' };
import enUS from '../src/locales/en-US.json' with { type: 'json' };
const catalogs = { 'zh-CN': zhCN, 'zh-HK': zhHK, 'en-US': enUS };
const manifest = JSON.parse(fs.readFileSync(process.env.M2A_UAT_MANIFEST!, 'utf8'));
// Credential-entry requests must never become Playwright traces/screenshots.
test.use({ trace: 'off', screenshot: 'off', actionTimeout: 15000 });
async function identity(request: APIRequestContext, persona: string) {
  expect((await request.post('/m0-demo/login', { data: { persona } })).status()).toBe(200);
}
async function clean(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.locator('body').innerText()).not.toContain('ui.phase1kb.');
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain('ci-local-credential');
}
for (const [locale, m] of Object.entries(catalogs)) {
  test(`governed admin providers, write-only secret and real HTTP tests ${locale}`, async ({ page, playwright }) => {
    test.setTimeout(120000);
    const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
    page.on('console', e => { if (e.type() === 'error') errors.push(e.text()); });
    page.on('response', r => { if (r.status() >= 400) errors.push(`HTTP ${r.status()} ${new URL(r.url()).pathname}`); });
    await page.addInitScript(x => localStorage.setItem('stage1-alpha.ui-locale', x), locale);
    await identity(page.request, 'LLM_ADMIN'); await page.goto('/admin');
    await page.getByRole('button', { name: m['ui.phase1kb.providers'], exact: true }).click();
    const form = page.locator('.admin-content form').first();
    await form.getByLabel(m['ui.phase1kb.code']).fill(`browser-${locale}-${Date.now()}`);
    const providerName = `Browser Provider ${locale} ${Date.now()}`;
    await form.getByLabel(m['ui.phase1kb.displayName']).fill(providerName);
    await form.getByLabel(m['ui.phase1kb.endpoint']).fill(manifest.LLM_ADMIN.endpoint);
    await form.getByLabel(m['ui.phase1kb.credential']).fill('ci-local-credential');
    await form.getByLabel(m['ui.phase1kb.deployment']).click();
    await page.getByTitle('PRIVATE_CLOUD', { exact: true }).click();
    await form.getByLabel(m['ui.phase1kb.trust']).fill('APPROVED');
    await form.getByLabel(m['ui.phase1kb.boundary']).fill('TENANT');
    const saved = page.waitForResponse(r => r.url().endsWith('/admin/model-providers') && r.request().method() === 'POST');
    await form.getByRole('button', { name: m['ui.phase1kb.saveProvider'], exact: true }).click();
    const response = await saved; expect(response.status()).toBe(201); const provider = await response.json();
    expect(JSON.stringify(provider)).not.toContain('ci-local-credential'); expect(provider.secret_configured).toBe(true);
    await expect(form.getByLabel(m['ui.phase1kb.credential'])).toHaveValue('');
    const row = page.getByRole('row').filter({ hasText: providerName });
    await row.getByRole('button', { name: m['ui.phase1kb.testConnection'], exact: true }).click();
    await expect(page.locator('.admin-content').getByRole('alert')).toContainText(m['ui.phase1kb.health.HEALTHY']);
    await row.getByRole('button', { name: m['ui.phase1kb.discover'], exact: true }).click();
    await row.getByRole('button', { name: m['ui.phase1kb.submit'], exact: true }).click();
    const reviewer = await playwright.request.newContext({ baseURL: process.env.M0_FRONTEND_URL ?? 'http://127.0.0.1:5173' });
    await identity(reviewer, 'LLM_REVIEWER');
    const list = await (await page.request.get('/api/v1/admin/model-providers')).json();
    const version = list.providers.find((p: { provider_id: string }) => p.provider_id === provider.provider_id).versions[0];
    expect((await reviewer.post(`/api/v1/admin/model-providers/versions/${version.provider_version_id}/transition`, { data: { target_status: 'APPROVED', expected_record_version: version.record_version } })).status()).toBe(200);
    await page.reload(); await page.getByRole('button', { name: m['ui.phase1kb.providers'], exact: true }).click();
    await row.getByRole('button', { name: m['ui.phase1kb.publish'], exact: true }).click();
    await row.getByRole('button', { name: m['ui.phase1kb.discover'], exact: true }).click();
    const modelForm = page.locator('.admin-content form').nth(1);
    await modelForm.getByLabel(m['ui.phase1kb.providerVersion']).click();
    await page.getByTitle(m['ui.phase1kb.version'].replace('{{version}}', '1'), { exact: true }).click();
    await modelForm.getByLabel(m['ui.phase1kb.displayName']).fill(`Browser Model ${locale}`);
    await modelForm.getByLabel(m['ui.phase1kb.remoteModel']).fill('A1');
    const modelSaved = page.waitForResponse(r => r.url().endsWith(`/${provider.provider_id}/models`) && r.request().method() === 'POST');
    await modelForm.getByRole('button', { name: m['ui.phase1kb.saveModel'], exact: true }).click();
    expect((await modelSaved).status()).toBe(201);
    const modelRow = page.getByRole('row').filter({ hasText: `Browser Model ${locale}` });
    await modelRow.getByRole('button', { name: m['ui.phase1kb.submit'], exact: true }).click();
    const models = await (await page.request.get(`/api/v1/admin/model-providers/${provider.provider_id}/models`)).json();
    const model = models.models[0];
    expect((await reviewer.post(`/api/v1/admin/model-providers/models/deployments/${model.deployment_id}/transition`, { data: { target_status: 'APPROVED', expected_record_version: model.record_version } })).status()).toBe(200);
    await page.reload(); await page.getByRole('button', { name: m['ui.phase1kb.providers'], exact: true }).click();
    await row.getByRole('button', { name: m['ui.phase1kb.models'], exact: true }).click();
    await modelRow.getByRole('button', { name: m['ui.phase1kb.publish'], exact: true }).click();
    await modelRow.getByRole('button', { name: `${m['ui.phase1kb.testModel']} chat`, exact: true }).click();
    await expect(page.locator('.admin-content').getByRole('alert')).toContainText(m['ui.phase1kb.health.HEALTHY']);
    await page.reload(); await page.getByRole('button', { name: m['ui.phase1kb.providers'], exact: true }).click();
    await expect(row).toContainText(m['ui.phase1kb.configured']);
    await clean(page); expect(errors).toEqual([]); await reviewer.dispose();
  });
  test(`authorized eligible selection, genuine document extraction and exact workflow ${locale}`, async ({ page, playwright }) => {
    test.setTimeout(150000);
    const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
    page.on('console', e => { if (e.type() === 'error') errors.push(e.text()); });
    await page.addInitScript(x => localStorage.setItem('stage1-alpha.ui-locale', x), locale);
    expect(manifest.LLM_USER.permissions).not.toContain('metadata:admin');
    expect(manifest.LLM_USER.permissions).not.toContain('metadata:publish');
    await identity(page.request, 'LLM_USER');
    expect((await page.request.get('/api/v1/admin/model-providers')).status()).toBe(404);
    await page.goto('/intake');
    await page.getByLabel(m['ui.m2a.projectName']).fill(`Governed LLM ${locale} ${Date.now()}`);
    await page.getByRole('button', { name: m['ui.m2a.create'], exact: true }).click();
    const project = await page.getByTestId('intake-project-id').innerText();
    const contexts = await Promise.all(['LLM_ADMIN', 'LLM_REVIEWER'].map(async persona => {
      const c = await playwright.request.newContext({ baseURL: process.env.M0_FRONTEND_URL ?? 'http://127.0.0.1:5173' }); await identity(c, persona); return c;
    }));
    // Independent governed PROJECT policy provisioning, never browser authorization.
    let policy = await (await contexts[0].post('/api/v1/admin/model-usage-policies', { data: {
      code: `project-${Date.now()}`, display_name: 'Governed project model policy',
      payload: { ...manifest.LLM_USER.project_policy_payload, project_id: project },
    } })).json();
    for (const [action, actor] of [['submit-review', 0], ['approve', 1], ['publish', 0]] as const) {
      const response = await contexts[actor].post(`/api/v1/admin/model-usage-policies/${policy.version_id}/${action}`, { data: { expected_record_version: policy.record_version } });
      expect(response.status()).toBe(200); policy = await response.json();
    }
    const v = manifest.LLM_USER.intake; const next = () => page.getByRole('button', { name: m['ui.m1.next'], exact: true }).click();
    await page.getByLabel(m['ui.m1.field.scenario']).selectOption(v.business_scenario);
    await page.getByLabel(m['ui.m1.field.product']).selectOption(v.selected_products[0]); await next();
    for (const field of ['source', 'destination'] as const) await page.getByLabel(m[`ui.m1.field.${field}`]).selectOption(v.source_locations[0]);
    await page.getByLabel(m['ui.m1.field.purpose']).fill(v.business_purpose);
    await page.getByLabel(m['ui.m1.field.dataVolume']).fill('3'); await next();
    await page.getByLabel(m['ui.m1.field.description']).fill('Governed typed intake with an unstructured requirement document.');
    const selection = page.getByLabel(m['ui.phase1kb.selectionMode'], { exact: true });
    await expect(selection).toHaveValue('AUTO');
    await selection.selectOption('SINGLE');
    const eligible = page.getByLabel(m['ui.phase1kb.eligibleModels']); await eligible.selectOption(manifest.LLM_USER.models[0]);
    await eligible.selectOption(manifest.LLM_USER.models[2]);
    await selection.selectOption('MULTI_MODEL'); await eligible.selectOption([manifest.LLM_USER.models[0], manifest.LLM_USER.models[2]]);
    const mode = locale === 'zh-CN' ? 'AUTO' : locale === 'zh-HK' ? 'SINGLE' : 'MULTI_MODEL';
    await selection.selectOption(mode);
    if (mode === 'SINGLE') await eligible.selectOption(manifest.LLM_USER.models[2]);
    if (mode === 'MULTI_MODEL') await eligible.selectOption([manifest.LLM_USER.models[0], manifest.LLM_USER.models[2]]);
    await page.getByRole('button', { name: m['ui.m2a.save'], exact: true }).click();
    await expect(page.getByLabel(m['ui.m1.field.scenario'])).toBeVisible(); await page.reload(); await next(); await next();
    await expect(selection).toHaveValue(mode);
    await page.getByLabel(m['ui.m2b.select']).setInputFiles({ name: 'semantic-requirement.txt', mimeType: 'text/plain', buffer: Buffer.from(`The unstructured requirement for project ${project} asks for analysis of business processing and governed evidence.`) });
    const uploaded = page.waitForResponse(r => r.url().includes('/intake/documents') && r.request().method() === 'POST');
    await page.getByRole('button', { name: m['ui.m2b.upload'], exact: true }).click();
    const uploadResponse = await uploaded; expect(uploadResponse.status(), await uploadResponse.text()).toBe(201);
    await expect(page.getByTestId('document-input')).toContainText('semantic-requirement.txt');
    await page.getByRole('button', { name: m['ui.m2b.parse'], exact: true }).click();
    await expect(page.getByTestId('document-input')).toContainText(m['ui.m2b.parsed']);
    await next(); await page.getByRole('checkbox', { name: m['ui.m1.confirmFacts'] }).check();
    await page.getByRole('button', { name: m['ui.m2a.confirmStart'], exact: true }).click();
    await expect(page.getByTestId('workflow-run-id')).toBeVisible({ timeout: 90000 });
    const run = await page.getByTestId('workflow-run-id').innerText();
    const confirmed = await (await page.request.get(`/api/v1/projects/${project}/intake`)).json();
    const view = await (await page.request.get(`/api/v1/workflows/${run}`)).json();
    expect(confirmed.intake.ai_model_preference.selection_mode).toBe(mode);
    expect(view.status).toBe('COMPLETED'); expect(view.project_id).toBe(project); expect(view.analysis_snapshot_id).toBe(confirmed.analysis_snapshot_id);
    expect(view.result_refs.applicability).toHaveLength(1);
    await clean(page); expect(errors).toEqual([]); await Promise.all(contexts.map(c => c.dispose()));
  });
}
