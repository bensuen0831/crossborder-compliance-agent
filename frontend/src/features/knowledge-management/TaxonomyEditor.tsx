import { useState } from "react";
import { useTranslation } from "react-i18next";
import { KnowledgeManagementClient, mutation } from "./client";
import type { Schema } from "./client";

type Detail = Schema<"TaxonomyDetail">;
type Row = Schema<"TaxonomyView">;
export function TaxonomyEditor({
  row,
  choices,
  client,
  can,
  reason,
  refreshed,
}: {
  row: Detail;
  choices: Row[];
  client: KnowledgeManagementClient;
  can: (operation: string) => boolean;
  reason: string;
  refreshed: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const payload = row.payload as Schema<"TaxonomyPayload">;
  const [aliases, setAliases] = useState((payload.aliases ?? []).join("\n"));
  const [names, setNames] = useState<Record<string, string>>({
    ...payload.localized_display?.localized_display_names,
  });
  const [parent, setParent] = useState(payload.parent_definition_id ?? "");
  const [merge, setMerge] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [impact, setImpact] = useState<Schema<"TaxonomyImpact">>();
  const [aliasesView, setAliasesView] = useState<Schema<"TaxonomyAliases">>();
  const current = row.versions.find(
    (version) => version.version_id === row.version_id,
  );
  const draft = current?.lifecycle_status === "DRAFT";
  const run = async (work: () => Promise<void>) => {
    setPending(true);
    setError("");
    try {
      await work();
      await refreshed();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  };
  return (
    <div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            const body = {
              ...mutation(
                draft ? current.record_version : row.record_version,
                reason,
              ),
              payload: {
                ...payload,
                aliases: aliases
                  .split("\n")
                  .map((value) => value.trim())
                  .filter(Boolean),
                parent_definition_id: parent || null,
                localized_display: {
                  localized_display_names: Object.fromEntries(
                    Object.entries(names).filter(([, value]) => value.trim()),
                  ),
                  fallback_locale:
                    payload.localized_display?.fallback_locale ?? "en-US",
                },
              },
            };
            await client.mutate(
              draft
                ? `/taxonomy/versions/${current.version_id}`
                : `/taxonomy/${row.definition_id}/versions`,
              body,
              draft ? "PATCH" : "POST",
            );
          });
        }}
      >
        {(["zh-CN", "zh-HK", "en-US"] as const).map((locale) => (
          <label key={locale}>
            {t("ui.kb01.name")} ({locale})
            <input
              value={names[locale] ?? ""}
              onChange={(e) => setNames({ ...names, [locale]: e.target.value })}
              maxLength={400}
            />
          </label>
        ))}
        <label>
          {t("ui.kb01.aliases")}
          <textarea
            value={aliases}
            onChange={(e) => setAliases(e.target.value)}
          />
        </label>
        <label>
          {t("ui.kb01.parent")}
          <select value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">{t("ui.kb01.noParent")}</option>
            {choices
              .filter(
                (item) =>
                  item.kind === row.kind &&
                  item.definition_id !== row.definition_id,
              )
              .map((item) => (
                <option key={item.definition_id} value={item.definition_id}>
                  {item.display_name}
                </option>
              ))}
          </select>
        </label>
        <button disabled={pending || !can("taxonomy:write") || !reason}>
          {t(draft ? "ui.kb01.saveMetadata" : "ui.kb01.newVersion")}
        </button>
      </form>
      <div className="actions">
        <button
          disabled={!can("taxonomy:read") || pending}
          onClick={() =>
            void run(async () => {
              setImpact(
                await client.get(`/taxonomy/${row.definition_id}/impact`),
              );
              setAliasesView(
                await client.get(`/taxonomy/${row.definition_id}/aliases`),
              );
            })
          }
        >
          {t("ui.kb01.impact")}
        </button>
        <button
          disabled={
            !can("taxonomy:delete") ||
            pending ||
            !reason ||
            !impact?.eligible_draft
          }
          onClick={() =>
            void run(async () => {
              await client.mutate(
                `/taxonomy/${row.definition_id}`,
                mutation(row.record_version, reason),
                "DELETE",
              );
            })
          }
        >
          {t("ui.kb01.deleteDraft")}
        </button>
      </div>
      {impact && (
        <dl>
          <dt>{t("ui.kb01.protectedReferences")}</dt>
          {Object.entries(impact.references).map(([key, value]) => (
            <dd key={key}>
              {key}: {value}
            </dd>
          ))}
        </dl>
      )}
      {aliasesView && (
        <ul>
          {aliasesView.targets.map((target) => (
            <li key={target.definition_id}>{target.display_name}</li>
          ))}
        </ul>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            const target = choices.find((item) => item.definition_id === merge);
            if (!target) return;
            await client.mutate(`/taxonomy/${row.definition_id}/merge`, {
              ...mutation(row.record_version, reason),
              target_definition_id: target.definition_id,
              expected_target_record_version: target.record_version,
            });
          });
        }}
      >
        <label>
          {t("ui.kb01.mergeTarget")}
          <select
            value={merge}
            onChange={(e) => setMerge(e.target.value)}
            required
          >
            <option value="">{t("ui.kb01.select")}</option>
            {choices
              .filter(
                (item) =>
                  item.kind === row.kind &&
                  item.definition_id !== row.definition_id,
              )
              .map((item) => (
                <option key={item.definition_id} value={item.definition_id}>
                  {item.display_name}
                </option>
              ))}
          </select>
        </label>
        <p>{t("ui.kb01.mergeHint")}</p>
        <button
          disabled={pending || !can("taxonomy:write") || !reason || !merge}
        >
          {t("ui.kb01.proposeMerge")}
        </button>
      </form>
    </div>
  );
}
