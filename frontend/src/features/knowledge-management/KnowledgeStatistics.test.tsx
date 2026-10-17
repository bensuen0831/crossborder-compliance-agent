import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../../i18n";
import { AdminClient } from "../admin/client";
import type { FetchPort } from "../admin/contracts";
import { KnowledgeManagementClient, type Schema } from "./client";
import { KnowledgeStatistics } from "./KnowledgeStatistics";

const statistics: Schema<"KnowledgeStatisticsView"> = {
  as_of: "2026-10-16T00:00:00Z", documents: 2, versions: 5, attached_originals: 3, attached_bytes: 150,
  parse_status: { COMPLETED: 3, FAILED: 1 }, version_lifecycle_counts: { DRAFT: 2, ACTIVE: 2, EXPIRED: 1 },
  import_inventory: { scope: "TENANT_OPERATIONAL_UNFILTERED", manifest_records: 7, missing_manifest_files: 4, verified_uploads: 6, verified_upload_bytes: 650 },
  by_format: [{ key: "DOCX", documents: 2 }], by_language: [{ key: "ar", documents: 2 }], by_lifecycle: [], by_classification: [],
  classification_groups_truncated: false, representative_version: "ACTIVE_ELSE_LATEST_MATCHING_LIST", many_to_many_group_totals_are_not_global_totals: true,
  scope: { query: "Scoped", label_ids: ["country", "category"], label_id: null, language: null, lifecycle: null },
};
const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });

describe("server-owned statistics and cross-tabs", () => {
  it.each(["zh-CN", "zh-HK", "en-US"])("preserves separate counting scopes and sends exact country/category filters in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    const fetcher = vi.fn<FetchPort>().mockImplementation(async () => response({
      as_of: statistics.as_of, dimension: "language", total: 1, page: 1, page_size: 50,
      items: [{ jurisdiction_id: "country", jurisdiction_code: "SYNTHETIC", value: "ar", documents: 2 }],
      scope: statistics.scope, missing_dimension_values_excluded: true, group_totals_are_not_global_totals: true,
    }));
    render(<KnowledgeStatistics client={new KnowledgeManagementClient(new AdminClient(fetcher))} statistics={statistics}
      filters="query=Scoped&label_ids=country&label_ids=category" />);
    expect(screen.getByText(i18n.t("ui.kb01.importInventoryScope"))).toBeVisible();
    expect(screen.getByText("DOCX: 2")).toBeVisible();
    expect(screen.getByText("ar: 2")).toBeVisible();
    expect(fetcher).not.toHaveBeenCalled();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: i18n.t("ui.kb01.crossTab") }), "language");
    await screen.findByRole("cell", { name: "SYNTHETIC" });
    const request = new URL(String(fetcher.mock.calls[0][0]), "http://test.invalid");
    expect(request.pathname).toBe("/api/v1/admin/knowledge-management/statistics/cross-tab");
    expect(request.searchParams.getAll("label_ids")).toEqual(["country", "category"]);
    expect(request.searchParams.get("dimension")).toBe("language");
    expect(request.searchParams.get("page_size")).toBe("50");
    expect(request.searchParams.has("tenant_id")).toBe(false);
    expect(screen.getByText(i18n.t("ui.kb01.crossTabScope"))).toBeVisible();
  });
  it("does not turn a permission-restricted import inventory into zero", () => {
    const fetcher = vi.fn<FetchPort>();
    render(<KnowledgeStatistics client={new KnowledgeManagementClient(new AdminClient(fetcher))} statistics={{ ...statistics, import_inventory: null }} filters="" />);
    expect(screen.getByText(i18n.t("ui.kb01.importInventoryRestricted"))).toBeVisible();
    expect(screen.queryByText(i18n.t("ui.kb01.manifest_records"))).not.toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
  });
});
