import { request } from '../../api/client';
import type { components } from '../../api/phase1kb-generated';
import type { FetchPort } from '../admin/contracts';

type Schema = components['schemas'];
export type Provider = Schema['ProviderView'];
export type ProviderVersion = Schema['ProviderVersionView'];
export type Model = Schema['ModelView'];
export type ProviderDraft = Schema['ProviderDraft'];
export type ModelDraft = Schema['ModelDraft'];
export type TestResult = Schema['ProviderTestResult'];
export type Transition = Schema['ControlTransition'];

export class ModelControlClient {
  constructor(private transport: FetchPort = fetch) {}
  private call<T>(path: string, schema: string, method = 'GET', body?: unknown, signal?: AbortSignal) {
    return request<T>(`/api/v1/admin/model-providers${path}`, {
      method, signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    }, schema, this.transport);
  }
  providers(signal?: AbortSignal) { return this.call<Schema['ProviderListView']>('', 'ProviderListView', 'GET', undefined, signal); }
  saveProvider(body: ProviderDraft) { return this.call<ProviderVersion>('', 'ProviderVersionView', 'POST', body); }
  transitionProvider(id: string, body: Transition) { return this.call<ProviderVersion>(`/versions/${encodeURIComponent(id)}/transition`, 'ProviderVersionView', 'POST', body); }
  providerEnabled(provider: Provider, enabled: boolean) { return this.call<Schema['EnabledView']>(`/${encodeURIComponent(provider.provider_id)}/enabled`, 'EnabledView', 'PUT', { enabled, expected_record_version: provider.record_version }); }
  testConnection(id: string) { return this.call<TestResult>(`/versions/${encodeURIComponent(id)}/test-connection`, 'ProviderTestResult', 'POST'); }
  discover(id: string) { return this.call<TestResult>(`/versions/${encodeURIComponent(id)}/discover-models`, 'ProviderTestResult', 'POST'); }
  models(id: string, signal?: AbortSignal) { return this.call<Schema['ModelListView']>(`/${encodeURIComponent(id)}/models`, 'ModelListView', 'GET', undefined, signal); }
  saveModel(id: string, body: ModelDraft) { return this.call<Model>(`/${encodeURIComponent(id)}/models`, 'ModelView', 'POST', body); }
  transitionModel(id: string, body: Transition) { return this.call<Model>(`/models/deployments/${encodeURIComponent(id)}/transition`, 'ModelView', 'POST', body); }
  modelEnabled(model: Model, enabled: boolean) { return this.call<Schema['EnabledView']>(`/models/${encodeURIComponent(model.model_id)}/enabled`, 'EnabledView', 'PUT', { enabled, expected_record_version: model.model_record_version }); }
  testModel(id: string, operation: 'chat' | 'structured_output' | 'embedding') { return this.call<TestResult>(`/models/deployments/${encodeURIComponent(id)}/test`, 'ProviderTestResult', 'POST', { operation }); }
  presets(signal?: AbortSignal) {
    return request<{ items: Array<{ display_name: string; code: string; payload?: { vendor_preset?: string } }> }>(
      '/api/v1/metadata/llm-provider-presets', { signal }, 'Metadata', this.transport);
  }
}
