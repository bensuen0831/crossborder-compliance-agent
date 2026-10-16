import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, type AdminClient } from "../admin/client";
import type { AdminSession } from "../admin/contracts";
import { idempotencyKey, KnowledgeManagementClient, mutation } from "./client";
import type { Schema } from "./client";
import { transferFile } from "./uploads";
import { TaxonomyEditor } from "./TaxonomyEditor";
import { TaxonomyTree } from "./TaxonomyTree";
import { TranslationAlignment } from "./TranslationAlignment";
import { ManifestPanel } from "./ManifestPanel";
import { KnowledgeScopeControls } from "./KnowledgeScopeControls";

type Document = Schema<"ManagedKnowledgeDocumentView">;
type Detail = Schema<"ManagedKnowledgeDocumentDetail">;
type Taxonomy = Schema<"TaxonomyView">;
type Version = Schema<"ManagedKnowledgeVersionView">;
type Batch = Schema<"KnowledgeBatchView">;
type Upload = Schema<"KnowledgeUploadView">;
const lifecycles = [
  "DRAFT",
  "INGESTED",
  "VALIDATED",
  "PENDING_REVIEW",
  "APPROVED",
  "ACTIVE",
  "SUPERSEDED",
  "EXPIRED",
  "ARCHIVED",
];
const kinds = [
  "JURISDICTION_CONFIG",
  "REGULATION_CATEGORY",
  "RESEARCH_TOPIC",
  "LANGUAGE",
  "ISSUING_AUTHORITY",
  "KNOWLEDGE_SOURCE_TYPE",
  "LEGAL_EFFECT",
] as const;

