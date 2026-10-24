import { test, expect } from "@playwright/test";
import crypto from "node:crypto";
import en from "../src/locales/en-US.json" with { type: "json" };
import { safeBrowserError } from "./kb01-safe-evidence";

const prefix = "/api/v1/admin/knowledge-management";
const t = (key: keyof typeof en) => en[key];

test("KB01 country and regulation-category UI preserves governed versions, tree and protected deletion", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(safeBrowserError(error.message)));
  page.on("console", message => { if (message.type() === "error") errors.push(safeBrowserError(message.text())); });
  page.on("response", response => { if (response.status() >= 500) errors.push(`HTTP_${response.status()}`); });
  await page.addInitScript(() => { if (["http:", "https:"].includes(location.protocol)) localStorage.setItem("stage1-alpha.ui-locale", "en-US"); });
  const workspace = "/admin?admin_resource=knowledge-management";
  const login = async (persona: string) => {
    await page.goto("about:blank");
    expect((await page.request.post("/m0-demo/login", { data: { persona } })).status()).toBe(200);
    await page.goto(workspace);
    await page.getByRole("tab", { name: t("ui.kb01.taxonomy"), exact: true }).click();
  };
  await login("A");
  const rows: { id: string; versionId: string; name: string; kind: string }[] = [];
  for (const kind of ["JURISDICTION_CONFIG", "REGULATION_CATEGORY"]) {
    const code = "KB01_" + crypto.randomUUID().replaceAll("-", "").toUpperCase();
    const name = "SYNTHETIC_GOVERNED_TEST_DATA " + code;
    const form = page.locator("form").filter({ has: page.getByRole("heading", { name: t("ui.kb01.createTaxonomy"), exact: true }) });
    await form.getByRole("combobox", { name: t("ui.kb01.kind"), exact: true }).selectOption(kind);
    await form.getByLabel(t("ui.kb01.code"), { exact: true }).fill(code);
    await form.getByLabel(t("ui.kb01.name"), { exact: true }).fill(name);
    const creation = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === prefix + "/taxonomy");
    await form.getByRole("button", { name: t("ui.kb01.createTaxonomy"), exact: true }).click();
    const created = await creation;
    expect(created.status()).toBe(201);
    const row = await created.json();
    await page.getByRole("button", { name: new RegExp("^" + name + " · " + kind) }).click();
    await page.getByRole("textbox", { name: t("ui.kb01.reason"), exact: true }).fill("SYNTHETIC_GOVERNED_TEST_DATA metadata review");
    const detail = page.getByRole("heading", { name, exact: true }).locator("..");
    const updatedName = name + " reviewed";
    await detail.getByLabel(t("ui.kb01.name") + " (en-US)", { exact: true }).fill(updatedName);
    await detail.getByLabel(t("ui.kb01.aliases"), { exact: true }).fill("synthetic-alias-" + code);
    const edited = page.waitForResponse(response => response.request().method() === "PATCH" && new URL(response.url()).pathname.startsWith(prefix + "/taxonomy/versions/"));
    await detail.getByRole("button", { name: t("ui.kb01.saveMetadata"), exact: true }).click();
    expect((await edited).status()).toBe(200);
    await expect(page.getByRole("heading", { name: updatedName, exact: true })).toBeVisible();
    const submission = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith(`/taxonomy/versions/${row.version_id}/submit-review`));
    await page.getByRole("button", { name: t("ui.kb01.action.submit-review"), exact: true }).click();
    expect((await submission).status()).toBe(200);
    await expect(page.getByRole("button", { name: t("ui.kb01.action.approve"), exact: true })).toBeDisabled();
    rows.push({ id: row.definition_id, versionId: row.version_id, name: updatedName, kind });
  }
  for (const [persona, action, lifecycle] of [["REVIEWER", "approve", "APPROVED"], ["PUBLISHER", "publish", "ACTIVE"]] as const) {
    await login(persona);
    for (const row of rows) {
      await page.getByRole("button", { name: new RegExp("^" + row.name + " · " + row.kind) }).click();
      await page.getByRole("textbox", { name: t("ui.kb01.reason"), exact: true }).fill("Synthetic independent metadata review and publication");
      const changed = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith(`/taxonomy/versions/${row.versionId}/${action}`));
      await page.getByRole("button", { name: t(`ui.kb01.action.${action}`), exact: true }).click();
      expect((await changed).status()).toBe(200);
      const canonical = await (await page.request.get(`${prefix}/taxonomy/${row.id}`)).json();
      expect(canonical.lifecycle).toBe(lifecycle);
      expect(canonical.payload.aliases).toHaveLength(1);
    }
  }
  await login("A");
  const country = rows.find(row => row.kind === "JURISDICTION_CONFIG")!;
  await page.getByRole("button", { name: new RegExp("^" + country.name + " · " + country.kind) }).click();
  const impactResponse = page.waitForResponse(response => response.request().method() === "GET" && response.url().endsWith(`/taxonomy/${country.id}/impact`));
  await page.getByRole("button", { name: t("ui.kb01.impact"), exact: true }).click();
  const impact = await (await impactResponse).json();
  expect(impact.eligible_draft).toBe(false);
  await expect(page.getByRole("button", { name: t("ui.kb01.deleteDraft"), exact: true })).toBeDisabled();
  await page.getByRole("tab", { name: t("ui.kb01.documents"), exact: true }).click();
  const treeCountry = page.getByRole("button", { name: country.name, exact: true });
  await expect(treeCountry).toBeVisible();
  await treeCountry.click();
  await expect(treeCountry).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByRole("button", { name: country.name, exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
