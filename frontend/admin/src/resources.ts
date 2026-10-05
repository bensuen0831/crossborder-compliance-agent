import type { Action, AdminSession, Lifecycle, Operation, Resource } from './contracts';

const payload = { name: 'payload', label: 'Version metadata (JSON)', type: 'json' as const };
export const resources: readonly Resource[] = [
  { key: 'jurisdictions', label: 'Jurisdictions', group: 'Metadata', family: 'metadata', registry: 'jurisdictions', fields: [payload] },
  { key: 'scenarios', label: 'Business scenarios', group: 'Metadata', family: 'metadata', registry: 'scenarios', fields: [payload] },
  { key: 'products', label: 'Products', group: 'Metadata', family: 'metadata', registry: 'products', fields: [payload] },
  { key: 'knowledge-collections', label: 'Knowledge collections', group: 'Knowledge', family: 'metadata', fields: [payload] },
  { key: 'knowledge-versions', label: 'Knowledge operations', group: 'Knowledge', family: 'knowledge', fields: [] },
  { key: 'templates', label: 'Templates', group: 'Configuration', family: 'metadata', fields: [{ name: 'content_ref', label: 'Content reference', type: 'text' }, { name: 'field_schema', label: 'Field schema (JSON)', type: 'json' }] },
  { key: 'prompts', label: 'Prompts', group: 'Configuration', family: 'metadata', fields: [{ name: 'template_text', label: 'Prompt template', type: 'text' }, { name: 'capability_requirement', label: 'Capability requirements (JSON array)', type: 'json' }] },
  { key: 'models', label: 'Models', group: 'Configuration', family: 'metadata', fields: [payload] },
  ...[
    ['product-domains', 'Product domains / tags'], ['regulations', 'Regulation metadata'],
    ['country-config', 'Country configuration'], ['skills', 'Skills'], ['rules', 'Rules · Phase 1H'],
  ].map(([key, label]): Resource => ({ key, label, group: 'Integration boundaries', family: 'boundary', fields: [], gap: key === 'rules' ? 'Rule authoring awaits the Phase 1H Admin contract.' : 'No corresponding Admin endpoint is exposed in this base. See ADMIN_BACKEND_GAP.' })),
];

export const operationFor: Record<Action, Operation> = {
  validate: 'REVIEW', 'submit-review': 'REVIEW', approve: 'APPROVE', reject: 'APPROVE',
  publish: 'PUBLISH', supersede: 'PUBLISH', expire: 'PUBLISH', archive: 'ARCHIVE',
};
const backendScope = (resource: Resource, operation: Operation): string => {
  if (resource.family === 'knowledge') return 'knowledge:admin';
  if (operation === 'APPROVE') return 'metadata:review';
  if (operation === 'PUBLISH' || operation === 'ARCHIVE') return 'metadata:publish';
  return 'metadata:admin';
};
export function allowed(session: AdminSession, resource: Resource, operation: Operation): boolean {
  return resource.family !== 'boundary'
    && (session.grants[resource.key]?.includes(operation) ?? false)
    && session.backendScopes.includes(backendScope(resource, operation));
}
const metadataActions: Partial<Record<Lifecycle, readonly Action[]>> = {
  DRAFT: ['submit-review', 'archive'], PENDING_REVIEW: ['approve', 'reject'],
  APPROVED: ['publish', 'archive'], ACTIVE: ['supersede', 'archive'],
  SUPERSEDED: ['archive'], EXPIRED: ['archive'],
};
const knowledgeActions: Partial<Record<Lifecycle, readonly Action[]>> = {
  INGESTED: ['validate'], VALIDATED: ['submit-review'], PENDING_REVIEW: ['approve'],
  APPROVED: ['publish'], ACTIVE: ['supersede', 'expire'], EXPIRED: ['archive'],
};
export function actions(resource: Resource, status: Lifecycle): readonly Action[] {
  return (resource.family === 'knowledge' ? knowledgeActions : metadataActions)[status] ?? [];
}
