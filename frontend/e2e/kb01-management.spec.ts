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
      (value) => localStorage.setItem("stage1-alpha.ui-locale", value),
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
    await page
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
    await page.reload();
    await expect(
      page.getByRole("heading", { name: t("ui.kb01.workspace"), exact: true }),
    ).toBeVisible();
    const saved = await (
      await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)
    ).json();
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
