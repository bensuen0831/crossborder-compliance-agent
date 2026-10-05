import type { Action, Draft, FetchPort, IngestionRun, KnowledgeVersion, Payload, RegistryResponse, RuntimeReadiness, Source, Version } from './contracts';

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
function version(row: Record<string, unknown>): Version {
  const id = row.version_id ?? row.metadata_version_id ?? row.jurisdiction_version_id;
  const definition = row.definition_id ?? row.metadata_definition_id ?? row.jurisdiction_id;
  if (typeof id !== 'string' || typeof definition !== 'string'
    || typeof row.record_version !== 'number' || typeof row.lifecycle_status !== 'string') {
    throw new ApiError(502, 'Unrecognized version response; refresh or contact the API owner.');
  }
  return { id, definitionId: definition, number: typeof row.version_no === 'number' ? row.version_no : null,
    lifecycle: row.lifecycle_status as Version['lifecycle'], recordVersion: row.record_version,
    payload: (row.payload ?? row.payload_json) as Payload | undefined };
}
export class AdminClient {
  constructor(private transport: FetchPort = fetch) {}
  async request<T>(path: string, method = 'GET', data?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await this.transport(`/api/v1${path}`, {
      method, credentials: 'same-origin', signal,
      headers: data === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    if (!response.ok) {
      // Do not reflect raw backend errors/configuration/secrets into the UI.
      const messages: Record<number, string> = {
        401: 'Sign in through the host application to continue.',
        403: 'The server denied this operation for your current context.',
        404: 'This record or API capability is unavailable in your context.',
        409: 'This version changed. Reload it before retrying; your edits are retained.',
        422: 'The API rejected the fields or lifecycle transition. Check the contract and current version.',
      };
      throw new ApiError(response.status, messages[response.status] ?? 'The service could not complete this operation.');
    }
    return response.json() as Promise<T>;
  }
  registry(key: string, signal?: AbortSignal) { return this.request<RegistryResponse>(`/metadata/${encodeURIComponent(key)}`, 'GET', undefined, signal); }
  async create(key: string, draft: Draft) { return version(await this.request<Record<string, unknown>>(`/admin/${encodeURIComponent(key)}`, 'POST', draft)); }
  async update(key: string, current: Version, payload: Payload) { return version(await this.request<Record<string, unknown>>(`/admin/${encodeURIComponent(key)}/${encodeURIComponent(current.id)}/draft`, 'PATCH', { payload, expected_record_version: current.recordVersion })); }
  async transition(key: string, current: Version, action: Action) { return version(await this.request<Record<string, unknown>>(`/admin/${encodeURIComponent(key)}/${encodeURIComponent(current.id)}/${action}`, 'POST', { expected_record_version: current.recordVersion })); }
  async history(key: string, definitionId: string) { const result = await this.request<{ items: Record<string, unknown>[] }>(`/admin/${encodeURIComponent(key)}/${encodeURIComponent(definitionId)}/versions`); return result.items.map(row => ({ ...version(row), definitionId })); }
  impact(key: string, definitionId: string) { return this.request<Payload>(`/admin/${encodeURIComponent(key)}/${encodeURIComponent(definitionId)}/impact-preview`); }
  source(payload: Payload) { return this.request<Source>('/admin/knowledge-sources', 'POST', payload); }
  getSource(id: string) { return this.request<Source & Payload>(`/admin/knowledge-sources/${encodeURIComponent(id)}`); }
  updateSource(id: string, recordVersion: number, payload: Payload) { return this.request<Source>(`/admin/knowledge-sources/${encodeURIComponent(id)}`, 'PATCH', { ...payload, expected_record_version: recordVersion }); }
  document(sourceId: string, displayName: string) { return this.request<{ document_id: string }>('/admin/knowledge-documents', 'POST', { source_id: sourceId, display_name: displayName }); }
  knowledgeVersion(documentId: string, payload: Payload) { return this.request<KnowledgeVersion>(`/admin/knowledge-documents/${encodeURIComponent(documentId)}/versions`, 'POST', payload); }
  getKnowledgeVersion(id: string) { return this.request<KnowledgeVersion>(`/admin/knowledge-versions/${encodeURIComponent(id)}`); }
  ingest(id: string, payload: Payload) { return this.request<IngestionRun>(`/admin/knowledge-versions/${encodeURIComponent(id)}/ingest`, 'POST', payload); }
  ingestionRun(id: string) { return this.request<IngestionRun>(`/admin/knowledge-ingestion-runs/${encodeURIComponent(id)}`); }
  knowledgeTransition(current: KnowledgeVersion, action: Action) { return this.request<KnowledgeVersion>(`/admin/knowledge-versions/${encodeURIComponent(current.knowledge_version_id)}/${action}`, 'POST', { expected_record_version: current.record_version }); }
  readiness(id: string, signal?: AbortSignal) { return this.request<RuntimeReadiness>(`/admin/knowledge-versions/${encodeURIComponent(id)}/runtime-readiness`, 'GET', undefined, signal); }
  bindings(id: string) { return this.request<Payload[]>(`/admin/knowledge-versions/${encodeURIComponent(id)}/bindings`); }
  quality(id: string) { return this.request<Payload[]>(`/admin/knowledge-versions/${encodeURIComponent(id)}/quality`); }
  retrieve(projectId: string, payload: Payload) { return this.request<Payload>(`/projects/${encodeURIComponent(projectId)}/knowledge/retrieve`, 'POST', payload); }
}
