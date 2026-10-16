import { test, expect } from "@playwright/test";
import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import enUS from "../src/locales/en-US.json" with { type: "json" };
import zhHK from "../src/locales/zh-HK.json" with { type: "json" };
import zhCN from "../src/locales/zh-CN.json" with { type: "json" };
const catalogs = { "zh-CN": zhCN, "zh-HK": zhHK, "en-US": enUS };
const prefix = "/api/v1/admin/knowledge-management";
const originals = process.env.KB01_BROWSER_FIXTURES
  ? (JSON.parse(fs.readFileSync(process.env.KB01_BROWSER_FIXTURES, "utf8")) as {
      locale: string;
      format: string;
      path: string;
      marker: string;
    }[])
  : [];
for (const locale of Object.keys(catalogs) as (keyof typeof catalogs)[]) {
  test(`KB01 genuine six-format local batch, scoped SQL counts, source and download in ${locale}`, async ({
    page,
  }) => {
    test.setTimeout(240_000);
    const t = (key: keyof typeof enUS) => catalogs[locale][key];
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("response", (response) => {
      if (response.status() >= 500) errors.push(`HTTP_${response.status()}`);
    });
    const fixtures = originals.filter((row) => row.locale === locale);
    expect(fixtures).toHaveLength(6);
    await page.addInitScript(
      (value) => {
        if (["http:", "https:"].includes(location.protocol)) localStorage.setItem("stage1-alpha.ui-locale", value);
      },
      locale,
    );
    expect(
      (
        await page.request.post("/m0-demo/login", { data: { persona: "A" } })
      ).status(),
    ).toBe(200);
    await page.goto("/admin?admin_resource=knowledge-management");
    await expect(
      page.getByRole("heading", { name: t("ui.kb01.workspace"), exact: true }),
    ).toBeVisible();
    await page
      .getByRole("tab", { name: t("ui.kb01.uploads"), exact: true })
      .click();
    await page
      .getByLabel(t("ui.kb01.files"), { exact: true })
      .setInputFiles(fixtures.map((row) => row.path));
    await page
      .getByRole("button", { name: t("ui.kb01.startResume"), exact: true })
      .click();
    const createBatch = page.getByRole("button", {
      name: t("ui.kb01.createBatch"),
      exact: true,
    });
    await expect(createBatch).toBeEnabled({ timeout: 120_000 });
    const batchResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === prefix + "/import-batches" &&
        response.request().method() === "POST",
    );
    await createBatch.click();
    const batch = await (await batchResponse).json();
    const sourcePage = await (
      await page.request.get(prefix + "/sources")
    ).json();
    expect(sourcePage.items.length).toBeGreaterThan(0);
    const source = sourcePage.items[0];
    await page
      .getByRole("combobox", { name: t("ui.kb01.sourceId"), exact: true })
      .selectOption(source.source_id);
    const versions = await (
      await page.request.get(
        `${prefix}/sources/${source.source_id}/collection-versions`,
      )
    ).json();
    await page
      .getByRole("combobox", {
        name: t("ui.kb01.collectionVersion"),
        exact: true,
      })
      .selectOption(versions.items[0].collection_version_id);
    await page.locator("form").filter({ has: page.getByRole("heading", { name: t("ui.kb01.documentMetadata"), exact: true }) })
      .getByRole("textbox", { name: t("ui.kb01.language"), exact: true })
      .fill("en");
    const mapped = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname ===
        `${prefix}/import-batches/${batch.batch_id}/confirm-items`,
    );
    await page
      .getByRole("button", { name: t("ui.kb01.confirmMapping"), exact: true })
      .click();
    expect((await mapped).status()).toBe(200);
    await expect
      .poll(
        async () =>
          (
            await (
              await page.request.get(
                `${prefix}/import-batches/${batch.batch_id}`,
              )
            ).json()
          ).status,
        { timeout: 120_000, intervals: [1000] },
      )
      .toBe("COMPLETED");
    const completed = await (
      await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)
    ).json();
    expect(completed.counts).toEqual({ COMPLETED: 6 });
    const ids = new Map<string, string>(
      completed.items.map(
        (item: { relative_path: string; knowledge_version_id: string }) => [
          item.relative_path,
          item.knowledge_version_id,
        ],
      ),
    );
    for (const fixture of fixtures) {
      const id = ids.get(path.basename(fixture.path));
      expect(id).toBeTruthy();
      const preview = await (
        await page.request.get(`${prefix}/documents/versions/${id}/preview`)
      ).json();
      expect(
        preview.items.some((node: { original_excerpt: string }) =>
          node.original_excerpt.includes(fixture.marker),
        ),
      ).toBe(true);
      expect(
        preview.items.every((node: { citation_id: string }) =>
          Boolean(node.citation_id),
        ),
      ).toBe(true);
    }
    await page
      .getByRole("tab", { name: t("ui.kb01.documents"), exact: true })
      .click();
    const docx = fixtures.find((row) => row.format === "DOCX")!;
    const currentVersion = await (
      await page.request.get(
        `/api/v1/admin/knowledge-versions/${ids.get(path.basename(docx.path))}`,
      )
    ).json();
    await page
      .locator(`button[data-document-id="${currentVersion.document_id}"]`)
      .click();
    await page
      .getByRole("button", { name: t("ui.kb01.preview"), exact: true })
      .click();
    await expect(page.getByText(docx.marker, { exact: false })).toBeVisible();
    const download = page.waitForEvent("download");
    await page
      .getByRole("link", { name: t("ui.kb01.downloadOriginal") })
      .click();
    const output = await (await download).path();
    expect(output).toBeTruthy();
    const hash = (file: string) =>
      crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
    expect(hash(output!)).toBe(hash(docx.path));
    // The management channel must be able to reach the existing quality,
    // independent review, publication and runtime barrier without a seed result.
    const jurisdictionOptions = await (await page.request.get(`${prefix}/scope-options?dimension=jurisdiction`)).json();
    expect(jurisdictionOptions.items.length).toBeGreaterThan(0);
    const jurisdictionId = jurisdictionOptions.items[0].object_id;
    const docxId = ids.get(path.basename(docx.path))!;
    await page.getByRole("button", { name: t("ui.kb01.scopeBindings"), exact: true }).click();
    const scopePanel = page.getByRole("region", { name: t("ui.kb01.scopeBindings"), exact: true });
    await expect(scopePanel.getByLabel(t("ui.kb01.scopeType"))).toHaveValue("");
    await scopePanel.getByLabel(t("ui.kb01.scopeType")).selectOption("GLOBAL");
    await expect(scopePanel.getByLabel(t("ui.kb01.scopeReferences")).locator(`option[value="${jurisdictionId}"]`)).toHaveCount(1);
    await scopePanel.getByLabel(t("ui.kb01.scopeReferences")).selectOption(jurisdictionId);
    await scopePanel.getByLabel(t("ui.kb01.reason")).fill("SYNTHETIC_GOVERNED_TEST_DATA explicit knowledge scope");
    const bound = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith(`/documents/versions/${docxId}/scope-bindings`));
    await scopePanel.getByRole("button", { name: t("ui.kb01.addScopeBinding") }).click();
    expect((await bound).status()).toBe(201);
    await expect(scopePanel.getByLabel(t("ui.kb01.scopeType"))).toHaveValue("");
    await page.getByRole("textbox", { name: t("ui.kb01.reason"), exact: true }).first().fill("SYNTHETIC_GOVERNED_TEST_DATA source publication");
    const pending = new Map<string, number>();
    for (const action of ["validate", "submit-review"] as const) {
      const response = page.waitForResponse((value) => value.request().method() === "POST" && value.url().endsWith(`/documents/versions/${docxId}/${action}`));
      await page.getByRole("button", { name: t(`ui.kb01.action.${action}`), exact: true }).click();
      const actual = await response;
      expect(actual.status()).toBe(200);
      const state = await actual.json();
      expect(state.lifecycle).toBe(action === "validate" ? "VALIDATED" : "PENDING_REVIEW");
      pending.set(docxId, state.record_version);
    }
    await expect(page.getByRole("button", { name: t("ui.kb01.action.approve"), exact: true })).toBeDisabled();
    for (const id of ids.values()) {
      if (id === docxId) continue;
      const v = await (await page.request.get(`/api/v1/admin/knowledge-versions/${id}`)).json();
      const binding = await page.request.post(`${prefix}/documents/versions/${id}/scope-bindings`, { data: {
        expected_record_version: v.record_version, idempotency_key: crypto.randomUUID(),
        reason: "SYNTHETIC_GOVERNED_TEST_DATA explicit scope", scope_type: "GLOBAL",
        dimensions: { jurisdiction: [jurisdictionId] },
      } });
      expect(binding.status()).toBe(201);
      let revision = (await binding.json()).record_version;
      for (const action of ["validate", "submit-review"]) {
        const changed = await page.request.post(`${prefix}/documents/versions/${id}/${action}`, { data: {
          expected_record_version: revision, idempotency_key: crypto.randomUUID(), reason: "Synthetic governed publication review",
        } });
        expect(changed.status()).toBe(200);
        const state = await changed.json();
        expect(state.lifecycle).toBe(action === "validate" ? "VALIDATED" : "PENDING_REVIEW");
        revision = state.record_version;
      }
      pending.set(id, revision);
    }
    const workspaceUrl = page.url();
    for (const [persona, action, expected] of [["REVIEWER", "approve", "APPROVED"], ["PUBLISHER", "publish", "ACTIVE"]] as const) {
      // Dispose the previous actor's polling page before changing its session.
      await page.goto("about:blank");
      expect((await page.request.post("/m0-demo/login", { data: { persona } })).status()).toBe(200);
      await page.goto(workspaceUrl);
      await page.locator(`button[data-document-id="${currentVersion.document_id}"]`).click();
      await page.getByRole("textbox", { name: t("ui.kb01.reason"), exact: true }).first().fill("SYNTHETIC_GOVERNED_TEST_DATA independent governed publication");
      const response = page.waitForResponse((value) => value.request().method() === "POST" && value.url().endsWith(`/documents/versions/${docxId}/${action}`));
      await page.getByRole("button", { name: t(`ui.kb01.action.${action}`), exact: true }).click();
      const actual = await response;
      expect(actual.status()).toBe(200);
      const state = await actual.json();
      expect(state.lifecycle).toBe(expected);
      pending.set(docxId, state.record_version);
      for (const id of ids.values()) {
        if (id === docxId) continue;
        const changed = await page.request.post(`${prefix}/documents/versions/${id}/${action}`, { data: {
          expected_record_version: pending.get(id), idempotency_key: crypto.randomUUID(), reason: "Synthetic independent review and publication",
        } });
        expect(changed.status()).toBe(200);
        const result = await changed.json();
        expect(result.lifecycle).toBe(expected);
        pending.set(id, result.record_version);
      }
    }
    for (const id of ids.values()) {
      await expect.poll(async () => (await (await page.request.get(`${prefix}/documents/versions/${id}/scope-bindings`)).json()).runtime_readiness?.status,
        { timeout: 60_000, intervals: [1000] }).toBe("READY");
    }
    // Publication authority does not grant transport-history authority.
    await page.goto("about:blank");
    const publisherBatch = await page.request.get(`${prefix}/import-batches/${batch.batch_id}`);
    expect(publisherBatch.status()).toBe(403);
    expect((await page.request.post("/m0-demo/login", { data: { persona: "A" } })).status()).toBe(200);
    await page.goto(workspaceUrl);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: t("ui.kb01.workspace"), exact: true }),
    ).toBeVisible();
    const savedResponse = await page.request.get(`${prefix}/import-batches/${batch.batch_id}`);
    expect(savedResponse.status()).toBe(200);
    const saved = await savedResponse.json();
    expect(
      saved.items
        .map(
          (item: { knowledge_version_id: string }) => item.knowledge_version_id,
        )
        .sort(),
    ).toEqual([...ids.values()].sort());
    expect(errors).toEqual([]);
  });
}
