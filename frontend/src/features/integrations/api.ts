import { request, validateContract, ApiError } from '../../api/client';
import type { components } from '../../api/m2e-generated';
import type { FetchPort } from '../admin/contracts';

type Schema = components['schemas'];
export type Client = Schema['ClientView'];
export type Subscription = Schema['WebhookView'];
export type Delivery = Schema['DeliveryView'];
export class IntegrationAdminClient {
  constructor(private transport: FetchPort = fetch) {}
  private call<T>(path: string, schema: string, method = 'GET', body?: unknown) {
    return request<T>(`/api/v1/admin/integration-clients${path}`, {
      method, ...(body === undefined ? {} : { body: JSON.stringify(body), headers: { 'Idempotency-Key': crypto.randomUUID() } }),
    }, schema, this.transport);
  }
  private async list<T>(path: string, schema: string) {
    const values = await request<unknown>(`/api/v1/admin/integration-clients${path}`, {}, undefined, this.transport);
    if (!Array.isArray(values)) throw new ApiError(502, 'API_CONTRACT_MISMATCH');
    return values.map(value => validateContract<T>(schema, value));
  }
  clients() { return this.list<Client>('', 'ClientView'); }
  options() { return this.call<Schema['IntegrationOptions']>('/options', 'IntegrationOptions'); }
  create(body: Schema['ClientCreate']) { return this.call<Schema['ClientCredentialView']>('', 'ClientCredentialView', 'POST', body); }
  update(client: Client, status: string, allowed_scopes = client.allowed_scopes) { return this.call<Client>(`/${client.client_id}`, 'ClientView', 'PATCH', { expected_version: client.record_version, status, allowed_scopes }); }
  rotate(client: Client) { return this.call<Schema['ClientCredentialView']>(`/${client.client_id}/rotate-credential`, 'ClientCredentialView', 'POST', { expected_version: client.record_version }); }
  bindings(id: string) { return this.list<Schema['ProjectBindingView']>(`/${id}/project-bindings`, 'ProjectBindingView'); }
  bind(client: Client, project_id: string, status = 'ACTIVE') { return this.call<Client>(`/${client.client_id}/project-binding`, 'ClientView', 'PUT', { expected_version: client.record_version, project_id, status }); }
  subscriptions(id: string) { return this.list<Subscription>(`/${id}/webhook-subscriptions`, 'WebhookView'); }
  createWebhook(id: string, body: Schema['WebhookCreate']) { return this.call<Schema['WebhookSecretView']>(`/${id}/webhook-subscriptions`, 'WebhookSecretView', 'POST', body); }
  updateWebhook(id: string, sub: Subscription, enabled: boolean) { return this.call<Subscription>(`/${id}/webhook-subscriptions/${sub.subscription_id}`, 'WebhookView', 'PATCH', { expected_version: sub.record_version, enabled }); }
  rotateWebhook(id: string, sub: Subscription) { return this.call<Schema['WebhookSecretView']>(`/${id}/webhook-subscriptions/${sub.subscription_id}/rotate-secret`, 'WebhookSecretView', 'POST', { expected_version: sub.record_version }); }
  testWebhook(id: string, sub: Subscription) { return request<Schema['DeliveryAccepted']>(`/api/v1/admin/integration-clients/${id}/webhook-subscriptions/${sub.subscription_id}/test`, { method: 'POST', body: '{}', headers: { 'Idempotency-Key': crypto.randomUUID() } }, 'DeliveryAccepted', this.transport); }
  deliveries(id: string, sub: Subscription) { return this.list<Delivery>(`/${id}/webhook-subscriptions/${sub.subscription_id}/deliveries`, 'DeliveryView'); }
}
