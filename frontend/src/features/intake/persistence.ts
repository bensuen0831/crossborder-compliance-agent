import type { components } from '../../api/m2a-generated';
import { ApiError, request } from '../../api/client';
import { emptyDraft, type Draft } from './contracts';

export type IntakeView = components['schemas']['IntakeView'];
export type IntakeFacts = components['schemas']['IntakeFacts'];
export interface IntakePersistence {
  record: IntakeView;
  save: (draft: Draft) => Promise<void>;
  confirm: () => Promise<IntakeView>;
}
export const intakeApi = {
  create: (name: string, analysis_as_of_date: string, key: string) => request<IntakeView>('/api/v1/projects', { method: 'POST', body: JSON.stringify({ name, idempotency_key: key, facts: { analysis_as_of_date } }) }, 'IntakeView'),
  read: async (id: string, signal?: AbortSignal) => {
    const result = await request<IntakeView>(`/api/v1/projects/${encodeURIComponent(id)}/intake`, { signal }, 'IntakeView');
    if (result.project_id !== id) throw new ApiError(502, 'INTAKE_IDENTITY_MISMATCH');
    return result;
  },
  save: (record: IntakeView, facts: IntakeFacts, key: string) => request<IntakeView>(`/api/v1/projects/${record.project_id}/intake`, { method: 'PUT', body: JSON.stringify({ expected_version: record.version, idempotency_key: key, facts }) }, 'IntakeView'),
  confirm: (record: IntakeView) => request<IntakeView>(`/api/v1/projects/${record.project_id}/intake/confirm`, { method: 'POST', body: JSON.stringify({ expected_version: record.version }) }, 'IntakeView'),
};
export function restoreDraft(record: IntakeView): Draft {
  const x = record.intake;
  return { ...emptyDraft(), scenario: x.business_scenario ?? '', product: x.selected_products?.[0] ?? '', source: x.source_locations ?? [], destination: x.destination_locations ?? [], processing: x.processing_locations ?? [], storage: x.storage_locations ?? [], categories: x.data_categories ?? [], organizations: x.organizations ?? [], thirdParties: x.third_parties ?? [], purpose: x.business_purpose ?? '', dataVolume: x.data_volume ?? '', flowDescription: x.data_flow_description ?? '', description: x.scenario_description ?? '', documents: (x.uploaded_documents ?? []).join('\n') };
}
export function draftFacts(record: IntakeView, draft: Draft): IntakeFacts {
  // Only canonical writable facts are submitted; policy/tenant/result/run refs
  // remain server-owned. Unsupported flow/data facts are not fabricated.
  return { industry: record.intake.industry, business_scenario: draft.scenario || null, selected_products: draft.product ? [draft.product] : [], selected_product_domains: record.intake.selected_product_domains, source_locations: draft.source, destination_locations: draft.destination, processing_locations: draft.processing, storage_locations: draft.storage, data_categories: draft.categories, business_purpose: draft.purpose, scenario_description: draft.description, data_flow_description: draft.flowDescription, data_volume: draft.dataVolume, organizations: draft.organizations, third_parties: draft.thirdParties, uploaded_documents: draft.documents.split('\n').map(x => x.trim()).filter(Boolean), requested_outputs: record.intake.requested_outputs, analysis_as_of_date: record.intake.analysis_as_of_date };
}
