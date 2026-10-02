import { expect, test, type Page } from '@playwright/test';

async function signIn(page: Page, persona: 'A' | 'B') {
  await page.getByRole('button', { name: `登入 UAT 使用者 ${persona}` }).click();
  await expect(page.getByText(`UAT User ${persona}`, { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: '專案 / 已固定的分析版本' }).click();
  await page.getByTitle(`Generic Project · UAT ${persona}`, { exact: true }).click();
  await expect(page.getByRole('textbox', { name: '知識問題或關鍵字' })).toBeEnabled();
}

test('real knowledge search, canonical citation, sufficiency, fallback and runtime status', async ({ page }) => {
  await page.goto('/');
  await signIn(page, 'A');
  await page.getByRole('textbox', { name: '知識問題或關鍵字' }).fill('Generic');
  const result = page.waitForResponse((r) => r.url().includes('/knowledge/retrieve') && r.status() === 200);
  await page.getByRole('button', { name: '查詢知識', exact: true }).click();
  const actual = await (await result).json();
  expect(actual.rag_context_pack.evidence_pack.items.length).toBeGreaterThan(0);
  await expect(page.getByText('不足 · INSUFFICIENT')).toBeVisible();
  await expect(page.getByText('證據補足指引', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/knowledge-evidence.png', fullPage: true });
  await page.getByRole('button', { name: '來源與引用' }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText(actual.rag_context_pack.evidence_pack.items[0].citation_id, { exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: '運行狀態', exact: true }).click();
  await expect(page.getByText('READY', { exact: true })).toBeVisible();
});

test('identity switch purges evidence, isolates tenant B, and rejects A resource guessing server-side', async ({ page }) => {
  await page.goto('/'); await signIn(page, 'A');
  await page.getByRole('textbox', { name: '知識問題或關鍵字' }).fill('Generic');
  const response = page.waitForResponse((r) => r.url().includes('/knowledge/retrieve') && r.status() === 200);
  await page.getByRole('button', { name: '查詢知識', exact: true }).click();
  const a = await (await response).json();
  await expect(page.getByText('不足 · INSUFFICIENT')).toBeVisible();
  await signIn(page, 'B');
  await expect(page.getByRole('button', { name: '來源與引用' })).toHaveCount(0);
  const denied = await page.request.get(`/api/v1/retrieval-runs/${a.retrieval_run_id}`);
  expect(denied.status()).toBe(404);
  expect(await denied.text()).not.toContain(a.rag_context_pack.evidence_pack.items[0].original_text);
  await page.getByRole('textbox', { name: '知識問題或關鍵字' }).fill('Generic');
  const bResponse = page.waitForResponse((r) => r.url().includes('/knowledge/retrieve') && r.status() === 200);
  await page.getByRole('button', { name: '查詢知識', exact: true }).click();
  const b = await (await bResponse).json();
  expect(b.rag_context_pack.scope.tenant_id).not.toBe(a.rag_context_pack.scope.tenant_id);
  const aVersions = a.rag_context_pack.evidence_pack.items.map((item: { knowledge_version_id: string }) => item.knowledge_version_id);
  for (const item of b.rag_context_pack.evidence_pack.items) expect(aVersions).not.toContain(item.knowledge_version_id);
  await expect(page.getByText('不足 · INSUFFICIENT')).toBeVisible();
});

test('no-match query renders empty evidence and actionable backend guidance on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 1000 });
  await page.goto('/'); await signIn(page, 'A');
  await page.getByRole('textbox', { name: '知識問題或關鍵字' }).fill('zzznomatchtokenzzz');
  await page.getByRole('button', { name: '查詢知識', exact: true }).click();
  await expect(page.getByText('本次查詢沒有授權證據')).toBeVisible();
  await expect(page.getByText('證據補足指引', { exact: true })).toBeVisible();
  await expect(page.getByRole('progressbar')).toHaveCount(0);
});
