import type { Action, AdminSession, Lifecycle, Operation, Resource } from './contracts';

const payload = { name: 'payload', label: "ui.metadataPayload", type: 'json' as const };
export const resources: readonly Resource[] = [
  { key: 'jurisdictions', label: "ui.jurisdictions", group: "ui.metadataGroup", family: 'metadata', registry: 'jurisdictions', fields: [payload] },
  { key: 'scenarios', label: "ui.scenarios", group: "ui.metadataGroup", family: 'metadata', registry: 'scenarios', fields: [payload] },
  { key: 'products', label: "ui.products", group: "ui.metadataGroup", family: 'metadata', registry: 'products', fields: [payload] },
  { key: 'knowledge-collections', label: "ui.collections", group: "ui.knowledgeGroup", family: 'metadata', fields: [payload] },
  { key: 'knowledge-versions', label: "ui.knowledgeOperations", group: "ui.knowledgeGroup", family: 'knowledge', fields: [] },
  { key: 'templates', label: "ui.templates", group: "ui.configurationGroup", family: 'metadata', fields: [{ name: 'content_ref', label: "ui.contentRef", type: 'text' }, { name: 'field_schema', label: "ui.fieldSchema", type: 'json' }] },
  { key: 'prompts', label: "ui.prompts", group: "ui.configurationGroup", family: 'metadata', fields: [{ name: 'template_text', label: "ui.promptTemplate", type: 'text' }, { name: 'capability_requirement', label: "ui.capabilityRequirements", type: 'json' }] },
  { key: 'models', label: "ui.phase1kb.providers", group: "ui.configurationGroup", family: 'metadata', fields: [payload] },
  { key: 'llm-provider-presets', label: "ui.phase1kb.presets", group: "ui.configurationGroup", family: 'metadata', registry: 'llm-provider-presets', fields: [payload] },
  { key: 'llm-invocation-policies', label: "ui.phase1kb.invocationPolicy", group: "ui.configurationGroup", family: 'metadata', registry: 'llm-invocation-policies', fields: [payload] },
  { key: 'model-usage-policies', label: "ui.phase1kb.usagePolicy", group: "ui.configurationGroup", family: 'metadata', registry: 'model-usage-policies', fields: [payload] },
  { key: 'rules', label: "ui.rules", group: "ui.configurationGroup", family: 'metadata', fields: [] },
  ...[
    ['product-domains', "ui.productDomains"], ['regulations', "ui.regulations"],
    ['country-config', "ui.countryConfig"], ['skills', "ui.skills"],
  ].map(([key, label]): Resource => ({ key, label, group: "ui.boundariesGroup", family: 'boundary', fields: [], gap: "ui.boundaryGap" })),
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
  DRAFT: ['submit-review', "archive"], PENDING_REVIEW: ['approve', "reject"],
  APPROVED: ['publish', "archive"], ACTIVE: ['supersede', "archive"],
  SUPERSEDED: ['archive'], EXPIRED: ['archive'],
};
const knowledgeActions: Partial<Record<Lifecycle, readonly Action[]>> = {
  INGESTED: ['validate'], VALIDATED: ['submit-review'], PENDING_REVIEW: ['approve'],
  APPROVED: ['publish'], ACTIVE: ['supersede', "expire"], EXPIRED: ['archive'],
};
export function actions(resource: Resource, status: Lifecycle): readonly Action[] {
  return (resource.family === 'knowledge' ? knowledgeActions : metadataActions)[status] ?? [];
}
