import { test, expect } from "@playwright/test";
import crypto from "node:crypto";
import en from "../src/locales/en-US.json" with { type: "json" };
import { safeBrowserError } from "./kb01-safe-evidence";

const prefix = "/api/v1/admin/knowledge-management";
const t = (key: keyof typeof en) => en[key];

test("KB01 bounded batch deletion previews references, uses canonical commands and reconciles SQL counts", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(safeBrowserError(e.message)));
  page.on("console", (message) => { if (message.type() === "error") errors.push(safeBrowserError(message.text())); });
  page.on("response", (response) => { if (response.status() >= 500) errors.push(`HTTP_${response.status()}`); });
  await page.addInitScript(() => { if (["http:", "https:"].includes(location.protocol)) localStorage.setItem("stage1-alpha.ui-locale", "en-US"); });
  expect((await page.request.post("/m0-demo/login", { data: { persona: "A" } })).status()).toBe(200);
  const source = (await (await page.request.get(prefix + "/sources")).json()).items[0];
  const collection = (await (await page.request.get(`${prefix}/sources/${source.source_id}/collection-versions`)).json()).items[0];
  const marker = "SYNTHETIC_BULK_" + crypto.randomUUID();
  const labels: { kind: string; definition_id: string; version_id: string; record_version: number }[] = [];
  for (const kind of ["JURISDICTION_CONFIG", "REGULATION_CATEGORY"]) {
    const made = await page.request.post(prefix + "/taxonomy", { data: {
      kind, code: "BULK_" + crypto.randomUUID().replaceAll("-", "").toUpperCase(), display_name: marker + kind,
      payload: kind === "JURISDICTION_CONFIG" ? { jurisdiction_type: "COUNTRY" } : {}, idempotency_key: crypto.randomUUID(),
    } });
    expect(made.status()).toBe(201);
    labels.push({ ...await made.json(), kind });
  }
  for (const [persona, action] of [["A", "submit-review"], ["REVIEWER", "approve"], ["PUBLISHER", "publish"]]) {
    expect((await page.request.post("/m0-demo/login", { data: { persona } })).status()).toBe(200);
    for (const label of labels) {
      const changed = await page.request.post(`${prefix}/taxonomy/versions/${label.version_id}/${action}`, { data: {
        expected_record_version: label.record_version, idempotency_key: crypto.randomUUID(), reason: "Synthetic independent statistics label publication",
      } });
      expect(changed.status()).toBe(200);
      label.record_version = (await changed.json()).record_version;
    }
  }
  expect((await page.request.post("/m0-demo/login", { data: { persona: "A" } })).status()).toBe(200);
  const ids: string[] = [];
  for (const suffix of ["A", "B"]) {
    const made = await page.request.post(prefix + "/documents", { data: {
      source_id: source.source_id, collection_version_id: collection.collection_version_id,
      language: "en", metadata: { title: `${marker}_${suffix}`, labels: labels.map(({ kind, definition_id, version_id }) => ({ kind, definition_id, version_id })) }, idempotency_key: crypto.randomUUID(),
    } });
    expect(made.status()).toBe(201);
    ids.push((await made.json()).document_id);
  }
  const before = await (await page.request.get(`${prefix}/statistics?query=${marker}`)).json();
  expect(before.documents).toBe(2);
  await page.goto("/admin?admin_resource=knowledge-management");
  await page.getByRole("textbox", { name: t("ui.kb01.search"), exact: true }).fill(marker);
  await page.getByRole("combobox", { name: t("ui.kb01.documentSort"), exact: true }).selectOption("title_asc");
  const stats = page.getByRole("region", { name: t("ui.kb01.statistics"), exact: true });
  await stats.getByRole("combobox", { name: t("ui.kb01.crossTab"), exact: true }).selectOption("category");
  await expect(stats.getByRole("region", { name: t("ui.kb01.crossTabResults"), exact: true }).getByRole("cell", { name: "2", exact: true })).toBeVisible();
  const projected = await (await page.request.get(`${prefix}/statistics/cross-tab?dimension=category&query=${marker}`)).json();
  expect(projected.items).toHaveLength(1);
  expect(projected.items[0].documents).toBe(2);
  expect(projected.items[0].jurisdiction_id).toBe(labels[0].definition_id);
  expect(projected.items[0].value).toBe(labels[1].definition_id);
  const bulk = page.getByRole("region", { name: t("ui.kb01.bulkActions"), exact: true });
  for (const id of ids) await bulk.locator(`input[data-bulk-document-id="${id}"]`).check();
  await bulk.getByRole("textbox", { name: t("ui.kb01.reason"), exact: true }).fill("Synthetic explicitly authorized unreferenced draft cleanup");
  await bulk.getByRole("button", { name: t("ui.kb01.bulkPreview"), exact: true }).click();
  await expect(bulk.locator("article[data-bulk-preview-id]")).toHaveCount(2);
  await expect(bulk.getByText(t("ui.kb01.bulkProtected"), { exact: true })).toHaveCount(0);
  await bulk.getByRole("button", { name: t("ui.kb01.bulkConfirm"), exact: true }).click();
  await expect(bulk.getByText(t("ui.kb01.bulkSuccess"), { exact: true })).toHaveCount(2);
  await expect.poll(async () => (await (await page.request.get(`${prefix}/statistics?query=${marker}`)).json()).documents).toBe(0);
  for (const id of ids) {
    const audit = await (await page.request.get(`${prefix}/audit/${id}`)).json();
    expect(audit.items.some((event: { operation: string; reason: string }) => event.operation === "DOCUMENT_DELETE_DRAFT" && event.reason.includes("explicitly authorized"))).toBe(true);
  }
  await page.reload();
  expect((await (await page.request.get(`${prefix}/documents?query=${marker}&sort=title_asc`)).json()).total).toBe(0);
  expect(errors).toEqual([]);
});
