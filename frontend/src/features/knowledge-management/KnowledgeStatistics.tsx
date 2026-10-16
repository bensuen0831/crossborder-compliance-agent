import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { KnowledgeManagementClient, Schema } from "./client";

export function KnowledgeStatistics({ client, statistics, filters }: {
  client: KnowledgeManagementClient;
  statistics: Schema<"KnowledgeStatisticsView">;
  filters: string;
}) {
  const { t } = useTranslation();
  const [dimension, setDimension] = useState("");
  const [page, setPage] = useState(1);
  const [cells, setCells] = useState<Schema<"KnowledgeCrossTabView">>();
  const [error, setError] = useState("");
  useEffect(() => {
    if (!dimension) return;
    const abort = new AbortController();
    const query = new URLSearchParams(filters);
    query.delete("sort"); query.set("dimension", dimension); query.set("page", String(page)); query.set("page_size", "50");
    client.get<Schema<"KnowledgeCrossTabView">>(`/statistics/cross-tab?${query}`, abort.signal)
      .then((value) => { if (!abort.signal.aborted) { setCells(value); setError(""); } })
      .catch((e) => { if (!abort.signal.aborted) { setCells(undefined); setError(e instanceof Error ? e.message : String(e)); } });
    return () => abort.abort();
  }, [client, filters, dimension, page, statistics.as_of]);
  return <div>
    <p>{t("ui.kb01.statisticsSemantics")}</p>
    <dl className="checks">
      {["DRAFT", "INGESTED", "VALIDATED", "PENDING_REVIEW", "APPROVED", "ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"].map((key) => [key, statistics.version_lifecycle_counts?.[key] ?? 0] as const).map(([key, value]) => <div key={key}><dt>{t("ui.kb01.version")} · {key}</dt><dd>{value.toLocaleString()}</dd></div>)}
      {Object.entries({ COMPLETED: 0, FAILED: 0, ...statistics.parse_status }).map(([key, value]) => <div key={key}><dt>{t("ui.kb01.parseRuns")} · {key}</dt><dd>{value.toLocaleString()}</dd></div>)}
    </dl>
    <h4>{t("ui.kb01.importInventory")}</h4>
    <p>{t("ui.kb01.importInventoryScope")}</p>
    {statistics.import_inventory ? <dl className="checks">{(["manifest_records", "missing_manifest_files", "verified_uploads", "verified_upload_bytes"] as const).map((key) => <div key={key}>
      <dt>{t(`ui.kb01.${key}`)}</dt><dd>{statistics.import_inventory![key].toLocaleString()}</dd>
    </div>)}</dl> : <p>{t("ui.kb01.importInventoryRestricted")}</p>}
    {(["by_language", "by_format"] as const).map((dimension) => <section key={dimension} aria-label={t(`ui.kb01.${dimension}`)}>
      <h4>{t(`ui.kb01.${dimension}`)}</h4><ul>{statistics[dimension]?.map((group) => <li key={group.key}>{group.key}: {group.documents.toLocaleString()}</li>)}</ul>
    </section>)}
    {statistics.classification_groups_truncated && <p>{t("ui.kb01.statisticsTruncated")}</p>}
    <label>{t("ui.kb01.crossTab")}<select value={dimension} onChange={(e) => { setDimension(e.target.value); setPage(1); setCells(undefined); }}>
      <option value="">{t("ui.kb01.chooseCrossTab")}</option>
      {["category", "topic", "language", "format", "status", "source"].map((key) => <option key={key} value={key}>{t(`ui.kb01.crossTab.${key}`)}</option>)}
    </select></label>
    {cells && <section aria-label={t("ui.kb01.crossTabResults")}>
      <p>{t("ui.kb01.crossTabScope")}</p><time>{cells.as_of}</time>
      <table><thead><tr><th>{t("ui.kb01.countryFilter")}</th><th>{t(`ui.kb01.crossTab.${cells.dimension}`)}</th><th>{t("ui.kb01.documents")}</th></tr></thead>
        <tbody>{cells.items.map((row) => <tr key={row.jurisdiction_id + ":" + row.value}><td>{row.jurisdiction_code}</td><td>{row.value}</td><td>{row.documents.toLocaleString()}</td></tr>)}</tbody>
      </table>
      <p>{t("ui.kb01.total", { count: cells.total })}</p>
      <button disabled={page <= 1} onClick={() => setPage((old) => old - 1)}>{t("ui.kb01.previous")}</button>
      <span>{page}</span><button disabled={page * cells.page_size >= cells.total} onClick={() => setPage((old) => old + 1)}>{t("ui.kb01.next")}</button>
    </section>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
