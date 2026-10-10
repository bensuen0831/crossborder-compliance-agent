/** Versioned northbound transport only; the server owns every formal decision. */
import type { components } from './generated.js';
export type Schema = components['schemas'];
export type WorkflowEvent = Schema['ExternalWorkflowEvent'];
export class GatewayError extends Error {
  constructor(public status: number, public code: string, public traceId?: string, public retryable = false) { super(code); }
}
export class AgentClient {
  private token?: string;
  constructor(private baseUrl: string, private transport: typeof fetch = fetch) {}
  useServiceCredential(credential: string) { this.token = credential; }
  private async call<T>(path: string, method = 'GET', body?: unknown, key?: string): Promise<T> {
    const form = body instanceof FormData;
    const response = await this.transport(this.baseUrl.replace(/\/$/, '') + '/api/v1/external' + path, {
      method, headers: { Accept: 'application/json', ...(this.token ? { Authorization: 'Bearer ' + this.token } : {}),
        ...(key ? { 'Idempotency-Key': key } : {}), ...(!form && body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      ...(body === undefined ? {} : { body: form ? body : JSON.stringify(body) }),
    });
    if (!response.ok) {
      const failure = await response.json().catch(() => ({})) as Partial<Schema['GatewayError']>;
      throw new GatewayError(response.status, failure.error_code ?? 'GATEWAY_UNAVAILABLE', failure.trace_id, failure.retryable);
    }
    return response.json() as Promise<T>;
  }
  async authenticate(clientId: string, clientSecret: string, scope?: string): Promise<Schema['TokenView']> {
    const response = await this.transport(this.baseUrl.replace(/\/$/, '') + '/api/v1/external/oauth/token', {
      method: 'POST', body: new URLSearchParams({ grant_type: 'client_credentials', client_id: clientId, client_secret: clientSecret, ...(scope ? { scope } : {}) }),
    });
    if (!response.ok) throw new GatewayError(response.status, 'UNAUTHORIZED');
    const value = await response.json() as Schema['TokenView']; this.token = value.access_token; return value;
  }
  createProject(input: Schema['ExternalProjectCreate'], key: string) { return this.call<Schema['IntakeView']>('/projects', 'POST', input, key); }
  getIntake(project: string) { return this.call<Schema['IntakeView']>(`/projects/${encodeURIComponent(project)}/intake`); }
  updateIntake(project: string, input: Schema['ExternalIntakeUpdate'], key: string) { return this.call<Schema['IntakeView']>(`/projects/${encodeURIComponent(project)}/intake`, 'PUT', input, key); }
  uploadDocument(project: string, file: Blob, filename: string, expectedVersion: number, key: string) {
    const form = new FormData(); form.append('file', file, filename); form.append('expected_version', String(expectedVersion));
    return this.call<Schema['DocumentInputsView']>(`/projects/${encodeURIComponent(project)}/documents`, 'POST', form, key);
  }
  parseDocument(project: string, version: string, expectedVersion: number, key: string) { return this.call<Schema['DocumentInputsView']>(`/projects/${encodeURIComponent(project)}/documents/${encodeURIComponent(version)}/parse`, 'POST', { expected_version: expectedVersion }, key); }
  listEligibleModels(project: string) { return this.call<Schema['EligibleModelCatalog']>(`/projects/${encodeURIComponent(project)}/eligible-models`); }
  confirm(project: string, expectedVersion: number, key: string) { return this.call<Schema['IntakeView']>(`/projects/${encodeURIComponent(project)}/intake/confirm`, 'POST', { expected_version: expectedVersion }, key); }
  startAnalysis(project: string, snapshot: string, key: string) { return this.call<Schema['ExternalWorkflowAccepted']>(`/projects/${encodeURIComponent(project)}/snapshots/${encodeURIComponent(snapshot)}/workflow`, 'POST', {}, key); }
  getStatus(run: string) { return this.call<Schema['WorkflowView']>(`/workflows/${encodeURIComponent(run)}`); }
  getResult(run: string) { return this.call<Schema['Stage1ComplianceResult']>(`/workflows/${encodeURIComponent(run)}/stage1-result`); }
  subscribeWebhook(input: Schema['WebhookCreate'], key: string) { return this.call<Schema['WebhookSecretView']>('/webhook-subscriptions', 'POST', input, key); }
  async waitForCompletion(run: string, timeoutMs = 60000, intervalMs = 1000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const view = await this.getStatus(run); if (view.status !== 'RUNNING') return view;
      await new Promise(resolve => setTimeout(resolve, Math.min(intervalMs, Math.max(0, deadline - Date.now()))));
    }
    throw new GatewayError(408, 'POLL_TIMEOUT', undefined, true);
  }
  async *events(run: string, lastEventId?: string, signal?: AbortSignal): AsyncGenerator<WorkflowEvent> {
    const response = await this.transport(this.baseUrl.replace(/\/$/, '') + `/api/v1/external/workflows/${encodeURIComponent(run)}/events`, {
      signal, headers: { Accept: 'text/event-stream', Authorization: 'Bearer ' + (this.token ?? ''), ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}) },
    });
    if (!response.ok || !response.body) throw new GatewayError(response.status, 'EVENT_STREAM_DENIED');
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) return;
        buffer += decoder.decode(value, { stream: true });
        let index: number;
        while ((index = buffer.indexOf('\n\n')) >= 0) {
          const frame = buffer.slice(0, index); buffer = buffer.slice(index + 2);
          if (frame.length > 65536) throw new GatewayError(502, 'EVENT_PAYLOAD_TOO_LARGE');
          const data = frame.split('\n').filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n');
          if (data) yield JSON.parse(data) as WorkflowEvent;
        }
        if (buffer.length > 65536) throw new GatewayError(502, 'EVENT_PAYLOAD_TOO_LARGE');
      }
    } finally { await reader.cancel(); reader.releaseLock(); }
  }
}
