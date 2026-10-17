import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../../i18n";
import { AdminClient } from "../admin/client";
import type { FetchPort } from "../admin/contracts";
import { KnowledgeManagementClient } from "./client";
import { TaxonomyTree } from "./TaxonomyTree";

describe("published jurisdiction hierarchy", () => {
  it("lazily reads canonical children and passes their identity to the document filter", async () => {
    await i18n.changeLanguage("en-US");
    const fetcher = vi.fn<FetchPort>().mockImplementation(async (path) => {
      const url = new URL(String(path), "http://test.invalid");
      const child = url.searchParams.get("parent_definition_id") === "region-id";
      return new Response(JSON.stringify({
        parent_definition_id: child ? "region-id" : null,
        total: 1, page: 1, page_size: 25,
        items: [{ definition_id: child ? "country-id" : "region-id",
          version_id: child ? "country-version" : "region-version",
          parent_definition_id: child ? "region-id" : null,
          kind: "JURISDICTION_CONFIG", code: child ? "SYNTH_COUNTRY" : "SYNTH_REGION",
          display_name: child ? "Synthetic country" : "Synthetic region",
          child_count: child ? 0 : 1 }],
      }), { headers: { "Content-Type": "application/json" } });
    });
    const select = vi.fn();
    render(<TaxonomyTree client={new KnowledgeManagementClient(new AdminClient(fetcher))}
      selected={["country-id"]} onSelect={select} />);
    await screen.findByRole("button", { name: "Synthetic region" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: /Expand or collapse/ }));
    const country = await screen.findByRole("button", { name: "Synthetic country" });
    expect(country).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(country);
    expect(select).toHaveBeenCalledWith(expect.objectContaining({
      definition_id: "country-id", version_id: "country-version", parent_definition_id: "region-id",
    }));
    expect(fetcher.mock.calls.every(([path]) => String(path).includes("locale=en-US"))).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: /Expand or collapse/ }));
    expect(screen.queryByRole("button", { name: "Synthetic country" })).not.toBeInTheDocument();
  });

  it("does not truncate the root hierarchy to its first page", async () => {
    await i18n.changeLanguage("en-US");
    const fetcher = vi.fn<FetchPort>().mockImplementation(async (path) => {
      const second = String(path).includes("page=2");
      return new Response(JSON.stringify({
        parent_definition_id: null, total: 26, page: second ? 2 : 1, page_size: 25,
        items: [{ definition_id: second ? "last" : "first", version_id: "version",
          parent_definition_id: null, kind: "JURISDICTION_CONFIG", code: "SYNTH",
          display_name: second ? "Last country" : "First country", child_count: 0 }],
      }), { headers: { "Content-Type": "application/json" } });
    });
    render(<TaxonomyTree client={new KnowledgeManagementClient(new AdminClient(fetcher))}
      selected={[]} onSelect={vi.fn()} />);
    await screen.findByRole("button", { name: "First country" });
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByRole("button", { name: "Last country" });
    expect(screen.getByText("2 / 2")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });
});
