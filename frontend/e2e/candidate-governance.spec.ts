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
for (const [locale, action] of [['zh-CN', 'ACCEPT'], ['zh-HK', 'ACCEPT'], ['en-US', 'ACCEPT'], ['en-US', 'REJECT'], ['en-US', 'EDIT']] as const) {
  const m = catalogs[locale];
  test(`pre-confirm genuine DOCX ${action} and exact input freeze ${locale}`, async ({ page, playwright }) => {
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
    await page.getByLabel(m['ui.m2b.select']).setInputFiles({ name: 'candidate-governance.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: fs.readFileSync(new URL('./fixtures/candidate-governance.docx', import.meta.url)) });
    const uploaded = page.waitForResponse(r => r.url().includes('/intake/documents') && r.request().method() === 'POST');
    await page.getByRole('button', { name: m['ui.m2b.upload'], exact: true }).click();
    const uploadResponse = await uploaded; expect(uploadResponse.status(), await uploadResponse.text()).toBe(201);
    await expect(page.getByTestId('document-input')).toContainText('candidate-governance.docx');
    await page.getByRole('button', { name: m['ui.m2b.parse'], exact: true }).click();
    await expect(page.getByTestId('document-input')).toContainText(m['ui.m2b.parsed']);
    await next();
    const preparing = page.waitForResponse(r => r.url().endsWith('/candidate-preparation') && r.request().method() === 'POST');
    await page.getByRole('button', { name: m['ui.candidates.prepare'], exact: true }).click();
    expect((await preparing).status()).toBe(200);
    await expect(page.getByTestId('candidate-review-item').first()).toContainText(m['ui.candidates.aiDerived']);
    const before = await (await page.request.get(`/api/v1/projects/${project}/intake`)).json();
    expect(before.status).toBe('DRAFT'); expect(before.analysis_snapshot_id).toBeNull();
    const unreviewed = await page.request.post(`/api/v1/projects/${project}/intake/confirm`, { data: { expected_version: before.version } });
    expect(unreviewed.status()).toBe(409); expect((await unreviewed.json()).detail).toBe('CANDIDATE_CONFIRMATION_REQUIRED');
    const candidates = page.getByTestId('candidate-review-item');
    await candidates.first().locator('summary').click();
    await expect(candidates.first().locator('blockquote')).toContainText('R11_BROWSER_SOURCE_MARKER');
    for (const item of await candidates.all()) {
      await item.getByRole('combobox').selectOption(action);
      if (action === 'EDIT') await item.getByLabel(m['ui.candidates.editedValue']).fill('Explicitly corrected browser note');
    }
    const deciding = page.waitForResponse(r => r.url().endsWith('/candidate-decisions') && r.request().method() === 'POST');
    await page.getByRole('button', { name: m['ui.candidates.submit'], exact: true }).click();
    const decision = await deciding; expect(decision.status()).toBe(200);
    const receipt = await decision.json(); expect(receipt.submitted_by).not.toBe('browser-spoof');
    const preview = await (await page.request.get(`/api/v1/projects/${project}/candidate-preview`)).json();
    expect(preview.candidates.every((c: { decision_status: string }) => c.decision_status === action)).toBe(true);
    await page.reload();
    await next(); await next(); await next();
    await expect(page.getByTestId('candidate-review-item').first()).toBeVisible();
    await page.getByRole('checkbox', { name: m['ui.m1.confirmFacts'] }).check();
    await page.getByRole('button', { name: m['ui.m2a.confirmStart'], exact: true }).click();
    await expect(page.getByTestId('workflow-run-id')).toBeVisible({ timeout: 90000 });
    const run = await page.getByTestId('workflow-run-id').innerText();
    const confirmed = await (await page.request.get(`/api/v1/projects/${project}/intake`)).json();
    const view = await (await page.request.get(`/api/v1/workflows/${run}`)).json();
    expect(confirmed.intake.ai_model_preference.selection_mode).toBe(mode);
    expect(view.status).toBe('COMPLETED'); expect(view.project_id).toBe(project); expect(view.analysis_snapshot_id).toBe(confirmed.analysis_snapshot_id);
    expect(view.result_refs.applicability).toHaveLength(1);
    expect(confirmed.intake.uploaded_documents).toHaveLength(1);
    await page.reload();
    const reloaded = await (await page.request.get(`/api/v1/projects/${project}/intake`)).json();
    expect(reloaded.analysis_snapshot_id).toBe(confirmed.analysis_snapshot_id);
    await clean(page); expect(errors).toEqual([]); await Promise.all(contexts.map(c => c.dispose()));
  });
}
