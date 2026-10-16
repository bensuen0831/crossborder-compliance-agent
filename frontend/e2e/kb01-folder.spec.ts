import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import en from "../src/locales/en-US.json" with { type: "json" };
import { safeBrowserError } from "./kb01-safe-evidence";

const prefix = "/api/v1/admin/knowledge-management";
const t = (key: keyof typeof en) => en[key];

test("KB01 real directory upload preserves duplicate basenames, native citations and exact originals without Excel", async ({ page }, info) => {
  test.setTimeout(180_000);
  const directory = info.outputPath("directory-input");
  const originals = new Map<string, string>();
  for (const country of ["source-a", "source-b"]) {
    const relative = `${country}/same.txt`;
    const filename = path.join(directory, relative);
    fs.mkdirSync(path.dirname(filename), { recursive: true });
    fs.writeFileSync(filename, `Article 1. SYNTHETIC_GOVERNED_TEST_DATA_FOLDER_${country}.\n`);
    originals.set(relative, filename);
  }
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(safeBrowserError(error.message)));
  page.on("console", (message) => { if (message.type() === "error") errors.push(safeBrowserError(message.text())); });
  page.on("response", (response) => { if (response.status() >= 500) errors.push(`HTTP_${response.status()}`); });
  await page.addInitScript(() => { if (["http:", "https:"].includes(location.protocol)) localStorage.setItem("stage1-alpha.ui-locale", "en-US"); });
  expect((await page.request.post("/m0-demo/login", { data: { persona: "A" } })).status()).toBe(200);
  await page.goto("/admin?admin_resource=knowledge-management");
  await expect(page.getByRole("heading", { name: t("ui.kb01.workspace"), exact: true })).toBeVisible();
  const workspace = page.url();
  await page.getByRole("tab", { name: t("ui.kb01.uploads"), exact: true }).click();
  const chooser = page.getByLabel(t("ui.kb01.folder"), { exact: true });
  await expect(chooser).toHaveAttribute("webkitdirectory", "");
  await chooser.setInputFiles(directory);
  await expect(page.getByText("directory-input/source-a/same.txt", { exact: false })).toBeVisible();
  await expect(page.getByText("directory-input/source-b/same.txt", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: t("ui.kb01.startResume"), exact: true }).click();
  const create = page.getByRole("button", { name: t("ui.kb01.createBatch"), exact: true });
  await expect(create).toBeEnabled({ timeout: 90_000 });
  const created = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === prefix + "/import-batches");
  await create.click();
  const batch = await (await created).json();
  const preview = await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)).json();
  expect(preview.items).toHaveLength(2);
  expect(new Set(preview.items.map((item: { relative_path: string }) => item.relative_path))).toEqual(new Set([...originals.keys()].map((value) => "directory-input/" + value)));
  expect((await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}/manifests`)).json()).total).toBe(0);
  const source = (await (await page.request.get(prefix + "/sources")).json()).items[0];
  await page.getByRole("combobox", { name: t("ui.kb01.sourceId"), exact: true }).selectOption(source.source_id);
  const collections = await (await page.request.get(`${prefix}/sources/${source.source_id}/collection-versions`)).json();
  await page.getByRole("combobox", { name: t("ui.kb01.collectionVersion"), exact: true }).selectOption(collections.items[0].collection_version_id);
  await page.locator("form").filter({ has: page.getByRole("heading", { name: t("ui.kb01.documentMetadata"), exact: true }) }).getByRole("textbox", { name: t("ui.kb01.language"), exact: true }).fill("en");
  const mapping = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith(`/import-batches/${batch.batch_id}/confirm-items`));
  await page.getByRole("button", { name: t("ui.kb01.confirmMapping"), exact: true }).click();
  expect((await mapping).status()).toBe(200);
  await expect.poll(async () => (await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)).json()).status, { timeout: 90_000, intervals: [1000] }).toBe("COMPLETED");
  const completed = await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)).json();
  expect(completed.counts).toEqual({ COMPLETED: 2 });
  for (const item of completed.items) {
    const relative = item.relative_path.replace(/^directory-input\//, "");
    expect(originals.has(relative)).toBe(true);
    const marker = `SYNTHETIC_GOVERNED_TEST_DATA_FOLDER_${relative.split("/")[0]}`;
    const parsed = await (await page.request.get(`${prefix}/documents/versions/${item.knowledge_version_id}/preview`)).json();
    expect(parsed.items.some((node: { original_excerpt: string; citation_id: string }) => node.original_excerpt.includes(marker) && Boolean(node.citation_id))).toBe(true);
    expect(item.manifest_record_id).toBeNull();
    const version = await (await page.request.get(`/api/v1/admin/knowledge-versions/${item.knowledge_version_id}`)).json();
    expect(version.lifecycle).toBe("INGESTED");
    await page.goto(workspace);
    await page.locator(`button[data-document-id="${version.document_id}"]`).click();
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("link", { name: t("ui.kb01.downloadOriginal") }).click();
    const download = await downloadEvent;
    const file = await download.path();
    expect(file).toBeTruthy();
    const hash = (filename: string) => crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex");
    expect(hash(file!)).toBe(hash(originals.get(relative)!));
    await download.delete();
  }
  // Independent canonical scope/review/publish precedes lifecycle commands.
  const jurisdiction = (await (await page.request.get(`${prefix}/scope-options?dimension=jurisdiction`)).json()).items[0].object_id;
  for (const item of completed.items) {
    const id = item.knowledge_version_id;
    const v = await (await page.request.get(`/api/v1/admin/knowledge-versions/${id}`)).json();
    const bound = await page.request.post(`${prefix}/documents/versions/${id}/scope-bindings`, { data: {
      expected_record_version: v.record_version, idempotency_key: crypto.randomUUID(), reason: "Synthetic explicit scope",
      scope_type: "GLOBAL", dimensions: { jurisdiction: [jurisdiction] },
    } });
    expect(bound.status()).toBe(201);
    for (const action of ["validate", "submit-review"]) {
      const exact = await (await page.request.get(`/api/v1/admin/knowledge-versions/${id}`)).json();
      expect((await page.request.post(`${prefix}/documents/versions/${id}/${action}`, { data: {
        expected_record_version: exact.record_version, idempotency_key: crypto.randomUUID(), reason: "Synthetic source quality and review",
      } })).status()).toBe(200);
    }
  }
  for (const [persona, action] of [["REVIEWER", "approve"], ["PUBLISHER", "publish"]]) {
    await page.goto("about:blank");
    expect((await page.request.post("/m0-demo/login", { data: { persona } })).status()).toBe(200);
    for (const item of completed.items) {
      const v = await (await page.request.get(`/api/v1/admin/knowledge-versions/${item.knowledge_version_id}`)).json();
      expect((await page.request.post(`${prefix}/documents/versions/${item.knowledge_version_id}/${action}`, { data: {
        expected_record_version: v.record_version, idempotency_key: crypto.randomUUID(), reason: "Synthetic independent authorization",
      } })).status()).toBe(200);
    }
  }
  await page.goto("about:blank");
  expect((await page.request.post("/m0-demo/login", { data: { persona: "A" } })).status()).toBe(200);
  await page.goto(workspace);
  for (const action of ["expire", "archive"]) {
    const bulk = page.getByRole("region", { name: t("ui.kb01.bulkActions"), exact: true });
    for (const item of completed.items) {
      const v = await (await page.request.get(`/api/v1/admin/knowledge-versions/${item.knowledge_version_id}`)).json();
      await bulk.locator(`input[data-bulk-document-id="${v.document_id}"]`).check();
    }
    await bulk.getByLabel(t("ui.kb01.bulkOperation")).selectOption(action);
    await bulk.getByLabel(t("ui.kb01.reason")).fill("Synthetic explicit batch lifecycle authorization");
    await bulk.getByRole("button", { name: t("ui.kb01.bulkPreview") }).click();
    await expect(bulk.locator("article[data-bulk-preview-id]")).toHaveCount(2);
    for (const item of completed.items) {
      const v = await (await page.request.get(`/api/v1/admin/knowledge-versions/${item.knowledge_version_id}`)).json();
      await bulk.locator(`article[data-bulk-preview-id="${v.document_id}"]`).getByLabel(t("ui.kb01.bulkChooseVersion")).selectOption(item.knowledge_version_id);
    }
    await bulk.getByRole("button", { name: t("ui.kb01.bulkConfirm") }).click();
    await expect(bulk.getByText(t("ui.kb01.bulkSuccess"), { exact: true })).toHaveCount(2);
    for (const item of completed.items) {
      const v = await (await page.request.get(`/api/v1/admin/knowledge-versions/${item.knowledge_version_id}`)).json();
      expect(v.lifecycle).toBe(action === "expire" ? "EXPIRED" : "ARCHIVED");
    }
    await page.reload();
  }
  await page.reload();
  const restored = await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)).json();
  expect(restored.status).toBe("COMPLETED");
  expect(restored.items).toEqual(completed.items);
  expect(errors).toEqual([]);
});
