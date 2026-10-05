import type { Payload, RegistryItem } from './contracts';

export function parseObject(text: string): Payload {
  const value: unknown = JSON.parse(text);
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('Enter a JSON object.');
  return value as Payload;
}
export function itemId(item: RegistryItem): string {
  return String(item.definition_id ?? item.jurisdiction_id ?? item.metadata_definition_id ?? item.product_id ?? item.scenario_id ?? '');
}
export function itemLabel(item: RegistryItem): string { return String(item.display_name ?? item.code ?? itemId(item)); }
