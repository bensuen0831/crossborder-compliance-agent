import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../../i18n";
import { AdminClient } from "../admin/client";
import type { FetchPort } from "../admin/contracts";
import { KnowledgeManagementClient, type Schema } from "./client";
import { ManifestPanel } from "./ManifestPanel";

const batch: Schema<"KnowledgeBatchView"> = {
  batch_id: "batch", archive_upload_session_id: null, status: "PREVIEW", record_version: 9,
  created_by: "server-author", manifest_digest: "inventory", attempts: 0, error_code: null,
};
const response = (data: unknown) => new Response(JSON.stringify(data), {
  headers: { "Content-Type": "application/json" },
});

describe("durable catalogue review", () => {
  it.each(["zh-CN", "zh-HK", "en-US"])("keeps missing/duplicate proposals separate from matched files in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    const fetcher = vi.fn<FetchPort>().mockImplementation(async (path) => {
      const url = String(path);
      const manifest = { manifest_id: "preview", status: "COMPLETED", created_at: "2026-10-16T00:00:00Z",
        created_by: "server-author", record_count: 3, error_code: null };
      if (url.includes("/manifests?")) return response({ total: 1, page: 1, page_size: 25, items: [manifest] });
      if (url.includes("/manifests/preview?")) return response({ ...manifest, total: 3, page: 1, page_size: 25, items: [
        { manifest_record_id: "matched", row_number: 2, canonical_path: "a/same.txt", matched_item_id: "actual-item",
          status: "FILE_MATCHED", proposed_values: { title: "Reviewed proposal" }, metadata_refs: {}, issues: [] },
        { manifest_record_id: "missing", row_number: 3, canonical_path: "missing.txt", matched_item_id: null,
          status: "FILE_MISSING", proposed_values: { title: "Missing proposal" }, metadata_refs: {}, issues: [] },
        { manifest_record_id: "duplicate", row_number: 4, canonical_path: "a/same.txt", matched_item_id: "actual-item",
          status: "MAPPING_REQUIRED", proposed_values: { title: "Duplicate proposal" }, metadata_refs: {},
          issues: [{ row: 4, field: "relative_path", code: "DUPLICATE_CANDIDATE" }] },
      ] });
      throw new Error("Unexpected request " + url);
    });
    const use = vi.fn();
    render(<ManifestPanel client={new KnowledgeManagementClient(new AdminClient(fetcher))}
      batch={batch} labels={[]} can={() => true} scope="test-session" onUse={use} />);
    await screen.findByRole("option", { name: /COMPLETED/ });
    await userEvent.selectOptions(screen.getByLabelText(i18n.t("ui.kb01.manifestHistory")), "preview");
    await screen.findByText(/Missing proposal/);
    const buttons = screen.getAllByRole("button", { name: i18n.t("ui.kb01.manifestUseProposal") });
    expect(buttons[0]).toBeEnabled(); expect(buttons[1]).toBeDisabled(); expect(buttons[2]).toBeDisabled();
    await userEvent.click(buttons[0]);
    expect(use).toHaveBeenCalledWith(expect.objectContaining({ manifest_record_id: "matched", matched_item_id: "actual-item" }));
    expect(fetcher.mock.calls.every(([, options]) => options?.method !== "POST")).toBe(true);
  });
});
