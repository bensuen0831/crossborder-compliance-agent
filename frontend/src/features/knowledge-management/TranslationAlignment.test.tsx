import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../../i18n";
import { AdminClient } from "../admin/client";
import type { FetchPort } from "../admin/contracts";
import { KnowledgeManagementClient, type Schema } from "./client";
import { TranslationAlignment } from "./TranslationAlignment";

const source: Schema<"ManagedKnowledgeVersionView"> = {
  knowledge_version_id: "source-version", document_id: "source-document", version: 1,
  record_version: 3, lifecycle: "INGESTED", language: "en", content_hash: "source-hash",
  file_available: true, effective_from: null, effective_to: null,
  metadata: { title: "Source", description: "", labels: [] },
};
const reply = (data: unknown) => new Response(JSON.stringify(data), {
  headers: { "Content-Type": "application/json" },
});

describe("human translation alignment channel", () => {
  it.each(["zh-CN", "zh-HK", "en-US"])("submits exact clause/version identities and CAS without actor authority in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    let created = false;
    const fetcher = vi.fn<FetchPort>().mockImplementation(async (path, options) => {
      const url = String(path);
      if (options?.method === "POST") { created = true; return reply({ translation_id: "alignment" }); }
      if (url.includes("/translation-alignments?")) return reply({
        total: created ? 1 : 0, page: 1, page_size: 25,
        items: created ? [{ translation_id: "alignment", source_language: "en", target_language: "ar",
          review_status: "PENDING", record_version: 1, submitted_by: "server-translator",
          submitted_at: "2026-10-15T00:00:00Z", pairs: [], reason: "Synthetic review" }] : [],
      });
      if (url.includes("/documents?")) return reply({ total: 1, page: 1, page_size: 25,
        items: [{ document_id: "translated-document", display_name: "Arabic human translation" }] });
      if (url.endsWith("/documents/translated-document")) return reply({ versions: [{
        ...source, knowledge_version_id: "target-version", language: "ar", record_version: 7,
      }] });
      if (url.includes("/preview?")) {
        const target = url.includes("/target-version/");
        return reply({ total: 1, page: 1, page_size: 25, items: [{
          structure_node_id: target ? "target-node" : "source-node",
          canonical_locator: "article/1", original_excerpt: target ? "نص تجريبي" : "Synthetic clause",
          citation_id: target ? "target-citation" : "source-citation",
        }] });
      }
      throw new Error("Unexpected transport request " + url);
    });
    render(<TranslationAlignment client={new KnowledgeManagementClient(new AdminClient(fetcher))}
      source={source} can={() => true} />);
    await userEvent.selectOptions(await screen.findByLabelText(i18n.t("ui.kb01.translationDocument")), "translated-document");
    await screen.findByRole("option", { name: /ar · 1/ });
    await userEvent.selectOptions(screen.getByLabelText(i18n.t("ui.kb01.translationVersion")), "target-version");
    await screen.findByRole("option", { name: /نص تجريبي/ });
    await userEvent.selectOptions(screen.getByLabelText(i18n.t("ui.kb01.originalClause")), "source-node");
    await userEvent.selectOptions(screen.getByLabelText(i18n.t("ui.kb01.translatedClause")), "target-node");
    await userEvent.type(screen.getByLabelText(i18n.t("ui.kb01.reason")), "Synthetic review");
    await userEvent.click(screen.getByRole("button", { name: i18n.t("ui.kb01.submitAlignment") }));
    await screen.findByText(/server-translator/);
    const create = fetcher.mock.calls.find(([path, options]) =>
      String(path).endsWith("/translation-alignments") && options?.method === "POST");
    expect(JSON.parse(String(create?.[1]?.body))).toEqual({
      source_version_id: "source-version", target_version_id: "target-version",
      expected_source_record_version: 3, expected_target_record_version: 7,
      translation_method: "HUMAN", pairs: [{ source_node_id: "source-node", target_node_id: "target-node" }],
      reason: "Synthetic review",
    });
    await userEvent.click(screen.getByRole("button", { name: i18n.t("ui.kb01.action.approve") }));
    const review = fetcher.mock.calls.find(([path]) => String(path).endsWith("/alignment/review"));
    expect(JSON.parse(String(review?.[1]?.body))).toEqual({
      expected_record_version: 1, action: "APPROVE", reason: "Synthetic review",
    });
  });
});
