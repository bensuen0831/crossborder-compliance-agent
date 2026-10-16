import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../../i18n";
import { AdminClient } from "../admin/client";
import type { AdminSession, FetchPort } from "../admin/contracts";
import { KnowledgeManagement } from "./KnowledgeManagement";

const session: AdminSession = {
  tenantId: "tenant",
  actorId: "author",
  roles: [],
  backendScopes: ["knowledge:admin"],
  grants: {},
};
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const originalLabel = {
  kind: "REGULATION_CATEGORY",
  definition_id: "older-category",
  version_id: "pinned-old-version",
};
const document = {
  document_id: "document-1",
  source_id: "source-1",
  display_name: "Original regulation",
  record_version: 1,
  status: "ACTIVE",
  created_at: "2026-10-15T00:00:00Z",
  updated_at: "2026-10-15T00:00:00Z",
};
const version = {
  knowledge_version_id: "version-1",
  document_id: document.document_id,
  version: 1,
  record_version: 8,
  lifecycle: "DRAFT",
  language: "ar",
  metadata: { title: document.display_name, labels: [originalLabel] },
  file_available: false,
  content_hash: null,
  effective_from: null,
  effective_to: null,
};
function transport(operations: string[]) {
  return vi.fn<FetchPort>().mockImplementation(async (path, options) => {
    const url = String(path);
    if (url.endsWith("/capabilities"))
      return response({
        operations,
        publication_requires_independent_review: true,
      });
    if (url.includes("/taxonomy?"))
      return response({ items: [], total: 0, page: 1, page_size: 100 });
    if (url.includes("/taxonomy-tree?"))
      return response({ items: [], total: 0, page: 1, page_size: 25, parent_definition_id: null });
    if (url.includes("/sources?"))
      return response({ items: [], total: 0, page: 1, page_size: 50 });
    if (url.includes("/documents?"))
      return response({ items: [document], total: 1, page: 1, page_size: 25 });
    if (url.includes("/statistics?"))
      return response({
        documents: 1,
        versions: 1,
        attached_originals: 0,
        attached_bytes: 0,
        by_classification: [],
        as_of: "2026-10-15T00:00:00Z",
      });
    if (url.endsWith("/documents/document-1"))
      return response({ ...document, versions: [version] });
    if (options?.method === "PATCH")
      return response({ ...version, record_version: 9 });
    throw new Error(`Unexpected transport request: ${url}`);
  });
}

describe("governed knowledge management UI", () => {
  it.each(["zh-CN", "zh-HK", "en-US"])(
    "renders actual scoped counts and source metadata in %s",
    async (locale) => {
      await i18n.changeLanguage(locale);
      const fetcher = transport(["document:read", "statistics:read"]);
      render(
        <KnowledgeManagement
          client={new AdminClient(fetcher)}
          session={session}
        />,
      );
      await screen.findByRole("button", { name: /Original regulation/ });
      expect(
        screen.getByRole("region", { name: i18n.t("ui.kb01.statistics") }),
      ).toHaveTextContent("0");
      expect(
        fetcher.mock.calls.some(([url]) =>
          String(url).includes("/statistics?"),
        ),
      ).toBe(true);
      await userEvent.click(
        screen.getByRole("button", { name: /Original regulation/ }),
      );
      await screen.findByText("document-1");
      expect(
        screen.getByRole("button", { name: i18n.t("ui.kb01.deleteDraft") }),
      ).toBeDisabled();
    },
  );
  it("does not infer operation permission from a legacy coarse admin scope", async () => {
    const fetcher = transport([]);
    render(
      <KnowledgeManagement
        client={new AdminClient(fetcher)}
        session={session}
      />,
    );
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(
      screen.getByRole("button", { name: i18n.t("ui.kb01.createDocument") }),
    ).toBeDisabled();
    expect(
      fetcher.mock.calls.some(([url]) => String(url).includes("/documents?")),
    ).toBe(false);
  });
  it("edits metadata with CAS and preserves exact labels absent from the first options page", async () => {
    const fetcher = transport(["document:read", "document:write"]);
    render(
      <KnowledgeManagement
        client={new AdminClient(fetcher)}
        session={session}
      />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /Original regulation/ }),
    );
    await userEvent.type(
      screen.getByLabelText(i18n.t("ui.kb01.reason")),
      "Correct display title",
    );
    await userEvent.click(
      await screen.findByRole("button", {
        name: i18n.t("ui.kb01.editMetadata"),
      }),
    );
    const title = screen.getByLabelText(i18n.t("ui.kb01.title"));
    await userEvent.clear(title);
    await userEvent.type(title, "Corrected display title");
    await userEvent.click(
      screen.getByRole("button", { name: i18n.t("ui.kb01.saveMetadata") }),
    );
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(([, init]) => init?.method === "PATCH"),
      ).toBe(true),
    );
    const [, options] = fetcher.mock.calls.find(
      ([, init]) => init?.method === "PATCH",
    )!;
    const body = JSON.parse(String(options?.body));
    expect(body.expected_record_version).toBe(8);
    expect(body.metadata.labels).toEqual([originalLabel]);
    expect(body.metadata.title).toBe("Corrected display title");
    expect(body).not.toHaveProperty("actor_id");
    expect(body).not.toHaveProperty("tenant_id");
  });
});

