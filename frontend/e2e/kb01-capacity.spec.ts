import { test, expect } from "@playwright/test";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import en from "../src/locales/en-US.json" with { type: "json" };

const prefix = "/api/v1/admin/knowledge-management";
type Original = { name: string; bytes: number; sha256: string; marker: string };
type Fixture = { kind: string; path: string; bytes: number; sha256: string; originals: Original[] };
type Item = { relative_path: string; knowledge_version_id: string };
const t = (key: keyof typeof en) => en[key];

for (const kind of ["SINGLE", "RAR4", "RAR5", "ZIP"] as const) {
  test(`KB01 genuine capacity ${kind}: signed upload through human publication and exact original`, async ({ page }) => {
    test.setTimeout(600_000);
    const root = process.env.KB01_CAPACITY_ROOT;
    expect(root, "Explicit generated capacity fixture directory is mandatory").toBeTruthy();
    const started = Date.now();
    const { stdout } = await promisify(execFile)("python", ["../scripts/kb01/generate_capacity.py", "--output", root!, "--kind", kind], { timeout: 180_000 });
    const fixture = JSON.parse(stdout) as Fixture;
    expect(fixture.bytes).toBeGreaterThan(kind === "SINGLE" ? 500 * 1024 ** 2 : 1024 ** 3);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 500) errors.push(`HTTP_${response.status()}`); });
    await page.addInitScript(() => { if (["http:", "https:"].includes(location.protocol)) localStorage.setItem("stage1-alpha.ui-locale", "en-US"); });
    expect((await page.request.post("/m0-demo/login", { data: { persona: "A" } })).status()).toBe(200);
    await page.goto("/admin?admin_resource=knowledge-management");
    await expect(page.getByRole("heading", { name: t("ui.kb01.workspace"), exact: true })).toBeVisible();
    const workspace = page.url();
    await page.getByRole("tab", { name: t("ui.kb01.uploads"), exact: true }).click();
    await page.getByLabel(t("ui.kb01.files"), { exact: true }).setInputFiles(fixture.path);
    await page.getByRole("button", { name: t("ui.kb01.startResume"), exact: true }).click();
    const create = page.getByRole("button", { name: t("ui.kb01.createBatch"), exact: true });
    await expect(create).toBeEnabled({ timeout: 240_000 });
    const creation = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === prefix + "/import-batches");
    await create.click();
    const batch = await (await creation).json();
    await expect.poll(async () => (await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)).json()).status, { timeout: 180_000, intervals: [1000] }).toBe("PREVIEW");
    const source = (await (await page.request.get(prefix + "/sources")).json()).items[0];
    await page.getByRole("combobox", { name: t("ui.kb01.sourceId"), exact: true }).selectOption(source.source_id);
    const collections = await (await page.request.get(`${prefix}/sources/${source.source_id}/collection-versions`)).json();
    await page.getByRole("combobox", { name: t("ui.kb01.collectionVersion"), exact: true }).selectOption(collections.items[0].collection_version_id);
    await page.locator("form").filter({ has: page.getByRole("heading", { name: t("ui.kb01.documentMetadata"), exact: true }) }).getByRole("textbox", { name: t("ui.kb01.language"), exact: true }).fill("en");
    await expect(page.getByRole("button", { name: t("ui.kb01.confirmMapping"), exact: true })).toBeEnabled({ timeout: 180_000 });
    const mapping = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith(`/import-batches/${batch.batch_id}/confirm-items`));
    await page.getByRole("button", { name: t("ui.kb01.confirmMapping"), exact: true }).click();
    expect((await mapping).status()).toBe(200);
    await expect.poll(async () => (await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)).json()).status, { timeout: 180_000, intervals: [1000] }).toBe("COMPLETED");
    const completed = await (await page.request.get(`${prefix}/import-batches/${batch.batch_id}`)).json();
    expect(completed.counts).toEqual({ COMPLETED: fixture.originals.length });
    const items = completed.items as Item[];
    expect(items).toHaveLength(fixture.originals.length);
    const jurisdiction = (await (await page.request.get(prefix + "/scope-options?dimension=jurisdiction")).json()).items[0].object_id;
    const revisions = new Map<string, number>();
    await page.goto("about:blank");
    for (const item of items) {
      const expected = fixture.originals.find(original => original.name === path.basename(item.relative_path));
      expect(expected).toBeTruthy();
      const previewResponse = await page.request.get(`${prefix}/documents/versions/${item.knowledge_version_id}/preview`);
      expect(previewResponse.status()).toBe(200);
      const preview = await previewResponse.json();
      expect(preview.items.length).toBeGreaterThanOrEqual(12);
      expect(preview.items.every((node: { original_excerpt: string; citation_id: string }) => node.original_excerpt.includes(expected!.marker) && Boolean(node.citation_id))).toBe(true);
      const version = await (await page.request.get(`/api/v1/admin/knowledge-versions/${item.knowledge_version_id}`)).json();
      const bound = await page.request.post(`${prefix}/documents/versions/${item.knowledge_version_id}/scope-bindings`, { data: { expected_record_version: version.record_version, idempotency_key: crypto.randomUUID(), reason: "SYNTHETIC_GOVERNED_TEST_DATA capacity acceptance", scope_type: "GLOBAL", dimensions: { jurisdiction: [jurisdiction] } } });
      expect(bound.status()).toBe(201);
      revisions.set(item.knowledge_version_id, (await bound.json()).record_version);
    }
    for (const [persona, actions] of [["A", ["validate", "submit-review"]], ["REVIEWER", ["approve"]], ["PUBLISHER", ["publish"]]] as const) {
      expect((await page.request.post("/m0-demo/login", { data: { persona } })).status()).toBe(200);
      for (const item of items) for (const action of actions) {
        const response = await page.request.post(`${prefix}/documents/versions/${item.knowledge_version_id}/${action}`, { data: { expected_record_version: revisions.get(item.knowledge_version_id), idempotency_key: crypto.randomUUID(), reason: "Synthetic independent capacity review and publication" } });
        expect(response.status()).toBe(200);
        const version = await response.json();
        expect(version.lifecycle).toBe({ validate: "VALIDATED", "submit-review": "PENDING_REVIEW", approve: "APPROVED", publish: "ACTIVE" }[action]);
        revisions.set(item.knowledge_version_id, version.record_version);
      }
    }
    for (const item of items) await expect.poll(async () => (await (await page.request.get(`${prefix}/documents/versions/${item.knowledge_version_id}/scope-bindings`)).json()).runtime_readiness?.status, { timeout: 60_000, intervals: [1000] }).toBe("READY");
    expect((await page.request.post("/m0-demo/login", { data: { persona: "A" } })).status()).toBe(200);
    await page.goto(workspace);
    await page.reload();
    const version = await (await page.request.get(`/api/v1/admin/knowledge-versions/${items[0].knowledge_version_id}`)).json();
    await page.locator(`button[data-document-id="${version.document_id}"]`).click();
    const downloaded = page.waitForEvent("download");
    await page.getByRole("link", { name: t("ui.kb01.downloadOriginal") }).click();
    const download = await downloaded;
    const file = await download.path();
    expect(file).toBeTruthy();
    const digest = crypto.createHash("sha256");
    for await (const chunk of fs.createReadStream(file!)) digest.update(chunk);
    expect(digest.digest("hex")).toBe(fixture.originals.find(original => original.name === path.basename(items[0].relative_path))!.sha256);
    await download.delete();
    expect(errors).toEqual([]);
    const evidence = process.env.KB01_CAPACITY_EVIDENCE;
    if (evidence) {
      fs.mkdirSync(evidence, { recursive: true });
      fs.writeFileSync(path.join(evidence, `${kind}.json`), JSON.stringify({ kind, bytes: fixture.bytes, sha256: fixture.sha256, batch_id: batch.batch_id, knowledge_version_ids: items.map(item => item.knowledge_version_id), source_class: "SYNTHETIC_GOVERNED_TEST_DATA", status: "PASS", publication: "ACTIVE", runtime: "READY", exact_original_download: "PASS", browser_retries: 0, elapsed_seconds: (Date.now() - started) / 1000 }, null, 2) + "\n");
    }
    // The immutable uploaded archive remains in versioned S3. Only this generated
    // local transport copy is disposable between serial CI capacity scenarios.
    if (kind !== "SINGLE" && process.env.KB01_CAPACITY_DISPOSE_GENERATED === "1") fs.unlinkSync(fixture.path);
  });
}
