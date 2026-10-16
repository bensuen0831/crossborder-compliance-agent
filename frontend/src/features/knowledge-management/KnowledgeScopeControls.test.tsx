import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../../i18n";
import { AdminClient } from "../admin/client";
import type { FetchPort } from "../admin/contracts";
import { KnowledgeManagementClient, type Schema } from "./client";
import { KnowledgeScopeControls } from "./KnowledgeScopeControls";

const version: Schema<"ManagedKnowledgeVersionView"> = {
  knowledge_version_id: "exact-version", document_id: "document", version: 1, record_version: 9,
  lifecycle: "INGESTED", language: "en", metadata: { title: "Synthetic source", description: "", labels: [] },
  file_available: true, content_hash: "content", effective_from: null, effective_to: null,
};
const response = (data: unknown) => new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });

describe("canonical knowledge scope management", () => {
  it.each(["zh-CN", "zh-HK", "en-US"])("requires an explicit scope and submits backend references with CAS in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    const fetcher = vi.fn<FetchPort>().mockImplementation(async (path, options) => {
      if (options?.method === "POST") return response({});
      if (String(path).includes("/scope-options?")) return response({
        dimension: "jurisdiction", total: 1, page: 1, page_size: 50,
        items: [{ object_id: "canonical-jurisdiction", display_name: "Synthetic jurisdiction", code: "SYNTHETIC" }],
      });
      return response({ knowledge_version_id: "exact-version", bindings: [], quality: {
        status: "FAILED", checks: { binding_completeness: false }, reason_codes: ["BINDING_REQUIRED"],
      }, runtime_readiness: null });
    });
    const refreshed = vi.fn(async () => {});
    render(<KnowledgeScopeControls client={new KnowledgeManagementClient(new AdminClient(fetcher))}
      version={version} can={() => true} refreshed={refreshed} onQueued={vi.fn(async () => {})} />);
    expect(screen.getByLabelText(i18n.t("ui.kb01.scopeType"))).toHaveValue("");
    expect(screen.getByRole("button", { name: i18n.t("ui.kb01.addScopeBinding") })).toBeDisabled();
    await screen.findByRole("option", { name: /Synthetic jurisdiction/ });
    await userEvent.selectOptions(screen.getByLabelText(i18n.t("ui.kb01.scopeType")), "GLOBAL");
    await userEvent.selectOptions(screen.getByLabelText(i18n.t("ui.kb01.scopeReferences")), "canonical-jurisdiction");
    await userEvent.type(screen.getByLabelText(i18n.t("ui.kb01.reason")), "Human scope configuration");
    await userEvent.click(screen.getByRole("button", { name: i18n.t("ui.kb01.addScopeBinding") }));
    await waitFor(() => expect(refreshed).toHaveBeenCalledOnce());
    const sent = fetcher.mock.calls.find(([, options]) => options?.method === "POST");
    expect(String(sent?.[0])).toContain("/exact-version/scope-bindings");
    expect(JSON.parse(String(sent?.[1]?.body))).toEqual({
      expected_record_version: 9, idempotency_key: expect.any(String), reason: "Human scope configuration",
      scope_type: "GLOBAL", dimensions: { jurisdiction: ["canonical-jurisdiction"] },
      permission_scopes: [], effective_from: null, effective_to: null,
    });
    expect(screen.getByText(/binding_completeness.*false/)).toBeVisible();
  });
});
