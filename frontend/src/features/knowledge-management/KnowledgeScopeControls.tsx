import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { idempotencyKey, mutation, type KnowledgeManagementClient, type Schema } from "./client";

const dimensions = ["jurisdiction", "jurisdiction_group", "product_domain", "product_category", "product_family", "product", "product_tag", "scenario", "industry", "data_category"] as const;
export function KnowledgeScopeControls({ client, version, can, refreshed, onQueued }: {
  client: KnowledgeManagementClient;
  version: Schema<"ManagedKnowledgeVersionView">;
  can: (operation: string) => boolean;
  refreshed: () => Promise<void>;
  onQueued: (batchId: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [read, setRead] = useState<Schema<"ManagedKnowledgeBindings">>();
  const [scope, setScope] = useState("");
  const [dimension, setDimension] = useState<(typeof dimensions)[number]>("jurisdiction");
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [known, setKnown] = useState<Record<string, Schema<"KnowledgeScopeOption">>>({});
  const [options, setOptions] = useState<Schema<"KnowledgeScopeOptions">>();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [permissionScopes, setPermissionScopes] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [effectiveTo, setEffectiveTo] = useState("");
  const run = async (work: () => Promise<void>) => {
    setPending(true); setError("");
    try { await work(); await refreshed(); } catch (e) { setError(String(e)); } finally { setPending(false); }
  };
  const runtimeStatus = read?.runtime_readiness?.status;
  useEffect(() => {
    const abort = new AbortController();
    const load = () => client.get<Schema<"ManagedKnowledgeBindings">>(
      `/documents/versions/${version.knowledge_version_id}/scope-bindings`, abort.signal,
    ).then(setRead).catch((e) => { if (!abort.signal.aborted) setError(String(e)); });
    void load();
    const timer = runtimeStatus && ["PENDING", "BUILDING"].includes(runtimeStatus) ? setInterval(() => void load(), 3000) : undefined;
    return () => { abort.abort(); if (timer) clearInterval(timer); };
  }, [client, version.knowledge_version_id, version.record_version, runtimeStatus]);
  useEffect(() => {
    if (!can("document:bind")) return;
    const abort = new AbortController();
    client.get<Schema<"KnowledgeScopeOptions">>(`/scope-options?${new URLSearchParams({ dimension, query, page: String(page), page_size: "50" })}`, abort.signal)
      .then((value) => { setOptions(value); setKnown((old) => {
        const keep = new Set(Object.values(selected).flat());
        return { ...Object.fromEntries(Object.entries(old).filter(([id]) => keep.has(id))),
          ...Object.fromEntries(value.items.map((row) => [row.object_id, row])) };
      }); }).catch((e) => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, [client, can, dimension, query, page, selected]);
  const draft = ["DRAFT", "INGESTED"].includes(version.lifecycle);
  return <section aria-label={t("ui.kb01.scopeBindings")}>
    <h4>{t("ui.kb01.scopeBindings")}</h4><p>{t("ui.kb01.scopeBoundary")}</p>
    {error && <p role="alert">{error}</p>}
    <label>{t("ui.kb01.reason")}<input value={reason} maxLength={2048} onChange={(e) => setReason(e.target.value)} /></label>
    {draft && can("document:bind") && <form onSubmit={(e) => {
      e.preventDefault(); void run(async () => {
        await client.mutate(`/documents/versions/${version.knowledge_version_id}/scope-bindings`, {
          ...mutation(version.record_version, reason), scope_type: scope,
          dimensions: Object.fromEntries(Object.entries(selected).filter(([, values]) => values.length)),
          permission_scopes: permissionScopes.split("\n").map((value) => value.trim()).filter(Boolean),
          effective_from: effectiveFrom || null, effective_to: effectiveTo || null,
        });
      });
    }}>
      <label>{t("ui.kb01.scopeType")}<select required value={scope} onChange={(e) => setScope(e.target.value)}>
        <option value="">{t("ui.kb01.select")}</option>
        {["PRODUCT_SPECIFIC", "DOMAIN_SHARED", "CROSS_PRODUCT", "GLOBAL"].map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <label>{t("ui.kb01.scopeDimension")}<select value={dimension} onChange={(e) => {
        setDimension(e.target.value as typeof dimension); setOptions(undefined); setPage(1); setQuery("");
      }}>{dimensions.map((value) => <option key={value} value={value}>{t(`ui.kb01.scopeDimension.${value}`)}</option>)}</select></label>
      <label>{t("ui.kb01.search")}<input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} /></label>
      <label>{t("ui.kb01.scopeReferences")}<select multiple value={selected[dimension] ?? []} onChange={(e) => {
        const visible = new Set(options?.items.map((row) => row.object_id));
        setSelected({ ...selected, [dimension]: [...(selected[dimension] ?? []).filter((id) => !visible.has(id)),
          ...Array.from(e.target.selectedOptions, (option) => option.value)] });
      }}>{options?.items.map((row) => <option key={row.object_id} value={row.object_id}>{row.display_name} · {row.code}</option>)}</select></label>
      {options && <div>
        <button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>{t("ui.kb01.previous")}</button>
        <span>{page}</span><button type="button" disabled={page * options.page_size >= options.total} onClick={() => setPage(page + 1)}>{t("ui.kb01.next")}</button>
      </div>}
      <ul>{Object.entries(selected).flatMap(([key, values]) => values.map((id) => <li key={`${key}:${id}`}>
        {t(`ui.kb01.scopeDimension.${key}`)} · {known[id]?.display_name ?? id}
        <button type="button" onClick={() => setSelected({ ...selected, [key]: values.filter((value) => value !== id) })}>{t("ui.kb01.removeSelection")}</button>
      </li>))}</ul>
      <label>{t("ui.kb01.requiredReadScopes")}<textarea value={permissionScopes} onChange={(e) => setPermissionScopes(e.target.value)} /></label>
      <label>{t("ui.kb01.effectiveFrom")}<input type="date" value={effectiveFrom} onChange={(e) => setEffectiveFrom(e.target.value)} /></label>
      <label>{t("ui.kb01.effectiveTo")}<input type="date" value={effectiveTo} onChange={(e) => setEffectiveTo(e.target.value)} /></label>
      <button type="submit" disabled={pending || !scope || !reason}>{t("ui.kb01.addScopeBinding")}</button>
    </form>}
    <ul>{read?.bindings.map((binding) => <li key={binding.binding_id}>
      {binding.scope_type} · {binding.review_status}
      <ul>{Object.entries(binding.dimensions ?? {}).map(([key, values]) => <li key={key}>{t(`ui.kb01.scopeDimension.${key}`)} · {values.join(", ")}</li>)}</ul>
    </li>)}</ul>
    <p>{t("ui.kb01.qualityGate")} · {read?.quality?.status ?? t("ui.kb01.notEvaluated")}</p>
    {read?.quality && <ul>{Object.entries(read.quality.checks).map(([key, value]) => <li key={key}>{key} · {String(value)}</li>)}</ul>}
    <p>{t("ui.kb01.runtimeReady")} · {read?.runtime_readiness?.status ?? t("ui.kb01.notEvaluated")}</p>
    {version.lifecycle === "DRAFT" && version.binary_upload_session_id && <button type="button" disabled={pending || !can("document:ingest")}
      onClick={() => void run(async () => {
        const job = await client.mutate<Schema<"KnowledgeBinaryIngestionView">>(`/versions/${version.knowledge_version_id}/binary-ingestion`, {
          binary_upload_session_id: version.binary_upload_session_id, expected_record_version: version.record_version,
          idempotency_key: idempotencyKey(), bindings: [], strategy: "STRUCTURE_AWARE",
        });
        await onQueued(job.batch_id);
      })}>{t("ui.kb01.parseOriginal")}</button>}
  </section>;
}
