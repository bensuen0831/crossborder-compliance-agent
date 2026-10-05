import type { EvidenceItem, Metadata } from '../../api/contracts';

export function metadataLabel(id: string, metadata?: Metadata): string {
  const item = metadata?.items.find((row) => (row.definition_id ?? row.jurisdiction_id) === id);
  return item?.display_name ?? item?.name ?? item?.code ?? id;
}

// The canonical DTO has no document title; preserve its actual source locator.
export function evidenceTitle(item: EvidenceItem): string {
  return item.canonical_locator;
}

export function safeSourceUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : undefined;
  } catch { return undefined; }
}
