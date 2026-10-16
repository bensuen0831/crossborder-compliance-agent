import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../../i18n";
import { AdminClient } from "../admin/client";
import type { FetchPort } from "../admin/contracts";
import { KnowledgeManagementClient, type Schema } from "./client";
import { BulkDocumentActions } from "./BulkDocumentActions";

const documents: Schema<"ManagedKnowledgeDocumentView">[] = ["a", "b"].map((id) => ({
  document_id: id, source_id: "source", display_name: `Synthetic ${id}`, record_version: id === "a" ? 7 : 12,
  status: "ACTIVE", created_at: "2026-10-16T00:00:00Z", updated_at: "2026-10-16T00:00:00Z",
}));
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
function setup(protectedId = "", failFirst = "") {
  let failed = false;
  const fetcher = vi.fn<FetchPort>().mockImplementation(async (path, options) => {
    const url = String(path);
    if (options?.method !== "GET") {
      if (!failed && url.endsWith(failFirst) && failFirst) { failed = true; return response({}, 409); }
      return response({});
    }
    const id = url.split("/documents/")[1].split("/")[0];
    if (url.endsWith("/impact")) return response({ document_id: id, eligible_draft: id !== protectedId,
      protected_version_history: id === protectedId, references: { snapshots: id === protectedId ? 1 : 0 } });
    return response({ ...documents.find((row) => row.document_id === id), versions: [{
      knowledge_version_id: `${id}-exact-old`, document_id: id, version: 1, record_version: 19, lifecycle: "EXPIRED", language: "en",
      metadata: { title: "Synthetic old", labels: [] }, file_available: false, content_hash: null, effective_from: null, effective_to: null,
    }, { knowledge_version_id: `${id}-latest`, document_id: id, version: 2, record_version: 23, lifecycle: "ACTIVE", language: "en",
      metadata: { title: "Synthetic latest", labels: [] }, file_available: false, content_hash: null, effective_from: null, effective_to: null,
    }] });
  });
  const client = new KnowledgeManagementClient(new AdminClient(fetcher));
  const changed = vi.fn();
  return { fetcher, client, changed };
}
const t = (key: string) => i18n.t("ui.kb01." + key);
async function selectAndPreview() {
  await userEvent.click(screen.getByLabelText("Synthetic a"));
  await userEvent.click(screen.getByLabelText("Synthetic b"));
  await userEvent.type(screen.getByLabelText(t("reason")), "Explicit lifecycle authorization");
  await userEvent.click(screen.getByRole("button", { name: t("bulkPreview") }));
  await screen.findByText("a", { exact: true });
}

describe("bounded document batch orchestration", () => {
  it.each(["zh-CN", "zh-HK", "en-US"])("requires exact human-selected versions and sends canonical CAS commands in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    const { fetcher, client, changed } = setup();
    render(<BulkDocumentActions client={client} documents={documents} can={() => true} onChanged={changed} />);
    await userEvent.selectOptions(screen.getByLabelText(t("bulkOperation")), "archive");
    await selectAndPreview();
    const confirm = screen.getByRole("button", { name: t("bulkConfirm") });
    expect(confirm).toBeDisabled();
    const choices = screen.getAllByRole("combobox", { name: t("bulkChooseVersion") });
    expect(choices[0]).toHaveValue("");
    await userEvent.selectOptions(choices[0], "a-exact-old");
    await userEvent.selectOptions(choices[1], "b-exact-old");
    await userEvent.click(confirm);
    await waitFor(() => expect(changed).toHaveBeenCalledOnce());
    const mutations = fetcher.mock.calls.filter(([, options]) => options?.method === "POST");
    expect(mutations).toHaveLength(2);
    expect(mutations.map(([url]) => url)).toEqual([
      "/api/v1/admin/knowledge-management/documents/versions/a-exact-old/archive",
      "/api/v1/admin/knowledge-management/documents/versions/b-exact-old/archive",
    ]);
    for (const [, options] of mutations) expect(JSON.parse(String(options?.body))).toEqual({
      expected_record_version: 19, reason: "Explicit lifecycle authorization", idempotency_key: expect.any(String),
    });
    expect(screen.getByLabelText(t("reason"))).toBeDisabled();
  });
  it("retains partial results and reuses the exact command on a failed-item retry", async () => {
    const { fetcher, client, changed } = setup("", "/b");
    render(<BulkDocumentActions client={client} documents={documents} can={() => true} onChanged={changed} />);
    await selectAndPreview();
    await userEvent.click(screen.getByRole("button", { name: t("bulkConfirm") }));
    await screen.findByText("HTTP_409");
    expect(screen.getByText(t("bulkSuccess"))).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: t("bulkConfirm") }));
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(2));
    const commands = fetcher.mock.calls.filter(([, options]) => options?.method === "DELETE");
    expect(commands).toHaveLength(3);
    expect(String(commands[0][0])).toMatch(/\/a$/);
    expect(JSON.parse(String(commands[0][1]?.body)).expected_record_version).toBe(7);
    expect(commands[1][0]).toEqual(commands[2][0]);
    expect(commands[1][1]?.body).toBe(commands[2][1]?.body);
    expect(JSON.parse(String(commands[1][1]?.body)).expected_record_version).toBe(12);
    expect(screen.getAllByText(t("bulkSuccess"))).toHaveLength(2);
  });
  it("does not submit deletion for backend-projected protected documents", async () => {
    const { fetcher, client, changed } = setup("b");
    render(<BulkDocumentActions client={client} documents={documents} can={() => true} onChanged={changed} />);
    await selectAndPreview();
    await userEvent.click(screen.getByRole("button", { name: t("bulkConfirm") }));
    await waitFor(() => expect(changed).toHaveBeenCalledOnce());
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === "DELETE")).toHaveLength(1);
    expect(screen.getAllByText(t("bulkProtected")).length).toBeGreaterThan(0);
  });
  it("rechecks operation capabilities after preview", async () => {
    const { fetcher, client, changed } = setup();
    const view = render(<BulkDocumentActions client={client} documents={documents} can={() => true} onChanged={changed} />);
    await selectAndPreview();
    view.rerender(<BulkDocumentActions client={client} documents={documents} can={(op) => op !== "document:delete"} onChanged={changed} />);
    expect(screen.getByRole("button", { name: t("bulkConfirm") })).toBeDisabled();
    expect(fetcher.mock.calls.every(([, options]) => options?.method === "GET")).toBe(true);
  });
  it("does not infer batch mutation authority from read access", () => {
    const { client, changed } = setup();
    render(<BulkDocumentActions client={client} documents={documents} can={(op) => op === "document:read"} onChanged={changed} />);
    expect(screen.queryByRole("region", { name: t("bulkActions") })).not.toBeInTheDocument();
  });
});
