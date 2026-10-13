import type { components } from '../../api/m2a-generated';
import { ApiError, request } from '../../api/client';
import { emptyDraft, type Draft } from './contracts';

export type IntakeView = components['schemas']['IntakeView'];
export type IntakeFacts = components['schemas']['IntakeFacts'];
export interface IntakePersistence {
  record: IntakeView;
  refresh?: () => Promise<void>;
  save: (draft: Draft) => Promise<void>;
  confirm: (decisionSetId?: string) => Promise<IntakeView>;
}
export const intakeApi = {
  create: (name: string, analysis_as_of_date: string, key: string) => request<IntakeView>('/api/v1/projects', { method: 'POST', body: JSON.stringify({ name, idempotency_key: key, facts: { analysis_as_of_date } }) }, 'IntakeView'),
  read: async (id: string, signal?: AbortSignal) => {
    const result = await request<IntakeView>(`/api/v1/projects/${encodeURIComponent(id)}/intake`, { signal }, 'IntakeView');
    if (result.project_id !== id) throw new ApiError(502, 'INTAKE_IDENTITY_MISMATCH');
    return result;
  },
  save: (record: IntakeView, facts: IntakeFacts, key: string) => request<IntakeView>(`/api/v1/projects/${record.project_id}/intake`, { method: 'PUT', body: JSON.stringify({ expected_version: record.version, idempotency_key: key, facts }) }, 'IntakeView'),
  confirm: (record: IntakeView, decisionSetId?: string) => request<IntakeView>(`/api/v1/projects/${record.project_id}/intake/confirm`, { method: 'POST', body: JSON.stringify({ expected_version: record.version, ...(decisionSetId ? { candidate_decision_set_id: decisionSetId } : {}) }) }, 'IntakeView'),
};
export function restoreDraft(record: IntakeView): Draft {
  const x = record.intake;
  return { ...emptyDraft(), flows: (x.data_flows ?? []).map(flow => ({ id: flow.input_key, data_item_id: '', data_item_canonical_name: flow.data_item_canonical_name, source_location: flow.source_jurisdiction_id, destination_location: flow.destination_jurisdiction_id, direction: flow.direction, source_name: flow.source_name, destination_name: flow.destination_name, source_party_id: flow.source_party_id, destination_party_id: flow.destination_party_id, source_system_id: flow.source_system_id, destination_system_id: flow.destination_system_id })), aiModelPreference: x.ai_model_preference, scenario: x.business_scenario ?? '', product: x.selected_products?.[0] ?? '', source: x.source_locations ?? [], destination: x.destination_locations ?? [], processing: x.processing_locations ?? [], storage: x.storage_locations ?? [], categories: x.data_categories ?? [], organizations: x.organizations ?? [], thirdParties: x.third_parties ?? [], purpose: x.business_purpose ?? '', dataVolume: x.data_volume ?? '', flowDescription: x.data_flow_description ?? '', description: x.scenario_description ?? '', documents: (x.uploaded_documents ?? []).join('\n') };
}
export function draftFacts(record: IntakeView, draft: Draft): IntakeFacts {
  // Only canonical writable facts are submitted; policy/tenant/result/run refs
  // remain server-owned. Typed flow inputs are explicit proposals, not formal IDs.
  return { data_flows: draft.flows.map(flow => ({ input_key: flow.id, data_item_canonical_name: flow.data_item_canonical_name ?? '', source_jurisdiction_id: flow.source_location, destination_jurisdiction_id: flow.destination_location, direction: flow.direction ?? 'SOURCE_TO_DESTINATION', source_name: flow.source_name ?? '', destination_name: flow.destination_name ?? '', source_party_id: flow.source_party_id ?? null, destination_party_id: flow.destination_party_id ?? null, source_system_id: flow.source_system_id ?? null, destination_system_id: flow.destination_system_id ?? null })), ai_model_preference: draft.aiModelPreference ?? record.intake.ai_model_preference, industry: record.intake.industry, business_scenario: draft.scenario || null, selected_products: draft.product ? [draft.product] : [], selected_product_domains: record.intake.selected_product_domains, source_locations: draft.source, destination_locations: draft.destination, processing_locations: draft.processing, storage_locations: draft.storage, data_categories: draft.categories, business_purpose: draft.purpose, scenario_description: draft.description, data_flow_description: draft.flowDescription, data_volume: draft.dataVolume, organizations: draft.organizations, third_parties: draft.thirdParties, uploaded_documents: record.intake.uploaded_documents, requested_outputs: record.intake.requested_outputs, analysis_as_of_date: record.intake.analysis_as_of_date };
}