it("submits the selected taxonomy version CAS rather than the definition revision", async () => {
  const row = {
    definition_id: "category",
    kind: "REGULATION_CATEGORY",
    code: "CAT",
    display_name: "Versioned category",
    record_version: 9,
    version_id: "tax-version",
    active_version_id: null,
    lifecycle: "PENDING_REVIEW",
    enabled: true,
    payload: {},
  };
  const fetcher = vi.fn<FetchPort>().mockImplementation(async (path, init) => {
    const url = String(path);
    if (url.endsWith("/capabilities"))
      return response({ operations: ["taxonomy:read", "taxonomy:approve"] });
    if (url.includes("/taxonomy?"))
      return response({ items: [row], total: 1, page: 1, page_size: 100 });
    if (url.endsWith("/taxonomy/category"))
      return response({
        ...row,
        versions: [
          {
            version_id: "tax-version",
            record_version: 3,
            lifecycle_status: "PENDING_REVIEW",
            version_no: 1,
            created_by: "other-author",
            approved_by: null,
            payload: {},
          },
        ],
      });
    if (init?.method === "POST") return response({});
    throw new Error(url);
  });
  render(
    <KnowledgeManagement client={new AdminClient(fetcher)} session={session} />,
  );
  await userEvent.click(
    screen.getByRole("tab", { name: i18n.t("ui.kb01.taxonomy") }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: /Versioned category/ }),
  );
  await userEvent.type(
    screen.getByLabelText(i18n.t("ui.kb01.reason")),
    "Independent review",
  );
  await userEvent.click(
    await screen.findByRole("button", {
      name: i18n.t("ui.kb01.action.approve"),
    }),
  );
  await waitFor(() =>
    expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(
      true,
    ),
  );
  const [url, init] = fetcher.mock.calls.find(
    ([, init]) => init?.method === "POST",
  )!;
  expect(url).toContain("/taxonomy/versions/tax-version/approve");
  expect(JSON.parse(String(init?.body)).expected_record_version).toBe(3);
});

it("sends country and category together to both list and SQL statistics", async () => {
  const country = {
    definition_id: "country-definition",
    kind: "JURISDICTION_CONFIG",
    code: "SYNTHETIC-J",
    display_name: "Synthetic jurisdiction",
    active_version_id: "country-version",
    enabled: true,
  };
  const category = {
    definition_id: "category-definition",
    kind: "REGULATION_CATEGORY",
    code: "SYNTHETIC-C",
    display_name: "Synthetic category",
    active_version_id: "category-version",
    enabled: true,
  };
  const base = transport(["document:read", "statistics:read", "taxonomy:read"]);
  const fetcher = vi
    .fn<FetchPort>()
    .mockImplementation((path, init) =>
      String(path).includes("/taxonomy?")
        ? Promise.resolve(
            response({
              items: [country, category],
              total: 2,
              page: 1,
              page_size: 100,
            }),
          )
        : base(path, init),
    );
  render(
    <KnowledgeManagement client={new AdminClient(fetcher)} session={session} />,
  );
  await within(screen.getByRole('listbox', { name: i18n.t('ui.kb01.countryFilter') })).findByRole('option', { name: 'Synthetic jurisdiction' });
  await userEvent.selectOptions(
    screen.getByRole("listbox", { name: i18n.t("ui.kb01.countryFilter") }),
    country.definition_id,
  );
  await userEvent.selectOptions(
    screen.getByRole("listbox", { name: i18n.t("ui.kb01.categoryFilter") }),
    category.definition_id,
  );
  await waitFor(() => {
    for (const path of ["/documents?", "/statistics?"]) {
      expect(
        base.mock.calls.some(([url]) => {
          const target = String(url);
          return (
            target.includes(path) &&
            new URL(target, "http://test.invalid").searchParams
              .getAll("label_ids")
              .sort()
              .join(",") ===
              ["category-definition", "country-definition"].join(",")
          );
        }),
      ).toBe(true);
    }
  });


});

  it("passes the selected document order to the canonical list query", async () => {
    const fetcher = transport(["document:read"]);
    render(<KnowledgeManagement client={new AdminClient(fetcher)} session={session} />);
    await screen.findByRole("button", { name: /Original regulation/ });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: i18n.t("ui.kb01.documentSort") }), "title_asc");
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes("/documents?") && String(url).includes("sort=title_asc"))).toBe(true));
  });


