import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { KnowledgeManagementClient, Schema } from "./client";

type Node = Schema<"TaxonomyTreeNode">;
type Props = {
  client: KnowledgeManagementClient;
  selected: string[];
  onSelect: (node: Node) => void;
  parent?: string;
};

// A nested list of disclosures keeps native keyboard controls. Each expanded
// level reads a bounded server page of the existing published hierarchy.
export function TaxonomyTree({ client, selected, onSelect, parent }: Props) {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Schema<"TaxonomyTreePage">>();
  const [expanded, setExpanded] = useState<string[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    const params = new URLSearchParams({
      kind: "JURISDICTION_CONFIG", locale: i18n.language,
      page: String(page), page_size: "25",
    });
    if (parent) params.set("parent_definition_id", parent);
    client.get<Schema<"TaxonomyTreePage">>(`/taxonomy-tree?${params}`, abort.signal)
      .then((result) => { setData(result); setError(""); })
      .catch((e) => { if (!abort.signal.aborted) { setData(undefined); setError(String(e)); } });
    return () => abort.abort();
  }, [client, parent, page, i18n.language]);
  return <>
    {error && <p role="alert">{error}</p>}
    <ul aria-busy={!data && !error}>
      {data?.items.map((node) => <li key={node.definition_id}>
        {node.child_count > 0 && <button type="button"
          aria-expanded={expanded.includes(node.definition_id)}
          aria-label={`${t("ui.kb01.expandHierarchy")} ${node.display_name}`}
          onClick={() => setExpanded((old) => old.includes(node.definition_id)
            ? old.filter((id) => id !== node.definition_id) : [...old, node.definition_id])}>
          {expanded.includes(node.definition_id) ? "−" : "+"}
        </button>}
        <button type="button" aria-pressed={selected.includes(node.definition_id)}
          onClick={() => onSelect(node)}>{node.display_name}</button>
        {expanded.includes(node.definition_id) && <TaxonomyTree
          client={client} selected={selected} onSelect={onSelect} parent={node.definition_id} />}
      </li>)}
    </ul>
    {data && data.total > data.page_size && <div>
      <button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>
        {t("ui.kb01.previous")}</button>
      <span>{page} / {Math.ceil(data.total / data.page_size)}</span>
      <button type="button" disabled={page * data.page_size >= data.total}
        onClick={() => setPage(page + 1)}>{t("ui.kb01.next")}</button>
    </div>}
  </>;
}
