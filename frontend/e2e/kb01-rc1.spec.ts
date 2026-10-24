import { test, expect } from '@playwright/test';
import enUS from '../src/locales/en-US.json' with { type: 'json' };

test('KB01 RC1 synthetic author reviewer publisher and restricted roles remain distinct', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('stage1-alpha.ui-locale', 'en-US'));
  await page.goto('/admin?admin_resource=knowledge-management');
  await page.getByRole('button', { name: enUS.loginA, exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/m0-demo/session')).json()).permissions).toContain('knowledge:taxonomy:write');
  let session = await (await page.request.get('/m0-demo/session')).json();
  expect(session.permissions).toContain('knowledge:taxonomy:write');
  expect(session.permissions).not.toContain('knowledge:taxonomy:approve');
  expect(session.permissions).not.toContain('knowledge:taxonomy:publish');
  const firstIdentity = session.identity_key;
  await page.getByRole('button', { name: enUS.loginReviewer, exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/m0-demo/session')).json()).permissions).toContain('knowledge:taxonomy:approve');
  await expect(page.getByRole('button', { name: enUS.loginReviewer, exact: true })).toBeEnabled();
  session = await (await page.request.get('/m0-demo/session')).json();
  expect(session.identity_key).not.toBe(firstIdentity);
  expect(session.permissions).toContain('knowledge:taxonomy:approve');
  expect(session.permissions).not.toContain('knowledge:taxonomy:publish');
  const deniedCreate = await page.request.post('/api/v1/admin/knowledge-management/taxonomy', {
    data: { kind: 'REGULATION_CATEGORY', code: 'RC1-DENIED', display_name: 'Test only', payload: {}, idempotency_key: crypto.randomUUID() },
  });
  expect(deniedCreate.status()).toBe(403);
  await page.getByRole('button', { name: enUS.loginPublisher, exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/m0-demo/session')).json()).permissions).toContain('knowledge:taxonomy:publish');
  await expect(page.getByRole('button', { name: enUS.loginPublisher, exact: true })).toBeEnabled();
  session = await (await page.request.get('/m0-demo/session')).json();
  expect(session.permissions).toContain('knowledge:taxonomy:publish');
  expect(session.permissions).not.toContain('knowledge:taxonomy:approve');
  await page.getByRole('button', { name: enUS.loginRestricted, exact: true }).click();
  await expect.poll(async () => (await (await page.request.get('/m0-demo/session')).json()).permissions).toEqual([]);
  await expect(page.getByRole('button', { name: enUS.loginRestricted, exact: true })).toBeEnabled();
  session = await (await page.request.get('/m0-demo/session')).json();
  expect(session.permissions).toEqual([]);
  expect((await page.request.get('/api/v1/admin/knowledge-management/taxonomy')).status()).toBe(403);
});
