import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { idempotencyKey, type KnowledgeManagementClient, type Schema } from "./client";
import { transferFile } from "./uploads";

type Row = Schema<"KnowledgeManifestRecordView">;
type Dimension = "language" | "category" | "jurisdiction" | "topic" | "issuer";
const fields = ["sequence", "title", "language", "category", "jurisdiction", "topic", "issuer", "format", "relative_path"] as const;
const dimensions: Record<Dimension, string> = {
  language: "LANGUAGE", category: "REGULATION_CATEGORY", jurisdiction: "JURISDICTION_CONFIG",
  topic: "RESEARCH_TOPIC", issuer: "ISSUING_AUTHORITY",
};
type Mapping = { dimension: Dimension; source_value: string; labels: Schema<"KnowledgeDocumentLabel">[] };

export function ManifestPanel({ client, batch, labels, can, scope, onUse }: {
  client: KnowledgeManagementClient;
  batch: Schema<"KnowledgeBatchView">;
  labels: Schema<"TaxonomyView">[];
  can: (operation: string) => boolean;
  scope: string;
  onUse: (row: Row) => void;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File>();
  const [upload, setUpload] = useState<Schema<"KnowledgeUploadView">>();
  const [columns, setColumns] = useState<Record<string, string>>({});
  const [sheet, setSheet] = useState("");
  const [encoding, setEncoding] = useState("utf-8-sig");
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [selected, setSelected] = useState("");
  const [history, setHistory] = useState<Schema<"KnowledgeManifestPage">>();
  const [historyPage, setHistoryPage] = useState(1);
  const [detail, setDetail] = useState<Schema<"KnowledgeManifestDetail">>();
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [mappings, setMappings] = useState<Record<string, Mapping>>({});
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const abort = new AbortController();
    client.get<Schema<"KnowledgeManifestPage">>(`/import-batches/${batch.batch_id}/manifests?page=${historyPage}`, abort.signal)
      .then(setHistory).catch((e) => { if (!abort.signal.aborted) setError(String(e)); });
    if (selected) client.get<Schema<"KnowledgeManifestDetail">>(
      `/import-batches/${batch.batch_id}/manifests/${selected}?page=${page}`, abort.signal,
    ).then(setDetail).catch((e) => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, [client, batch.batch_id, historyPage, selected, page, revision]);
  const uploadId = upload?.upload_session_id;
  const uploadStatus = upload?.status;
  useEffect(() => {
    if (!uploadId || !["QUEUED_SCAN", "SCANNING", "FINALIZING"].includes(uploadStatus ?? "")) return;
    const abort = new AbortController();
    const timer = setInterval(() => {
      client.get<Schema<"KnowledgeUploadView">>(`/upload-sessions/${uploadId}`, abort.signal)
        .then(setUpload).catch((e) => { if (!abort.signal.aborted) setError(String(e)); });
    }, 1500);
    return () => { clearInterval(timer); abort.abort(); };
  }, [client, uploadId, uploadStatus]);
  const run = async (work: () => Promise<void>) => {
    setError(""); setPending(true);
    try { await work(); } catch (e) { setError(String(e)); } finally { setPending(false); }
  };
  return <section className="panel" aria-label={t("ui.kb01.manifest")}>
    <h4>{t("ui.kb01.manifest")}</h4><p>{t("ui.kb01.manifestBoundary")}</p>
    {error && <p role="alert">{error}</p>}
    <label>{t("ui.kb01.manifestFile")}<input type="file" accept=".csv,.xlsx" disabled={pending}
      onChange={(e) => { setFile(e.target.files?.[0]); setUpload(undefined); }} /></label>
    <button type="button" disabled={pending || !file || !can("upload:create") || !can("upload:complete")}
      onClick={() => void run(async () => {
        if (!file) return;
        controller.current?.abort(); controller.current = new AbortController();
        const row = await transferFile(client, file, scope, controller.current.signal, (current, phase, bytes) => {
          if (current) setUpload(current); setProgress(`${t(`ui.kb01.${phase}`)} · ${bytes.toLocaleString()}`);
        });
        setUpload(row);
      })}>{t("ui.kb01.startResume")}</button>
    <button type="button" disabled={!pending} onClick={() => controller.current?.abort()}>{t("ui.kb01.pause")}</button>
    <p role="status">{progress} · {upload?.status} · {upload?.error_code}</p>
    <form onSubmit={(e) => {
      e.preventDefault();
      void run(async () => {
        if (!upload) return;
        const result = await client.mutate<Schema<"KnowledgeManifestView">>(`/import-batches/${batch.batch_id}/manifests`, {
          upload_session_id: upload.upload_session_id, expected_record_version: batch.record_version,
          columns: Object.fromEntries(Object.entries(columns).filter(([, value]) => value.trim())),
          required_fields: ["title", "relative_path"], metadata_mappings: Object.values(mappings).filter((mapping) => mapping.labels.length),
          sheet_name: sheet || null, csv_encoding: encoding, idempotency_key: idempotencyKey(),
        });
        setDetail(undefined); setSelected(result.manifest_id); setPage(1); setRevision((old) => old + 1);
      });
    }}>
      <p>{t("ui.kb01.manifestColumnMapping")}</p>
      {fields.map((field) => <label key={field}>{t(`ui.kb01.manifestField.${field}`)}<input
        value={columns[field] ?? ""} maxLength={128} required={["title", "relative_path"].includes(field)}
        onChange={(e) => setColumns({ ...columns, [field]: e.target.value })} /></label>)}
      <label>{t("ui.kb01.manifestSheet")}<input value={sheet} maxLength={128} onChange={(e) => setSheet(e.target.value)} /></label>
      <label>{t("ui.kb01.manifestEncoding")}<select value={encoding} onChange={(e) => setEncoding(e.target.value)}>
        {["utf-8-sig", "utf-8", "utf-16", "gb18030"].map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <button type="submit" disabled={pending || upload?.status !== "VERIFIED" || batch.status !== "PREVIEW" || !can("batch:manifest-import")}>{t("ui.kb01.manifestPrepare")}</button>
    </form>
    <label>{t("ui.kb01.manifestHistory")}<select value={selected} onChange={(e) => { setDetail(undefined); setSelected(e.target.value); setPage(1); }}>
      <option value="">{t("ui.kb01.select")}</option>
      {selected && !history?.items.some((row) => row.manifest_id === selected) && <option value={selected}>{selected}</option>}
      {history?.items.map((row) => <option key={row.manifest_id} value={row.manifest_id}>{row.created_at} · {row.status} · {row.record_count}</option>)}
    </select></label>
    {history && history.total > history.page_size && <div>
      <button type="button" disabled={historyPage === 1} onClick={() => setHistoryPage(historyPage - 1)}>{t("ui.kb01.previous")}</button>
      <span>{historyPage}</span><button type="button" disabled={historyPage * history.page_size >= history.total}
        onClick={() => setHistoryPage(historyPage + 1)}>{t("ui.kb01.next")}</button>
    </div>}
    {detail && <div>
      <p>{detail.status} · {detail.error_code} · {detail.created_by} · {detail.created_at}</p>
      <p>{t("ui.kb01.total", { count: detail.total })}</p>
      <button type="button" disabled={pending || !can("batch:manifest-export")} onClick={() => void run(async () => {
        const results: Schema<"KnowledgeManifestMissingFiles">[] = [];
        for (let current = 1; current <= 1000; current++) {
          const result = await client.get<Schema<"KnowledgeManifestMissingFiles">>(`/import-batches/${batch.batch_id}/manifests/${selected}/missing-files?page=${current}&page_size=100`);
          results.push(result);
          if (current * result.page_size >= Math.max(result.total, result.unlisted_total)) break;
          if (current === 1000 || (!result.items.length && !result.unlisted_files.length)) throw new Error("MANIFEST_EXPORT_LIMIT");
        }
        const url = URL.createObjectURL(new Blob([JSON.stringify(results, null, 2)], { type: "application/json" }));
        const anchor = document.createElement("a"); anchor.href = url; anchor.download = `manifest-${selected}.json`;
        anchor.click(); URL.revokeObjectURL(url);
      })}>{t("ui.kb01.manifestMissingReport")}</button>
      <ul>{detail.items.map((row) => <li key={row.manifest_record_id}>
        <p>{row.row_number} · {row.proposed_values.title} · {row.canonical_path} · {row.status}</p>
        <ul>{row.issues.map((issue, index) => <li key={index}>{issue.field} · {issue.code}</li>)}</ul>
        {row.issues.filter((issue) => issue.code === "METADATA_MAPPING_REQUIRED" && issue.field in dimensions).map((issue) => {
          const dimension = issue.field as Dimension;
          const value = row.proposed_values[dimension];
          const key = dimension + "\0" + value;
          return <label key={dimension}>{t(`ui.kb01.manifestField.${dimension}`)} · {value}<select multiple
            value={mappings[key]?.labels.map((label) => label.definition_id) ?? []}
            onChange={(e) => setMappings({ ...mappings, [key]: { dimension, source_value: value,
              labels: Array.from(e.target.selectedOptions, (option) => labels.find((label) => label.definition_id === option.value)!)
                .map((label) => ({ kind: label.kind, definition_id: label.definition_id, version_id: label.active_version_id! })) } })}>
            {labels.filter((label) => label.kind === dimensions[dimension] && label.active_version_id && label.lifecycle === "ACTIVE" && label.enabled)
              .map((label) => <option key={label.definition_id} value={label.definition_id}>{label.display_name}</option>)}
          </select></label>;
        })}
        <button type="button" disabled={row.status !== "FILE_MATCHED" || !row.matched_item_id || batch.status !== "PREVIEW" || !can("batch:confirm")}
          onClick={() => onUse(row)}>{t("ui.kb01.manifestUseProposal")}</button>
      </li>)}</ul>
      <button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>{t("ui.kb01.previous")}</button>
      <span>{page}</span><button type="button" disabled={page * detail.page_size >= detail.total}
        onClick={() => setPage(page + 1)}>{t("ui.kb01.next")}</button>
    </div>}
  </section>;
}
