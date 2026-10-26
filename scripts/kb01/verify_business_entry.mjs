/** Measured entry/auth/draft smoke only. Never certifies a real-law/model journey. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium, expect } = require('@playwright/test');
const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, all) =>
  index % 2 ? pairs : [...pairs, [value, all[index + 1]]], []));
const file = args['--credentials'];
const output = args['--output'];
if (!file || !output || (fs.statSync(file).mode & 0o077)) throw new Error('PRIVATE_CREDENTIAL_FILE_AND_OUTPUT_REQUIRED');
const credentials = JSON.parse(fs.readFileSync(file, 'utf8'));
const browser = await chromium.launch({ headless: true,
  ...(process.env.M0_CHROMIUM_PATH ? { executablePath: process.env.M0_CHROMIUM_PATH, args: ['--no-sandbox'] } : {}) });
const results = [];
const businessLogins = [];
let authPacingMilliseconds = 0;
let phase = 'start';
let safeDiagnostics = {};
try {
  for (const locale of ['zh-CN', 'zh-HK', 'en-US']) {
    const started = Date.now();
    const labels = JSON.parse(fs.readFileSync(path.join(root, 'frontend/src/locales', locale + '.json'), 'utf8'));
    // Ant Design inserts display spacing into two-character CJK buttons.
    // Match the same complete translated label, permitting only whitespace.
    const signOutLabel = new RegExp('^' + [...labels.signOut].map(character =>
      character.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s*') + '$');
    if (businessLogins.length >= 4) {
      const wait = 60_100 - (Date.now() - businessLogins[0]);
      if (wait > 0) { authPacingMilliseconds += wait; await new Promise(resolve => setTimeout(resolve, wait)); }
    }
    const context = await browser.newContext();
    const page = await context.newPage();
    page.setDefaultTimeout(30_000);
    const errors = [];
    const serverErrors = [];
    const expectedPolicyUnavailable = [];
    const responseChecks = [];
    const consoleErrors = [];
    const expectedHttpErrors = new Set();
    safeDiagnostics = { js_errors: errors, server_errors: serverErrors, console_errors: consoleErrors };
    page.on('pageerror', () => errors.push('UNCAUGHT_JS_ERROR'));
    page.on('console', message => {
      if (message.type() !== 'error') return;
      const match = /^Failed to load resource: the server responded with a status of (\d+)/.exec(message.text());
      let resource = '';
      try { resource = new URL(message.location().url).pathname; } catch { /* no URL */ }
      consoleErrors.push({ http_status: match ? Number(match[1]) : null, path: resource });
    });
    page.on('response', response => {
      const resource = new URL(response.url()).pathname;
      if (response.status() === 401 && resource === '/api/v1/session') expectedHttpErrors.add(`401:${resource}`);
    });
    page.on('response', response => { if (response.status() >= 500) responseChecks.push((async () => {
      const url = new URL(response.url()).pathname;
      if (url.endsWith('/upload-policy') && response.status() === 503) {
        const body = await response.json();
        if (body?.detail?.code === 'KNOWLEDGE_MANAGEMENT_POLICY_NOT_CONFIGURED_OR_AMBIGUOUS') {
          expectedPolicyUnavailable.push(url); expectedHttpErrors.add(`503:${url}`); return;
        }
      }
      serverErrors.push({ path: url, status: response.status() });
    })()); });
    await page.addInitScript(value => localStorage.setItem('stage1-alpha.ui-locale', value), locale);
    phase = 'business-login-' + locale;
    await page.goto('http://127.0.0.1:15174/intake');
    await page.getByLabel(labels['ui.acceptance.username'], { exact: true }).fill(credentials['business-user'].username);
    await page.getByLabel(labels['ui.acceptance.password'], { exact: true }).fill(credentials['business-user'].password);
    await page.getByRole('button', { name: labels['ui.acceptance.signIn'], exact: true }).click();
    await expect(page.getByText(labels['ui.acceptance.prerequisites'], { exact: true })).toBeVisible();
    businessLogins.push(Date.now());
    phase = 'blank-project-' + locale;
    await page.getByLabel(labels['ui.m2a.projectName'], { exact: true }).fill('Non-sensitive business entry ' + locale + ' ' + Date.now());
    await page.getByRole('button', { name: labels['ui.m2a.create'], exact: true }).click();
    const id = page.getByTestId('intake-project-id');
    await expect(id).toBeVisible();
    const projectId = await id.innerText();
    const projectUrl = page.url();
    await page.reload();
    await expect(id).toHaveText(projectId);
    const denied = await context.request.get('http://127.0.0.1:15174/api/v1/admin/model-providers');
    expect([403, 404]).toContain(denied.status());
    const readiness = await context.request.get('http://127.0.0.1:15174/api/v1/acceptance-readiness');
    expect(readiness.status()).toBe(200);
    const observed = await readiness.json();
    expect(observed.model_configuration.providers).toBe(0);
    expect(observed.live_model_workflow).not.toBe('VERIFIED');
    expect(observed.native_processing.status).toBe('BLOCKED');
    // Exercise the real UI identity boundary: it cancels in-flight queries
    // before deleting the cookie. Direct test-side logout races active reads.
    await page.getByRole('button', { name: signOutLabel }).click();
    await expect(page.getByLabel(labels['ui.acceptance.username'], { exact: true })).toBeVisible();
    await page.goto(projectUrl);
    await page.getByLabel(labels['ui.acceptance.username'], { exact: true }).fill(credentials['business-user'].username);
    await page.getByLabel(labels['ui.acceptance.password'], { exact: true }).fill(credentials['business-user'].password);
    await page.getByRole('button', { name: labels['ui.acceptance.signIn'], exact: true }).click();
    await expect(page.getByTestId('intake-project-id')).toHaveText(projectId);
    businessLogins.push(Date.now());
    phase = 'operator-login-' + locale;
    await page.getByRole('button', { name: signOutLabel }).click();
    await expect(page.getByLabel(labels['ui.acceptance.username'], { exact: true })).toBeVisible();
    await page.goto('http://127.0.0.1:15174/admin?admin_resource=models');
    await page.getByLabel(labels['ui.acceptance.username'], { exact: true }).fill(credentials['knowledge-operator'].username);
    await page.getByLabel(labels['ui.acceptance.password'], { exact: true }).fill(credentials['knowledge-operator'].password);
    await page.getByRole('button', { name: labels['ui.acceptance.signIn'], exact: true }).click();
    await expect(page.getByText(labels['ui.phase1kb.createProvider'], { exact: true })).toBeVisible();
    const policyResponse = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/upload-policy'), { timeout: 30_000 });
    await page.goto('http://127.0.0.1:15174/admin?admin_resource=knowledge-management');
    await expect(page.getByRole('heading', { name: labels['ui.kb01.workspace'], exact: true })).toBeVisible();
    const policy = await policyResponse;
    expect(policy.status()).toBe(503);
    expect((await policy.json()).detail.code).toBe('KNOWLEDGE_MANAGEMENT_POLICY_NOT_CONFIGURED_OR_AMBIGUOUS');
    await page.getByRole('tab', { name: labels['ui.kb01.uploads'], exact: true }).click();
    await expect(page.getByLabel(labels['ui.kb01.files'], { exact: true })).toBeVisible();
    await page.goto('http://127.0.0.1:15174/admin?admin_resource=regulatory-acceptance');
    await expect(page.getByText(labels['ui.acceptance.expertRecords'], { exact: true }).last()).toBeVisible();
    expect(errors).toEqual([]);
    // Missing governance policy is an explicit prerequisite, not fabricated acceptance.
    await Promise.all(responseChecks);
    expect(serverErrors).toEqual([]);
    expect(consoleErrors.filter(error => !expectedHttpErrors.has(`${error.http_status}:${error.path}`))).toEqual([]);
    results.push({ locale, project_id: projectId, project_url: projectUrl, login: 'PASS',
      blank_project: 'PASS', reload_relogin_same_project: 'PASS', unauthorized_model_admin: 'DENIED',
      provider_interface: 'VISIBLE', regulation_interface: 'FILE_INPUT_VISIBLE_UPLOAD_HELD_BY_MISSING_GOVERNED_POLICY', expert_records_interface: 'VISIBLE',
      native_processing: observed.native_processing, live_model_workflow: 'BLOCKED_NO_API_PROVIDER',
      legal_accuracy_execution: 'NOT_EXECUTED', retries: 0, js_errors: errors,
      unexpected_console_errors: 0, elapsed_ms: Date.now() - started,
      expected_missing_policy_503: expectedPolicyUnavailable.length });
    await context.close();
  }
  fs.writeFileSync(output, JSON.stringify({ source_sha: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    source_dirty: !!execFileSync('git', ['status', '--porcelain=v1'], { cwd: root, encoding: 'utf8' }).trim(),
    decision: 'ENTRY_AUTH_DRAFT_SMOKE_PASS_NOT_BUSINESS_OR_LEGAL_E2E', cases: results,
    passed: results.length, retries: 0, auth_pacing_ms: authPacingMilliseconds, pacing_reason: 'Respect5loginsPerMinute; no assertion retry', no_trace_or_credentials_archived: true }, null, 2));
  console.log('Three-locale entry smoke PASS; no live-model or legal-accuracy PASS asserted.');
} catch (failure) {
  safeDiagnostics.failure_type = failure.name;
  safeDiagnostics.failure_location = failure.stack?.match(/verify_business_entry.mjs:\d+:\d+/)?.[0];
  // Browser assertion messages may contain login inputs: never serialize them.
  fs.writeFileSync(output, JSON.stringify({ decision: 'FAILED', phase, completed_cases: results.length,
    diagnostics: safeDiagnostics,
    credential_values_omitted: true, retries: 0 }, null, 2));
  console.error('ENTRY_SMOKE_FAILED at safe phase: ' + phase);
  process.exitCode = 1;
} finally { await browser.close(); }