export function KnowledgeManagement({
  client: admin,
  session,
}: {
  client: AdminClient;
  session: AdminSession;
}) {
  const { t, i18n } = useTranslation();
  const client = useMemo(() => new KnowledgeManagementClient(admin), [admin]);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [tab, setTab] = useState<"documents" | "taxonomy" | "uploads">(
    "documents",
  );
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [revision, setRevision] = useState(0);
  const [documents, setDocuments] =
    useState<Schema<"ManagedKnowledgeDocumentPage">>();
  const [taxonomy, setTaxonomy] = useState<Schema<"TaxonomyPage">>();
  const [stats, setStats] = useState<Schema<"KnowledgeStatisticsView">>();
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("");
  const [lifecycle, setLifecycle] = useState("");
  const [label, setLabel] = useState("");
  const [countryFilters, setCountryFilters] = useState<string[]>([]);
  const [categoryFilters, setCategoryFilters] = useState<string[]>([]);
  const [classificationSearch, setClassificationSearch] = useState("");
  const [classificationPage, setClassificationPage] = useState(1);
  const [knownLabels, setKnownLabels] = useState<Record<string, Taxonomy>>({});
  const [selectedLabelPins, setSelectedLabelPins] = useState<
    Record<string, Schema<"KnowledgeDocumentLabel">>
  >({});
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<Detail>();
  const [preview, setPreview] = useState<Schema<"KnowledgeDocumentPreview">>();
  const [alignmentSource, setAlignmentSource] = useState<Version>();
  const [scopeVersion, setScopeVersion] = useState<Version>();
  const [history, setHistory] = useState<Schema<"KnowledgeAuditPage">>();
  const [selectedTaxonomy, setSelectedTaxonomy] =
    useState<Schema<"TaxonomyDetail">>();
  const [reason, setReason] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [batch, setBatch] = useState<Batch>();
  const [batchPage, setBatchPage] = useState(1);
  const [batchId, setBatchId] = useState("");
  const [manifestSelections, setManifestSelections] = useState<Record<string, Schema<"KnowledgeManifestRecordView">>>({});
  const [progress, setProgress] = useState("");
  const [uploadPolicy, setUploadPolicy] =
    useState<Schema<"KnowledgeUploadPolicyView">>();
  const controller = useRef<AbortController | null>(null);
  const folder = useRef<HTMLInputElement | null>(null);
  const [source, setSource] = useState("");
  const [sources, setSources] = useState<Schema<"KnowledgeSourceOptionPage">>();
  const [sourceSearch, setSourceSearch] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const [collectionOptions, setCollectionOptions] =
    useState<Schema<"KnowledgeCollectionVersionOptions">>();
  const [collection, setCollection] = useState("");
  const [documentLanguage, setDocumentLanguage] = useState("en");
  const [title, setTitle] = useState("");
  const [editing, setEditing] = useState<Version>();
  const [newVersionDocument, setNewVersionDocument] = useState<Detail>();
  const [officialSource, setOfficialSource] = useState("");
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
  const [taxonomyName, setTaxonomyName] = useState("");
  const [taxonomyCode, setTaxonomyCode] = useState("");
  const [taxonomyKind, setTaxonomyKind] = useState<(typeof kinds)[number]>(
    "REGULATION_CATEGORY",
  );
  const [aliases, setAliases] = useState("");
  const [jurisdictionType, setJurisdictionType] = useState("COUNTRY");
  const [localized, setLocalized] = useState<Record<string, string>>({
    "zh-CN": "",
    "zh-HK": "",
    "en-US": "",
  });
  const can = useCallback(
    (operation: string) => capabilities.includes(operation),
    [capabilities],
  );
  const perform = async (work: () => Promise<void>) => {
    setPending(true);
    setError("");
    try {
      await work();
      setRevision((value) => value + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  };
  useEffect(() => {
    const abort = new AbortController();
    client
      .get<Schema<"KnowledgeManagementCapabilities">>(
        "/capabilities",
        abort.signal,
      )
      .then((value) =>
        setCapabilities((previous) =>
          previous.join("\0") === value.operations.join("\0")
            ? previous
            : value.operations,
        ),
      )
      .catch((e) => {
        if (!abort.signal.aborted) {
          setCapabilities([]);
          setDocuments(undefined);
          setStats(undefined);
          setError(String(e));
        }
      });
    return () => {
      abort.abort();
      controller.current?.abort();
    };
  }, [client, revision]);
  useEffect(() => {
    folder.current?.setAttribute("webkitdirectory", "");
  }, [tab]);
  useEffect(() => {
    const abort = new AbortController();
    const filters = new URLSearchParams({
      query,
      page: String(page),
      page_size: "25",
    });
    if (language) filters.set("language", language);
    if (lifecycle) filters.set("lifecycle", lifecycle);
    if (label) filters.set("label_id", label);
    for (const identity of [...countryFilters, ...categoryFilters])
      filters.append("label_ids", identity);
    const fail = (e: unknown) => {
      if (!abort.signal.aborted) setError(String(e));
    };
    if (can("document:read"))
      client
        .get<
          Schema<"ManagedKnowledgeDocumentPage">
        >(`/documents?${filters}`, abort.signal)
        .then(setDocuments)
        .catch(fail);
    if (can("document:read") && can("statistics:read"))
      client
        .get<
          Schema<"KnowledgeStatisticsView">
        >(`/statistics?${filters}`, abort.signal)
        .then(setStats)
        .catch(fail);
    if (can("taxonomy:read"))
      client
        .get<Schema<"TaxonomyPage">>(
          `/taxonomy?${new URLSearchParams({ query: tab === "taxonomy" ? query : classificationSearch, page: String(tab === "taxonomy" ? page : classificationPage), page_size: "100", locale: i18n.language, ...(kind && tab === "taxonomy" ? { kind } : {}) })}`,
          abort.signal,
        )
        .then((value) => {
          setTaxonomy(value);
          setKnownLabels((previous) => {
            const keep = new Set([
              ...selectedLabels,
              ...countryFilters,
              ...categoryFilters,
              label,
            ]);
            return {
              ...Object.fromEntries(
                Object.entries(previous).filter(([key]) => keep.has(key)),
              ),
              ...Object.fromEntries(
                value.items.map((row) => [row.definition_id, row]),
              ),
            };
          });
        })
        .catch(fail);
    return () => abort.abort();
  }, [
    client,
    can,
    query,
    language,
    lifecycle,
    label,
    countryFilters,
    categoryFilters,
    classificationSearch,
    classificationPage,
    selectedLabels,
    kind,
    page,
    tab,
    revision,
    i18n.language,
  ]);
  useEffect(() => {
    if (!can("document:read")) return;
    const abort = new AbortController();
    client
      .get<Schema<"KnowledgeSourceOptionPage">>(
        `/sources?${new URLSearchParams({ query: sourceSearch, page: String(sourcePage), page_size: "50" })}`,
        abort.signal,
      )
      .then(setSources)
      .catch((e) => {
        if (!abort.signal.aborted) setError(String(e));
      });
    return () => abort.abort();
  }, [client, can, sourceSearch, sourcePage]);
  useEffect(() => {
    if (!source || !can("document:read")) return;
    const abort = new AbortController();
    client
      .get<Schema<"KnowledgeCollectionVersionOptions">>(
        `/sources/${source}/collection-versions`,
        abort.signal,
      )
      .then(setCollectionOptions)
      .catch((e) => {
        if (!abort.signal.aborted) setError(String(e));
      });
    return () => abort.abort();
  }, [client, can, source]);
  useEffect(() => {
    if (!can("upload:read")) return;
    const abort = new AbortController();
    client
      .get<Schema<"KnowledgeUploadPolicyView">>("/upload-policy", abort.signal)
      .then(setUploadPolicy)
      .catch((e) => {
        if (!abort.signal.aborted) setError(String(e));
      });
    return () => abort.abort();
  }, [client, can, revision]);
  const metadata = () => ({
    ...(editing?.metadata ?? {}),
    title,
    official_source_url: officialSource || null,
    labels: selectedLabels.map((identity) => {
      if (selectedLabelPins[identity]) return selectedLabelPins[identity];
      const original = editing?.metadata.labels?.find(
        (label) => label.definition_id === identity,
      );
      if (original) return original;
      const row = knownLabels[identity];
      if (!row?.active_version_id)
        throw new Error("CLASSIFICATION_VERSION_REQUIRED");
      return {
        kind: row.kind,
        definition_id: row.definition_id,
        version_id: row.active_version_id,
      };
    }),
  });
  const documentInput = (name: string) => ({
    source_id: source,
    collection_version_id: collection,
    language: documentLanguage,
    metadata: { ...metadata(), title: name },
    idempotency_key: idempotencyKey(),
  });
  const openDocument = async (row: Document) => {
    setEditing(undefined);
    setNewVersionDocument(undefined);
    setDetail(await client.get<Detail>(`/documents/${row.document_id}`));
    setPreview(undefined);
    setHistory(undefined);
    setScopeVersion(undefined);
    setAlignmentSource(undefined);
  };
  const batchIdentity = batch?.batch_id;
  const batchStatus = batch?.status;
  const pendingBatchTransport = batch?.items?.some((item) => item.transport_pending) ?? false;
  useEffect(() => {
    if (!batchIdentity || !can("batch:read")) return;
    const abort = new AbortController();
    const read = () =>
      client
        .get<Batch>(
          `/import-batches/${batchIdentity}?page=${batchPage}&page_size=100`,
          abort.signal,
        )
        .then(setBatch)
        .catch((e) => {
          if (!abort.signal.aborted) setError(String(e));
        });
    void read();
    const active = [
      "PENDING",
      "EXTRACTING",
      "CONFIRMED",
      "PROCESSING",
      "CANCELLING",
    ].includes(batchStatus ?? "") || pendingBatchTransport;
    const interval = active ? setInterval(() => void read(), 3000) : undefined;
    return () => {
      abort.abort();
      if (interval) clearInterval(interval);
    };
  }, [client, can, batchIdentity, batchStatus, batchPage, pendingBatchTransport]);
  const activeUploads = uploads
    .filter((row) =>
      ["QUEUED_SCAN", "SCANNING", "FINALIZING", "CANCELLING"].includes(
        row.status,
      ),
    )
    .map((row) => row.upload_session_id)
    .sort()
    .join(",");
  useEffect(() => {
    if (!activeUploads || !can("upload:read")) return;
    const abort = new AbortController();
    const interval = setInterval(() => {
      void Promise.all(
        activeUploads
          .split(",")
          .map((id) =>
            client.get<Upload>(`/upload-sessions/${id}`, abort.signal),
          ),
      )
        .then((rows) =>
          setUploads((old) =>
            old.map(
              (row) =>
                rows.find(
                  (next) => next.upload_session_id === row.upload_session_id,
                ) ?? row,
            ),
          ),
        )
        .catch((e) => {
          if (!abort.signal.aborted) setError(String(e));
        });
    }, 3000);
    return () => {
      abort.abort();
      clearInterval(interval);
    };
  }, [activeUploads, can, client]);
  const refreshBatch = async () => {
    if (batch)
      setBatch(
        await client.get<Batch>(
          `/import-batches/${batch.batch_id}?page=${batchPage}&page_size=100`,
        ),
      );
  };
  const operation = async (version: Version, action: string) => {
    await client.mutate(
      `/documents/versions/${version.knowledge_version_id}/${action}`,
      mutation(version.record_version, reason),
    );
    if (detail) await openDocument(detail);
  };
  const lifecycleActions = (version: Version): [string, string][] =>
    (({
      DRAFT: [],
      INGESTED: [["validate", "document:validate"]],
      VALIDATED: [["submit-review", "document:submit-review"]],
      PENDING_REVIEW: [["approve", "document:approve"]],
      APPROVED: [["publish", "document:publish"]],
      ACTIVE: [
        ["expire", "document:archive"],
        ["supersede", "document:archive"],
      ],
      EXPIRED: [["archive", "document:archive"]],
    })[version.lifecycle] as [string, string][] | undefined) ?? [];
  const taxonomyMutation = async (row: Taxonomy, action: string) => {
    const versionAction = [
      "submit-review",
      "approve",
      "reject",
      "publish",
      "archive",
    ].includes(action);
    const identity = versionAction ? row.version_id : row.definition_id;
    await client.mutate(
      `/taxonomy/${versionAction ? "versions/" : ""}${identity}/${action}`,
      mutation(
        versionAction
          ? (selectedTaxonomy?.versions.find(
              (version) => version.version_id === row.version_id,
            )?.record_version ?? row.record_version)
          : row.record_version,
        reason,
      ),
    );
    setSelectedTaxonomy(
      await client.get<Schema<"TaxonomyDetail">>(
        `/taxonomy/${row.definition_id}`,
      ),
    );
  };
  return (
    <section className="kb-management" aria-label={t("ui.kb01.workspace")}>
      <h2>{t("ui.kb01.workspace")}</h2>
      <p>{t("ui.kb01.governanceHint")}</p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="actions">
        <div role="tablist" aria-label={t("ui.kb01.workspace")}>
          {(["documents", "taxonomy", "uploads"] as const).map((name) => (
            <button
              key={name}
              role="tab"
              aria-selected={tab === name}
              onClick={() => {
                setTab(name);
                setPage(1);
              }}
            >
              {t(`ui.kb01.${name}`)}
            </button>
          ))}
        </div>
        <button onClick={() => setRevision((v) => v + 1)}>
          {t("ui.kb01.refresh")}
        </button>
      </div>
      <label>
        {t("ui.kb01.reason")}
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={2048}
        />
      </label>
      {tab !== "uploads" && (
        <div className="kb-filters">
          <label>
            {t("ui.kb01.search")}
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </label>
          {tab === "documents" ? (
            <>
              <label>
                {t("ui.kb01.language")}
                <input
                  value={language}
                  onChange={(e) => {
                    setLanguage(e.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <label>
                {t("ui.kb01.lifecycle")}
                <select
                  value={lifecycle}
                  onChange={(e) => {
                    setLifecycle(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">{t("ui.kb01.all")}</option>
                  {lifecycles.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("ui.kb01.classification")}
                <select
                  value={label}
                  onChange={(e) => {
                    setLabel(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">{t("ui.kb01.all")}</option>
                  {taxonomy?.items.map((row) => (
                    <option key={row.definition_id} value={row.definition_id}>
                      {row.display_name}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <label>
              {t("ui.kb01.kind")}
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">{t("ui.kb01.all")}</option>
                {kinds.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}
      {tab === "documents" && (
        <>
          {can("taxonomy:read") && <section className="panel" aria-label={t("ui.kb01.jurisdictionTree")}>
            <h3>{t("ui.kb01.jurisdictionTree")}</h3>
            <p>{t("ui.kb01.publishedHierarchy")}</p>
            <TaxonomyTree key={revision} client={client} selected={countryFilters}
              onSelect={(node) => {
                setCountryFilters((old) => old.includes(node.definition_id)
                  ? old.filter((id) => id !== node.definition_id) : [...old, node.definition_id]);
                setPage(1);
              }} />
          </section>}
          <div className="kb-filters">
            <label>
              {t("ui.kb01.countryFilter")}
              <select
                multiple
                value={countryFilters}
                onChange={(e) => {
                  setCountryFilters(
                    Array.from(
                      e.target.selectedOptions,
                      (option) => option.value,
                    ),
                  );
                  setPage(1);
                }}
              >
                {Object.values(knownLabels)
                  .filter((row) => row.kind === "JURISDICTION_CONFIG")
                  .map((row) => (
                    <option key={row.definition_id} value={row.definition_id}>
                      {row.display_name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              {t("ui.kb01.categoryFilter")}
              <select
                multiple
                value={categoryFilters}
                onChange={(e) => {
                  setCategoryFilters(
                    Array.from(
                      e.target.selectedOptions,
                      (option) => option.value,
                    ),
                  );
                  setPage(1);
                }}
              >
                {Object.values(knownLabels)
                  .filter((row) => row.kind === "REGULATION_CATEGORY")
                  .map((row) => (
                    <option key={row.definition_id} value={row.definition_id}>
                      {row.display_name}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          {stats && (
            <section className="panel" aria-label={t("ui.kb01.statistics")}>
              <h3>{t("ui.kb01.statistics")}</h3>
              <dl className="checks">
                {(
                  [
                    "documents",
                    "versions",
                    "attached_originals",
                    "attached_bytes",
                  ] as const
                ).map((key) => (
                  <div key={key}>
                    <dt>{t(`ui.kb01.${key}`)}</dt>
                    <dd>{stats[key].toLocaleString()}</dd>
                  </div>
                ))}
              </dl>
              <p>{t("ui.kb01.countScope")}</p>
              <time>{stats.as_of}</time>
              <ul>
                {stats.by_classification.map((group) => (
                  <li key={group.definition_id}>
                    {group.code}: {group.documents}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <ul className="resource-list">
            {documents?.items.map((row) => (
              <li key={row.document_id}>
                <button
                  data-document-id={row.document_id}
                  onClick={() => void perform(() => openDocument(row))}
                >
                  {row.display_name} · {row.status}
                </button>
              </li>
            ))}
          </ul>
          {documents && <p>{t("ui.kb01.total", { count: documents.total })}</p>}
          {detail && (
            <section className="panel">
              <h3>{detail.display_name}</h3>
              <p>{detail.document_id}</p>
              <button
                disabled={!can("audit:read") || pending}
                onClick={() =>
                  void perform(async () =>
                    setHistory(
                      await client.get(`/audit/${detail.document_id}`),
                    ),
                  )
                }
              >
                {t("ui.kb01.history")}
              </button>
              <button
                disabled={!can("document:delete") || pending || !reason}
                onClick={() =>
                  void perform(async () => {
                    await client.mutate(
                      `/documents/${detail.document_id}`,
                      mutation(detail.record_version, reason),
                      "DELETE",
                    );
                    setDetail(undefined);
                  })
                }
              >
                {t("ui.kb01.deleteDraft")}
              </button>
              {detail.versions.map((version) => (
                <article key={version.knowledge_version_id}>
                  <h4>
                    {t("ui.kb01.version")} {version.version} ·{" "}
                    {version.lifecycle} · {version.language}
                  </h4>
                  <p>{version.metadata.title}</p>
                  <div className="actions">
                    <button onClick={() => setScopeVersion(version)}>{t("ui.kb01.scopeBindings")}</button>
                    {can("translation:read") && version.content_hash && !["DRAFT", "ARCHIVED"].includes(version.lifecycle) && <button
                      onClick={() => setAlignmentSource(version)}>{t("ui.kb01.translationAlignment")}</button>}
                    <button
                      onClick={() =>
                        void perform(async () =>
                          setPreview(
                            await client.get(
                              `/documents/versions/${version.knowledge_version_id}/preview`,
                            ),
                          ),
                        )
                      }
                    >
                      {t("ui.kb01.preview")}
                    </button>
                    <button
                      disabled={!can("document:write") || pending || !reason}
                      onClick={() =>
                        void perform(async () => {
                          setNewVersionDocument(undefined);
                          setEditing(version);
                          setTitle(version.metadata.title);
                          setOfficialSource(
                            version.metadata.official_source_url ?? "",
                          );
                          setDocumentLanguage(version.language);
                          setSelectedLabels(
                            (version.metadata.labels ?? []).map(
                              (label) => label.definition_id,
                            ),
                          );
                        })
                      }
                    >
                      {t("ui.kb01.editMetadata")}
                    </button>
                    <button
                      disabled={pending || !can("document:write")}
                      onClick={() => {
                        setNewVersionDocument(detail);
                        setEditing(version);
                        setTitle(version.metadata.title);
                        setOfficialSource(
                          version.metadata.official_source_url ?? "",
                        );
                        setDocumentLanguage(version.language);
                        setSelectedLabels(
                          (version.metadata.labels ?? []).map(
                            (label) => label.definition_id,
                          ),
                        );
                      }}
                    >
                      {t("ui.kb01.newVersion")}
                    </button>
                    {version.file_available && can("document:download") && (
                      <a
                        href={`/api/v1/admin/knowledge-management/documents/versions/${version.knowledge_version_id}/original`}
                        download
                      >
                        {t("ui.kb01.downloadOriginal")}
                      </a>
                    )}
                    {lifecycleActions(version).map(([action, grant]) => (
                      <button
                        key={action}
                        disabled={!can(grant) || pending || !reason}
                        onClick={() =>
                          void perform(() => operation(version, action))
                        }
                      >
                        {t(`ui.kb01.action.${action}`)}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
              {history && (
                <ol>
                  {history.items.map((item) => (
                    <li key={item.receipt_id}>
                      {item.operation} · {item.actor_id} · {item.created_at}
                      <p>{item.reason}</p>
                    </li>
                  ))}
                </ol>
              )}
              {alignmentSource && <TranslationAlignment
                key={alignmentSource.knowledge_version_id} client={client} source={alignmentSource} can={can} />}
              {scopeVersion && <KnowledgeScopeControls key={`${scopeVersion.knowledge_version_id}:${scopeVersion.record_version}`}
                client={client} version={scopeVersion} can={can} refreshed={async () => {
                  const refreshed = await client.get<Detail>(`/documents/${detail.document_id}`);
                  setDetail(refreshed); setScopeVersion(refreshed.versions.find((version) => version.knowledge_version_id === scopeVersion.knowledge_version_id));
                }} onQueued={async (identity) => {
                  setBatch(await client.get<Batch>(`/import-batches/${identity}`)); setTab("uploads");
                }} />}
              {preview && (
                <section aria-label={t("ui.kb01.preview")}>
                  <p>{t("ui.kb01.total", { count: preview.total })}</p>
                  <div className="actions">
                    <button
                      disabled={pending || preview.page <= 1}
                      onClick={() =>
                        void perform(async () =>
                          setPreview(
                            await client.get(
                              `/documents/versions/${preview.knowledge_version_id}/preview?page=${preview.page - 1}`,
                            ),
                          ),
                        )
                      }
                    >
                      {t("ui.kb01.previous")}
                    </button>
                    <span>{preview.page}</span>
                    <button
                      disabled={
                        pending ||
                        preview.page * preview.page_size >= preview.total
                      }
                      onClick={() =>
                        void perform(async () =>
                          setPreview(
                            await client.get(
                              `/documents/versions/${preview.knowledge_version_id}/preview?page=${preview.page + 1}`,
                            ),
                          ),
                        )
                      }
                    >
                      {t("ui.kb01.next")}
                    </button>
                  </div>
                  {preview.items.map((node) => (
                    <article key={node.structure_node_id} dir="auto">
                      <h4>
                        {node.official_number} {node.heading}
                      </h4>
                      <p>
                        {node.canonical_locator} · {node.node_type} ·{" "}
                        {node.language}
                      </p>
                      <p style={{ whiteSpace: "pre-wrap" }}>
                        {node.original_excerpt}
                      </p>
                      <p>
                        {t("ui.kb01.citation")}: {node.citation_id}
                      </p>
                      {node.excerpt_truncated && (
                        <p>{t("ui.kb01.excerptTruncated")}</p>
                      )}
                    </article>
                  ))}
                </section>
              )}
            </section>
          )}
        </>
      )}
      {tab === "taxonomy" && (
        <>
          <ul className="resource-list">
            {taxonomy?.items.map((row) => (
              <li key={row.definition_id}>
                <button
                  onClick={() =>
                    void perform(async () =>
                      setSelectedTaxonomy(
                        await client.get(`/taxonomy/${row.definition_id}`),
                      ),
                    )
                  }
                >
                  {row.display_name} · {row.kind} · {row.lifecycle}{" "}
                  {row.enabled ? "" : t("ui.kb01.disabled")}
                </button>
              </li>
            ))}
          </ul>
          {selectedTaxonomy && (
            <section className="panel">
              <h3>{selectedTaxonomy.display_name}</h3>
              <p>{selectedTaxonomy.code}</p>
              <TaxonomyEditor
                key={`${selectedTaxonomy.definition_id}:${selectedTaxonomy.record_version}`}
                row={selectedTaxonomy}
                choices={taxonomy?.items ?? []}
                client={client}
                can={can}
                reason={reason}
                refreshed={async () => {
                  try {
                    setSelectedTaxonomy(
                      await client.get(
                        `/taxonomy/${selectedTaxonomy.definition_id}`,
                      ),
                    );
                  } catch (e) {
                    if (e instanceof ApiError && e.status === 404)
                      setSelectedTaxonomy(undefined);
                    else throw e;
                  }
                  setRevision((value) => value + 1);
                }}
              />

              <div className="actions">
                {[
                  ["submit-review", "taxonomy:submit-review"],
                  ["approve", "taxonomy:approve"],
                  ["reject", "taxonomy:approve"],
                  ["publish", "taxonomy:publish"],
                  ["archive", "taxonomy:archive"],
                  [
                    selectedTaxonomy.enabled ? "deactivate" : "reactivate",
                    "taxonomy:write",
                  ],
                ].map(([action, grant]) => (
                  <button
                    key={action}
                    disabled={!can(grant) || pending || !reason}
                    onClick={() =>
                      void perform(() =>
                        taxonomyMutation(selectedTaxonomy, action),
                      )
                    }
                  >
                    {t(`ui.kb01.action.${action}`)}
                  </button>
                ))}
              </div>
              <ol>
                {selectedTaxonomy.versions.map((version) => (
                  <li key={version.version_id}>
                    {version.version_no} · {version.lifecycle_status} ·{" "}
                    {version.created_by} · {version.approved_by}
                  </li>
                ))}
              </ol>
            </section>
          )}
          <form
            className="panel"
            onSubmit={(e) => {
              e.preventDefault();
              void perform(async () => {
                await client.mutate("/taxonomy", {
                  kind: taxonomyKind,
                  code: taxonomyCode,
                  display_name: taxonomyName,
                  payload: {
                    ...(taxonomyKind === "JURISDICTION_CONFIG"
                      ? { jurisdiction_type: jurisdictionType }
                      : {}),
                    aliases: aliases
                      .split("\n")
                      .map((value) => value.trim())
                      .filter(Boolean),
                    localized_display: {
                      localized_display_names: Object.fromEntries(
                        Object.entries(localized).filter(([, value]) =>
                          value.trim(),
                        ),
                      ),
                      fallback_locale: "en-US",
                    },
                  },
                  idempotency_key: idempotencyKey(),
                });
              });
            }}
          >
            <h3>{t("ui.kb01.createTaxonomy")}</h3>
            <label>
              {t("ui.kb01.kind")}
              <select
                value={taxonomyKind}
                onChange={(e) =>
                  setTaxonomyKind(e.target.value as typeof taxonomyKind)
                }
              >
                {kinds.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            {taxonomyKind === "JURISDICTION_CONFIG" && (
              <label>
                {t("ui.kb01.jurisdictionType")}
                <select
                  value={jurisdictionType}
                  onChange={(e) => setJurisdictionType(e.target.value)}
                >
                  {[
                    "COUNTRY",
                    "TERRITORY",
                    "SUPRANATIONAL",
                    "SUBJURISDICTION",
                    "SPECIAL_REGIME",
                  ].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
            )}
            <label>
              {t("ui.kb01.code")}
              <input
                value={taxonomyCode}
                onChange={(e) => setTaxonomyCode(e.target.value)}
                required
              />
            </label>
            <label>
              {t("ui.kb01.name")}
              <input
                value={taxonomyName}
                onChange={(e) => setTaxonomyName(e.target.value)}
                required
              />
            </label>
            {Object.keys(localized).map((locale) => (
              <label key={locale}>
                {t("ui.kb01.name")} ({locale})
                <input
                  value={localized[locale]}
                  onChange={(e) =>
                    setLocalized({ ...localized, [locale]: e.target.value })
                  }
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
            <button disabled={!can("taxonomy:write") || pending}>
              {t("ui.kb01.createTaxonomy")}
            </button>
          </form>
        </>
      )}
      {tab === "uploads" && (
        <section className="panel">
          <h3>{t("ui.kb01.localUpload")}</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void perform(async () => {
                setBatch(
                  await client.get(
                    `/import-batches/${encodeURIComponent(batchId)}?page=1&page_size=100`,
                  ),
                );
                setBatchPage(1);
              });
            }}
          >
            <label>
              {t("ui.kb01.batchId")}
              <input
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                required
              />
            </label>
            <button disabled={pending || !can("batch:read")}>
              {t("ui.kb01.openBatch")}
            </button>
          </form>
          <p>{t("ui.kb01.uploadHint")}</p>
          {uploadPolicy && (
            <p>
              {t("ui.kb01.uploadLimits", {
                document: uploadPolicy.max_single_bytes.toLocaleString(
                  i18n.language,
                ),
                archive: uploadPolicy.max_archive_bytes.toLocaleString(
                  i18n.language,
                ),
                chunk: uploadPolicy.multipart_chunk_bytes.toLocaleString(
                  i18n.language,
                ),
              })}
            </p>
          )}
          <label>
            {t("ui.kb01.files")}
            <input
              type="file"
              multiple
              accept={
                uploadPolicy
                  ? [
                      ...uploadPolicy.allowed_document_formats,
                      ...uploadPolicy.allowed_archive_formats,
                    ]
                      .map((format) => "." + format.toLowerCase())
                      .join(",")
                  : undefined
              }
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            />
          </label>
          <label>
            {t("ui.kb01.folder")}
            <input
              ref={folder}
              type="file"
              multiple
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            />
          </label>
          <ul>
            {files.map((file) => (
              <li key={file.webkitRelativePath || file.name}>
                {file.webkitRelativePath || file.name} ·{" "}
                {file.size.toLocaleString()}
              </li>
            ))}
          </ul>
          <button
            disabled={
              pending ||
              !files.length ||
              !uploadPolicy ||
              !can("upload:create") ||
              !can("upload:write") ||
              !can("upload:complete")
            }
            onClick={() =>
              void perform(async () => {
                const abort = new AbortController();
                controller.current = abort;
                for (const file of files) {
                  const row = await transferFile(
                    client,
                    file,
                    `${session.tenantId}:${session.actorId}`,
                    abort.signal,
                    (row, phase, sent) => {
                      setProgress(
                        `${file.name} · ${t(`ui.kb01.${phase}`)} · ${sent.toLocaleString()} / ${file.size.toLocaleString()}`,
                      );
                      if (row)
                        setUploads((old) => [
                          ...old.filter(
                            (value) =>
                              value.upload_session_id !== row.upload_session_id,
                          ),
                          row,
                        ]);
                    },
                  );
                  setUploads((old) => [
                    ...old.filter(
                      (value) =>
                        value.upload_session_id !== row.upload_session_id,
                    ),
                    row,
                  ]);
                }
              })
            }
          >
            {t("ui.kb01.startResume")}
          </button>
          <button
            disabled={!pending}
            onClick={() => controller.current?.abort()}
          >
            {t("ui.kb01.pause")}
          </button>
          <p role="status">{progress}</p>
          <ul>
            {uploads.map((row) => (
              <li key={row.upload_session_id}>
                {row.relative_path} · {row.status} · {row.error_code}
                <div className="actions">
                  <button
                    onClick={() =>
                      void perform(async () => {
                        const next = await client.get<Upload>(
                          `/upload-sessions/${row.upload_session_id}`,
                        );
                        setUploads((old) =>
                          old.map((value) =>
                            value.upload_session_id === next.upload_session_id
                              ? next
                              : value,
                          ),
                        );
                      })
                    }
                  >
                    {t("ui.kb01.refresh")}
                  </button>
                  <button
                    disabled={!can("upload:cancel") || pending}
                    onClick={() =>
                      void perform(async () => {
                        await client.mutate(
                          `/upload-sessions/${row.upload_session_id}/cancel`,
                          {
                            expected_record_version: row.record_version,
                            idempotency_key: idempotencyKey(),
                          },
                        );
                      })
                    }
                  >
                    {t("ui.kb01.cancel")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <button
            disabled={
              pending ||
              !uploads.length ||
              uploads.some((row) => row.status !== "VERIFIED") ||
              !can("batch:create")
            }
            onClick={() =>
              void perform(async () => {
                const archive = uploads.filter((row) =>
                  ["RAR", "ZIP"].includes(row.declared_format),
                );
                if (archive.length && uploads.length !== 1)
                  throw new Error("ONE_ARCHIVE_PER_BATCH");
                setBatch(
                  await client.mutate("/import-batches", {
                    ...(archive.length
                      ? {
                          archive_upload_session_id:
                            archive[0].upload_session_id,
                        }
                      : {
                          upload_session_ids: uploads.map(
                            (row) => row.upload_session_id,
                          ),
                        }),
                    idempotency_key: idempotencyKey(),
                  }),
                );
              })
            }
          >
            {t("ui.kb01.createBatch")}
          </button>
          {batch && (
            <section>
              {can("batch:manifest-read") && <ManifestPanel key={batch.batch_id} client={client} batch={batch}
                labels={Object.values(knownLabels)} can={can} scope={`${session.tenantId}:${session.actorId}:manifest`}
                onUse={(row) => { if (row.matched_item_id) setManifestSelections((old) => ({ ...old, [row.matched_item_id!]: row })); }} />}
              <h4>
                {t("ui.kb01.batch")} · {batch.status}
              </h4>
              <p>{batch.error_code}</p>
              <p>{t("ui.kb01.total", { count: batch.total ?? 0 })}</p>
              <dl>
                {Object.entries(batch.counts ?? {}).map(([status, count]) => (
                  <div key={status}>
                    <dt>{status}</dt>
                    <dd>{count}</dd>
                  </div>
                ))}
              </dl>
              <button
                disabled={pending || !can("batch:export") || !can("batch:read")}
                onClick={() =>
                  void perform(async () => {
                    const start = await client.get<Batch>(
                      `/import-batches/${batch.batch_id}`,
                    );
                    const rows: Schema<"KnowledgeBatchFailure">[] = [];
                    for (let page = 1; ; page++) {
                      const data = await client.get<
                        Schema<"KnowledgeBatchFailurePage">
                      >(
                        `/import-batches/${batch.batch_id}/failures?page=${page}&page_size=100`,
                      );
                      rows.push(...data.items);
                      if (rows.length >= data.total) break;
                      if (page >= 1000 || !data.items.length)
                        throw new Error("FAILURE_EXPORT_LIMIT");
                    }
                    const end = await client.get<Batch>(
                      `/import-batches/${batch.batch_id}`,
                    );
                    if (start.record_version !== end.record_version)
                      throw new Error(
                        "FAILURE_EXPORT_CHANGED_REFRESH_REQUIRED",
                      );
                    const url = URL.createObjectURL(
                      new Blob(
                        [
                          JSON.stringify(
                            {
                              batch_id: batch.batch_id,
                              record_version: end.record_version,
                              items: rows,
                            },
                            null,
                            2,
                          ),
                        ],
                        { type: "application/json" },
                      ),
                    );
                    const link = document.createElement("a");
                    link.href = url;
                    link.download = `knowledge-import-${batch.batch_id}-failures.json`;
                    link.click();
                    setTimeout(() => URL.revokeObjectURL(url), 1000);
                  })
                }
              >
                {t("ui.kb01.exportFailures")}
              </button>

              <div className="actions">
                <button onClick={() => void perform(refreshBatch)}>
                  {t("ui.kb01.refresh")}
                </button>
                {(["cancel", "retry"] as const).map((action) => (
                  <button
                    key={action}
                    disabled={pending || !can(`batch:${action}`)}
                    onClick={() =>
                      void perform(async () => {
                        setBatch(
                          await client.mutate(
                            `/import-batches/${batch.batch_id}/${action}`,
                            {
                              expected_record_version: batch.record_version,
                              idempotency_key: idempotencyKey(),
                            },
                          ),
                        );
                        await refreshBatch();
                      })
                    }
                  >
                    {t(`ui.kb01.${action}`)}
                  </button>
                ))}
              </div>
              <ul>
                {batch.items?.map((item) => (
                  <li key={item.item_id}>
                    {item.relative_path} · {item.status} · {item.error_code}
                    {manifestSelections[item.item_id] && <label>{t("ui.kb01.manifestSelectedProposal")}<input
                      value={manifestSelections[item.item_id].proposed_values.title}
                      onChange={(e) => setManifestSelections((old) => ({ ...old, [item.item_id]: {
                        ...old[item.item_id], proposed_values: { ...old[item.item_id].proposed_values, title: e.target.value },
                      } }))} maxLength={250} /></label>}
                    {item.technical_retry_available && (
                      <button
                        disabled={pending || !can("batch:retry")}
                        onClick={() =>
                          void perform(async () => {
                            await client.mutate(
                              `/import-batches/${batch.batch_id}/items/${item.item_id}/retry`,
                              {
                                expected_record_version: batch.record_version,
                                expected_item_record_version:
                                  item.record_version,
                                idempotency_key: idempotencyKey(),
                              },
                            );
                            await refreshBatch();
                          })
                        }
                      >
                        {t("ui.kb01.retry")}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
              <button
                disabled={
                  pending || !can("batch:confirm") || !source || !collection ||
                  batch.status !== "PREVIEW" || !batch.items?.some((item) => item.mapping_available) ||
                  batch.items.some((item) => item.status === "UNMAPPED" && !item.mapping_available)
                }
                onClick={() =>
                  void perform(async () => {
                    await client.mutate(
                      `/import-batches/${batch.batch_id}/confirm-items`,
                      {
                        expected_record_version: batch.record_version,
                        idempotency_key: idempotencyKey(),
                        mappings: batch.items
                          ?.filter((item) => item.status === "UNMAPPED")
                          .map((item) => {
                            const proposal = manifestSelections[item.item_id];
                            const document = documentInput(proposal?.proposed_values.title ?? item.relative_path.split("/").at(-1)!);
                            if (proposal) document.metadata.labels = Array.from(new Map([
                              ...document.metadata.labels, ...Object.values(proposal.metadata_refs).flat(),
                            ].map((label) => [label.definition_id, label])).values());
                            return { item_id: item.item_id, document,
                              ...(proposal ? { manifest_record_id: proposal.manifest_record_id } : {}) };
                          }),
                      },
                    );
                    await refreshBatch();
                  })
                }
              >
                {t("ui.kb01.confirmMapping")}
              </button>
              <div className="actions">
                <button
                  disabled={batchPage <= 1 || pending}
                  onClick={() => setBatchPage((value) => value - 1)}
                >
                  {t("ui.kb01.previous")}
                </button>
                <span>{batchPage}</span>
                <button
                  disabled={pending || batchPage * 100 >= (batch.total ?? 0)}
                  onClick={() => setBatchPage((value) => value + 1)}
                >
                  {t("ui.kb01.next")}
                </button>
              </div>
            </section>
          )}
        </section>
      )}
      {(tab === "documents" || tab === "uploads") && (
        <section className="panel">
          <label>
            {t("ui.kb01.findClassification")}
            <input
              value={classificationSearch}
              onChange={(e) => {
                setClassificationSearch(e.target.value);
                setClassificationPage(1);
              }}
            />
          </label>
          <div className="actions">
            <button
              disabled={classificationPage <= 1}
              onClick={() => setClassificationPage((value) => value - 1)}
            >
              {t("ui.kb01.previous")}
            </button>
            <span>{classificationPage}</span>
            <button
              disabled={classificationPage * 100 >= (taxonomy?.total ?? 0)}
              onClick={() => setClassificationPage((value) => value + 1)}
            >
              {t("ui.kb01.next")}
            </button>
          </div>
        </section>
      )}
      {(tab === "documents" || tab === "uploads") && (
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            void perform(async () => {
              if (newVersionDocument) {
                await client.mutate(
                  `/documents/${newVersionDocument.document_id}/versions`,
                  {
                    ...mutation(newVersionDocument.record_version, reason),
                    collection_version_id: collection,
                    language: documentLanguage,
                    metadata: metadata(),
                  },
                );
                setNewVersionDocument(undefined);
                setEditing(undefined);
                await openDocument(newVersionDocument);
              } else if (editing) {
                await client.mutate(
                  `/documents/versions/${editing.knowledge_version_id}`,
                  {
                    ...mutation(editing.record_version, reason),
                    metadata: metadata(),
                  },
                  "PATCH",
                );
                setEditing(undefined);
                if (detail) await openDocument(detail);
              } else await client.mutate("/documents", documentInput(title));
            });
          }}
        >
          <h3>{t("ui.kb01.documentMetadata")}</h3>
          <label>
            {t("ui.kb01.sourceSearch")}
            <input
              value={sourceSearch}
              onChange={(e) => {
                setSourceSearch(e.target.value);
                setSourcePage(1);
              }}
            />
          </label>
          <label>
            {t("ui.kb01.sourceId")}
            <select
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setCollection("");
                setCollectionOptions(undefined);
              }}
              required={!editing || !!newVersionDocument}
            >
              <option value="">{t("ui.kb01.select")}</option>
              {sources?.items.map((item) => (
                <option key={item.source_id} value={item.source_id}>
                  {item.code} · {item.collection_name}
                </option>
              ))}
            </select>
          </label>
          <div className="actions">
            <button
              type="button"
              disabled={sourcePage <= 1}
              onClick={() => setSourcePage((value) => value - 1)}
            >
              {t("ui.kb01.previous")}
            </button>
            <span>{sourcePage}</span>
            <button
              type="button"
              disabled={sourcePage * 50 >= (sources?.total ?? 0)}
              onClick={() => setSourcePage((value) => value + 1)}
            >
              {t("ui.kb01.next")}
            </button>
          </div>
          <label>
            {t("ui.kb01.collectionVersion")}
            <select
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
              required={!editing || !!newVersionDocument}
            >
              <option value="">{t("ui.kb01.select")}</option>
              {collectionOptions?.items.map((item) => (
                <option
                  key={item.collection_version_id}
                  value={item.collection_version_id}
                >
                  {item.display_name} · {item.version_no}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("ui.kb01.title")}
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={250}
            />
          </label>
          <label>
            {t("ui.kb01.language")}
            <input
              value={documentLanguage}
              onChange={(e) => setDocumentLanguage(e.target.value)}
              required
            />
          </label>
          <label>
            {t("ui.kb01.officialSource")}
            <input
              type="url"
              value={officialSource}
              onChange={(e) => setOfficialSource(e.target.value)}
            />
          </label>
          <label>
            {t("ui.kb01.classification")}
            <select
              multiple
              value={selectedLabels}
              onChange={(e) => {
                const ids = Array.from(
                  e.target.selectedOptions,
                  (option) => option.value,
                );
                setSelectedLabels(ids);
                setSelectedLabelPins((previous) =>
                  Object.fromEntries(
                    ids.map((id) => {
                      const row = knownLabels[id];
                      const original = selectedLabels.includes(id)
                        ? editing?.metadata.labels?.find(
                            (label) => label.definition_id === id,
                          )
                        : undefined;
                      return [
                        id,
                        previous[id] ??
                          original ?? {
                            kind: row.kind,
                            definition_id: id,
                            version_id: row.active_version_id!,
                          },
                      ];
                    }),
                  ),
                );
              }}
            >
              {selectedLabels
                .filter((id) => !knownLabels[id])
                .map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              {Object.values(knownLabels)
                .filter((row) => row.active_version_id && row.enabled)
                .map((row) => (
                  <option key={row.definition_id} value={row.definition_id}>
                    {row.display_name}
                  </option>
                ))}
            </select>
          </label>
          {tab === "documents" && (
            <button
              disabled={
                pending ||
                (!editing && !can("document:create")) ||
                !can("document:write") ||
                (!!editing && !reason)
              }
            >
              {t(
                newVersionDocument
                  ? "ui.kb01.newVersion"
                  : editing
                    ? "ui.kb01.saveMetadata"
                    : "ui.kb01.createDocument",
              )}
            </button>
          )}
        </form>
      )}
      {tab !== "uploads" && (
        <div className="actions">
          <button disabled={page <= 1} onClick={() => setPage((v) => v - 1)}>
            {t("ui.kb01.previous")}
          </button>
          <span>{page}</span>
          <button
            disabled={
              tab === "documents"
                ? page * 25 >= (documents?.total ?? 0)
                : page * 100 >= (taxonomy?.total ?? 0)
            }
            onClick={() => setPage((v) => v + 1)}
          >
            {t("ui.kb01.next")}
          </button>
        </div>
      )}
    </section>
  );
}