it.each([true, false])("requires a server reference preview before single-document deletion (eligible=%s)", async (eligible) => {
  await i18n.changeLanguage("en-US");
  const base = transport(["document:read", "document:delete"]);
  const fetcher = vi.fn<FetchPort>().mockImplementation((path, options) => {
    if (String(path).endsWith("/impact")) return Promise.resolve(response({ document_id: document.document_id,
      references: { snapshots: eligible ? 0 : 1 }, protected_version_history: !eligible, eligible_draft: eligible }));
    if (options?.method === "DELETE") return Promise.resolve(response({ deleted: true }));
    return base(path, options);
  });
  render(<KnowledgeManagement client={new AdminClient(fetcher)} session={session} />);
  await userEvent.click(await screen.findByRole("button", { name: /Original regulation/ }));
  await userEvent.type(screen.getAllByRole("textbox", { name: i18n.t("ui.kb01.reason") })[0], "Explicit draft cleanup");
  const remove = screen.getByRole("button", { name: i18n.t("ui.kb01.deleteDraft") });
  expect(remove).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: i18n.t("ui.kb01.impact") }));
  await screen.findByText(i18n.t(eligible ? "ui.kb01.deleteEligible" : "ui.kb01.deleteProtected"));
  if (!eligible) {
    expect(remove).toBeDisabled();
    expect(fetcher.mock.calls.some(([, options]) => options?.method === "DELETE")).toBe(false);
  } else {
    await userEvent.click(remove);
    await waitFor(() => expect(fetcher.mock.calls.some(([, options]) => options?.method === "DELETE")).toBe(true));
    const sent = fetcher.mock.calls.find(([, options]) => options?.method === "DELETE")!;
    expect(JSON.parse(String(sent[1]?.body))).toEqual({ expected_record_version: 1, reason: "Explicit draft cleanup", idempotency_key: expect.any(String) });
  }
});

it("refreshes the exact document CAS and explains concurrent deletion refusal", async () => {
  await i18n.changeLanguage("en-US");
  const base = transport(["document:read", "document:delete"]);
  let attempted = false;
  const fetcher = vi.fn<FetchPort>().mockImplementation((path, options) => {
    const url = String(path);
    if (url.endsWith("/impact")) return Promise.resolve(response({ document_id: document.document_id, eligible_draft: true, protected_version_history: false, references: {} }));
    if (options?.method === "DELETE") {
      if (!attempted) { attempted = true; return Promise.resolve(response({}, 409)); }
      return Promise.resolve(response({ deleted: true }));
    }
    if (attempted && url.endsWith("/documents/document-1")) return Promise.resolve(response({ ...document, record_version: 2, versions: [version] }));
    return base(path, options);
  });
  render(<KnowledgeManagement client={new AdminClient(fetcher)} session={session} />);
  await userEvent.click(await screen.findByRole("button", { name: /Original regulation/ }));
  await userEvent.type(screen.getAllByRole("textbox", { name: i18n.t("ui.kb01.reason") })[0], "Human reviewed draft cleanup");
  await userEvent.click(screen.getByRole("button", { name: i18n.t("ui.kb01.impact") }));
  const remove = screen.getByRole("button", { name: i18n.t("ui.kb01.deleteDraft") });
  await waitFor(() => expect(remove).toBeEnabled());
  await userEvent.click(remove);
  await screen.findByText(i18n.t("ui.kb01.deleteChanged"));
  await userEvent.click(remove);
  await waitFor(() => expect(fetcher.mock.calls.filter(([, options]) => options?.method === "DELETE")).toHaveLength(2));
  expect(fetcher.mock.calls.filter(([, options]) => options?.method === "DELETE").map(([, options]) => JSON.parse(String(options?.body)).expected_record_version)).toEqual([1, 2]);
});
