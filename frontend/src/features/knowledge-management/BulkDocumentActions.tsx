import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { idempotencyKey, type KnowledgeManagementClient, type Schema } from "./client";

type Action = "delete" | "expire" | "archive";
type Preview = {
  detail: Schema<"ManagedKnowledgeDocumentDetail">;
  impact: Schema<"ManagedKnowledgeDocumentImpact">;
};
type Command = { documentId: string; path: string; method: string; body: {
  expected_record_version: number; reason: string; idempotency_key: string;
}; };

/** Bounded channel orchestration. Each canonical command owns authorization,
 * eligibility, audit, CAS and idempotency; a batch is explicitly non-atomic. */
export function BulkDocumentActions({ client, documents, can, onChanged }: {
  client: KnowledgeManagementClient;
  documents: Schema<"ManagedKnowledgeDocumentView">[];
  can: (operation: string) => boolean;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string[]>([]);
  const [action, setAction] = useState<Action>("delete");
  const [reason, setReason] = useState("");
  const [previews, setPreviews] = useState<Preview[]>([]);
  const [versions, setVersions] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [frozen, setFrozen] = useState(false);
  const commands = useRef<Command[] | null>(null);
  const completed = useRef(new Set<string>());
  const running = useRef(false);
  if (!can("document:read") || !(can("document:delete") || can("document:archive"))) return null;

  const reset = () => {
    commands.current = null;
    completed.current.clear();
    setPreviews([]); setVersions({}); setResults({}); setError(""); setFrozen(false);
  };
  const permitted = can(action === "delete" ? "document:delete" : "document:archive");
  const preview = async () => {
    if (running.current || !permitted || !selected.length || selected.length > 100) return;
    running.current = true; setBusy(true); reset();
    try {
      const rows = [];
      for (const id of selected) {
        const detail = await client.get<Preview["detail"]>(`/documents/${id}`);
        const impact = await client.get<Preview["impact"]>(`/documents/${id}/impact`);
        rows.push({ detail, impact });
      }
      setPreviews(rows);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { running.current = false; setBusy(false); }
  };
  const execute = async () => {
    if (running.current || !permitted || !previews.length || !reason.trim()) return;
    if (action !== "delete" && previews.some(({ detail }) => !versions[detail.document_id])) return;
    running.current = true; setBusy(true); setError("");
    try {
      if (!commands.current) {
        const prepared: Command[] = [];
        for (const { detail, impact } of previews) {
          const id = detail.document_id;
          if (action === "delete" && !impact.eligible_draft) {
            setResults((old) => ({ ...old, [id]: t("ui.kb01.bulkProtected") }));
            continue;
          }
          const version = detail.versions.find((v) => v.knowledge_version_id === versions[id]);
          if (action !== "delete" && !version) throw new Error(t("ui.kb01.bulkChooseVersion"));
          prepared.push({ documentId: id,
            path: action === "delete" ? `/documents/${id}` : `/documents/versions/${version!.knowledge_version_id}/${action}`,
            method: action === "delete" ? "DELETE" : "POST",
            body: { expected_record_version: action === "delete" ? detail.record_version : version!.record_version,
              reason: reason.trim(), idempotency_key: idempotencyKey() },
          });
        }
        commands.current = prepared;
        setFrozen(true);
      }
      for (const command of commands.current) {
        if (completed.current.has(command.documentId)) continue;
        try {
          await client.mutate(command.path, command.body, command.method);
          completed.current.add(command.documentId);
          setResults((old) => ({ ...old, [command.documentId]: t("ui.kb01.bulkSuccess") }));
        } catch (e) {
          setResults((old) => ({ ...old, [command.documentId]: e instanceof Error ? e.message : String(e) }));
        }
      }
      onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { running.current = false; setBusy(false); }
  };
  return <section className="panel" aria-label={t("ui.kb01.bulkActions")}>
    <h3>{t("ui.kb01.bulkActions")}</h3>
    <p>{t("ui.kb01.bulkExplanation")}</p>
    <fieldset disabled={busy || frozen}>
      <legend>{t("ui.kb01.bulkSelection")}</legend>
      {documents.slice(0, 100).map((row) => <label key={row.document_id}>
        <input type="checkbox" data-bulk-document-id={row.document_id} checked={selected.includes(row.document_id)}
          onChange={(e) => { reset(); setSelected((old) => e.target.checked ? [...old, row.document_id] : old.filter((id) => id !== row.document_id)); }} />
        {row.display_name}
      </label>)}
      <label>{t("ui.kb01.bulkOperation")}<select value={action} onChange={(e) => { reset(); setAction(e.target.value as Action); }}>
        <option value="delete" disabled={!can("document:delete")}>{t("ui.kb01.deleteDraft")}</option>
        <option value="expire" disabled={!can("document:archive")}>{t("ui.kb01.action.expire")}</option>
        <option value="archive" disabled={!can("document:archive")}>{t("ui.kb01.action.archive")}</option>
      </select></label>
      <label>{t("ui.kb01.reason")}<input value={reason} maxLength={2048} onChange={(e) => setReason(e.target.value)} /></label>
    </fieldset>
    <button disabled={busy || !permitted || !selected.length} onClick={() => void preview()}>{t("ui.kb01.bulkPreview")}</button>
    <button disabled={busy} onClick={() => { reset(); setSelected([]); }}>{t("ui.kb01.bulkClear")}</button>
    {previews.map(({ detail, impact }) => <article key={detail.document_id} data-bulk-preview-id={detail.document_id}>
      <h4>{detail.display_name}</h4>
      <p>{detail.document_id}</p>
      <p>{t("ui.kb01.bulkReferences")}: {JSON.stringify(impact.references)}</p>
      {action === "delete" && !impact.eligible_draft && <p>{t("ui.kb01.bulkProtected")}</p>}
      {action !== "delete" && <label>{t("ui.kb01.bulkChooseVersion")}<select disabled={busy || frozen} value={versions[detail.document_id] ?? ""}
        onChange={(e) => setVersions((old) => ({ ...old, [detail.document_id]: e.target.value }))}>
        <option value="">{t("ui.kb01.bulkChooseVersion")}</option>
        {detail.versions.map((version) => <option key={version.knowledge_version_id} value={version.knowledge_version_id}>
          {version.version} · {version.lifecycle} · {version.knowledge_version_id}
        </option>)}
      </select></label>}
      <p role="status">{results[detail.document_id] ?? t("ui.kb01.bulkPending")}</p>
    </article>)}
    <button disabled={busy || !permitted || !previews.length || !reason.trim() || (action !== "delete" && previews.some(({ detail }) => !versions[detail.document_id]))}
      onClick={() => void execute()}>{t("ui.kb01.bulkConfirm")}</button>
    {error && <p role="alert">{error}</p>}
  </section>;
}
