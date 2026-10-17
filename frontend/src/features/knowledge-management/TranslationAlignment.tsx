import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { KnowledgeManagementClient, Schema } from "./client";

type Props = {
  client: KnowledgeManagementClient;
  source: Schema<"ManagedKnowledgeVersionView">;
  can: (operation: string) => boolean;
};

export function TranslationAlignment({ client, source, can }: Props) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [documentPage, setDocumentPage] = useState(1);
  const [documents, setDocuments] = useState<Schema<"ManagedKnowledgeDocumentPage">>();
  const [documentId, setDocumentId] = useState("");
  const [targetVersions, setTargetVersions] = useState<Schema<"ManagedKnowledgeVersionView">[]>([]);
  const [target, setTarget] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const [targetPage, setTargetPage] = useState(1);
  const [sourcePreview, setSourcePreview] = useState<Schema<"KnowledgeDocumentPreview">>();
  const [targetPreview, setTargetPreview] = useState<Schema<"KnowledgeDocumentPreview">>();
  const [sourceNode, setSourceNode] = useState("");
  const [targetNode, setTargetNode] = useState("");
  const [alignments, setAlignments] = useState<Schema<"TranslationAlignmentPage">>();
  const [alignmentPage, setAlignmentPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const abort = new AbortController();
    const fail = (e: unknown) => { if (!abort.signal.aborted) setError(String(e)); };
    client.get<Schema<"TranslationAlignmentPage">>(
      `/documents/versions/${source.knowledge_version_id}/translation-alignments?page=${alignmentPage}`, abort.signal,
    ).then(setAlignments).catch(fail);
    if (can("translation:write") && can("document:read")) {
      client.get<Schema<"ManagedKnowledgeDocumentPage">>(`/documents?${new URLSearchParams({
        query, page: String(documentPage), page_size: "25",
      })}`, abort.signal).then(setDocuments).catch(fail);
      client.get<Schema<"KnowledgeDocumentPreview">>(
        `/documents/versions/${source.knowledge_version_id}/preview?page=${sourcePage}`, abort.signal,
      ).then(setSourcePreview).catch(fail);
    }
    return () => abort.abort();
  }, [client, source.knowledge_version_id, sourcePage, query, documentPage, alignmentPage, revision, can]);
  useEffect(() => {
    if (!documentId) return;
    const abort = new AbortController();
    client.get<Schema<"ManagedKnowledgeDocumentDetail">>(`/documents/${documentId}`, abort.signal)
      .then((detail) => setTargetVersions(detail.versions.filter((version) =>
        version.content_hash && !["DRAFT", "ARCHIVED"].includes(version.lifecycle)
        && version.language !== source.language)))
      .catch((e) => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, [client, documentId, source.language]);
  useEffect(() => {
    if (!target) return;
    const abort = new AbortController();
    client.get<Schema<"KnowledgeDocumentPreview">>(`/documents/versions/${target}/preview?page=${targetPage}`, abort.signal)
      .then(setTargetPreview).catch((e) => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, [client, target, targetPage]);
  const run = async (work: () => Promise<unknown>) => {
    setPending(true); setError("");
    try { await work(); setRevision((old) => old + 1); }
    catch (e) { setError(String(e)); }
    finally { setPending(false); }
  };
  const nodeSelect = (label: string, preview: typeof sourcePreview, value: string,
    setValue: (value: string) => void, page: number, setPage: (page: number) => void) => <div>
    <label>{label}<select value={value} onChange={(e) => setValue(e.target.value)}>
      <option value="">{t("ui.kb01.select")}</option>
      {preview?.items.map((node) => <option key={node.structure_node_id} value={node.structure_node_id}>
        {node.canonical_locator} — {node.original_excerpt.slice(0, 120)}</option>)}
    </select></label>
    {preview && <div>
      <button type="button" disabled={page === 1} onClick={() => { setValue(""); setPage(page - 1); }}>{t("ui.kb01.previous")}</button>
      <span>{page}</span>
      <button type="button" disabled={page * preview.page_size >= preview.total}
        onClick={() => { setValue(""); setPage(page + 1); }}>{t("ui.kb01.next")}</button>
    </div>}
    {preview?.items.filter((node) => node.structure_node_id === value).map((node) => <div key={node.structure_node_id} dir="auto">
      <p>{node.original_excerpt}</p><p>{t("ui.kb01.citation")}: {node.citation_id}</p>
    </div>)}
  </div>;
  return <section aria-label={t("ui.kb01.translationAlignment")}>
    <h4>{t("ui.kb01.translationAlignment")}</h4>
    <p>{t("ui.kb01.translationBoundary")}</p>
    {error && <p role="alert">{error}</p>}
    <label>{t("ui.kb01.reason")}<input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2048} /></label>
    {can("translation:write") && can("document:read") && <form onSubmit={(e) => {
      e.preventDefault();
      const targetVersion = targetVersions.find((version) => version.knowledge_version_id === target);
      if (!targetVersion) return;
      void run(() => client.mutate("/translation-alignments", {
        source_version_id: source.knowledge_version_id, target_version_id: target,
        expected_source_record_version: source.record_version,
        expected_target_record_version: targetVersion.record_version,
        translation_method: "HUMAN", pairs: [{ source_node_id: sourceNode, target_node_id: targetNode }], reason,
      }));
    }}>
      <label>{t("ui.kb01.search")}<input value={query} onChange={(e) => {
        setQuery(e.target.value); setDocumentPage(1);
      }} /></label>
      <label>{t("ui.kb01.translationDocument")}<select value={documentId} onChange={(e) => {
        setDocumentId(e.target.value); setTargetVersions([]); setTarget(""); setTargetPreview(undefined); setTargetNode("");
      }}><option value="">{t("ui.kb01.select")}</option>
        {documents?.items.map((doc) => <option key={doc.document_id} value={doc.document_id}>{doc.display_name}</option>)}
      </select></label>
      {documents && <div>
        <button type="button" disabled={documentPage === 1} onClick={() => setDocumentPage(documentPage - 1)}>{t("ui.kb01.previous")}</button>
        <span>{documentPage}</span>
        <button type="button" disabled={documentPage * documents.page_size >= documents.total}
          onClick={() => setDocumentPage(documentPage + 1)}>{t("ui.kb01.next")}</button>
      </div>}
      <label>{t("ui.kb01.translationVersion")}<select value={target} onChange={(e) => {
        setTarget(e.target.value); setTargetPage(1); setTargetPreview(undefined); setTargetNode("");
      }}><option value="">{t("ui.kb01.select")}</option>
        {targetVersions.map((version) => <option key={version.knowledge_version_id} value={version.knowledge_version_id}>
          {version.language} · {version.version} · {version.lifecycle}</option>)}
      </select></label>
      {nodeSelect(t("ui.kb01.originalClause"), sourcePreview, sourceNode, setSourceNode, sourcePage, setSourcePage)}
      {nodeSelect(t("ui.kb01.translatedClause"), targetPreview, targetNode, setTargetNode, targetPage, setTargetPage)}
      <button type="submit" disabled={pending || !reason || !sourceNode || !targetNode}>{t("ui.kb01.submitAlignment")}</button>
    </form>}
    <ul>{alignments?.items.map((row) => <li key={row.translation_id}>
      <p>{row.source_language} → {row.target_language} · {row.review_status}</p>
      <p>{row.submitted_by} · {row.submitted_at} · {row.reviewer} · {row.reviewed_at}</p>
      <p>{row.reason} · {row.review_reason}</p>
      <ul>{row.pairs.map((pair) => <li key={`${pair.source_node_id}:${pair.target_node_id}`}>
        {pair.source_locator} → {pair.target_locator}<p>{pair.source_citation_id} / {pair.target_citation_id}</p>
      </li>)}</ul>
      {row.review_status === "PENDING" && ["APPROVE", "REJECT"].map((action) => <button key={action}
        disabled={pending || !reason || !can("translation:approve")}
        onClick={() => void run(() => client.mutate(`/translation-alignments/${row.translation_id}/review`, {
          expected_record_version: row.record_version, action, reason,
        }))}>{t(`ui.kb01.action.${action === "APPROVE" ? "approve" : "reject"}`)}</button>)}
    </li>)}</ul>
    {alignments && alignments.total > alignments.page_size && <div>
      <button type="button" disabled={alignmentPage === 1} onClick={() => setAlignmentPage(alignmentPage - 1)}>{t("ui.kb01.previous")}</button>
      <span>{alignmentPage}</span>
      <button type="button" disabled={alignmentPage * alignments.page_size >= alignments.total}
        onClick={() => setAlignmentPage(alignmentPage + 1)}>{t("ui.kb01.next")}</button>
    </div>}
  </section>;
}
