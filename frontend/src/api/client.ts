import Ajv from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import openapi from './openapi.json';
import type { AuthorizedContext, Health, Metadata, Readiness, RetrievalRequest, RetrievalResponse, Scope, Session } from './contracts';

export class ApiError extends Error {
  constructor(public status: number, message: string, public traceId?: string) {
    super(message);
  }
}

const ajv = new Ajv({ strict: false, allErrors: false });
addFormats(ajv);
const validators = new Map<string, ReturnType<typeof ajv.compile>>();
export function validateContract<T>(name: string, body: unknown): T {
  let validate = validators.get(name);
  if (!validate) {
    validate = ajv.compile({ $ref: `#/components/schemas/${name}`, components: openapi.components });
    validators.set(name, validate);
  }
  if (!validate(body)) throw new ApiError(502, 'API_CONTRACT_MISMATCH');
  return body as T;
}

const sessionPath = import.meta.env.VITE_SESSION_PATH ?? '/api/v1/session';
export const demoEnabled = import.meta.env.VITE_M0_DEMO === 'true';

async function request<T>(path: string, options: RequestInit = {}, schema?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { ...options, credentials: 'same-origin', headers: {
      Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    } });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'NETWORK_UNAVAILABLE');
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const data = body && typeof body === 'object' ? body as Record<string, unknown> : {};
    // Do not display serialized validation inputs, sensitive bodies or stack traces.
    const message = typeof data.message === 'string' ? data.message :
      typeof data.detail === 'string' ? data.detail : `HTTP_${response.status}`;
    throw new ApiError(response.status, message, typeof data.trace_id === 'string' ? data.trace_id : undefined);
  }
  return schema ? validateContract<T>(schema, body) : body as T;
}

export const api = {
  session: (signal?: AbortSignal) => request<Session>(sessionPath, { signal }),
  health: (signal?: AbortSignal) => request<Health>('/health/ready', { signal }),
  metadata: (resource: 'products' | 'scenarios' | 'jurisdictions', signal?: AbortSignal) =>
    request<Metadata>(`/api/v1/metadata/${resource}`, { signal }),
  scope: (context: AuthorizedContext, signal?: AbortSignal) => request<Scope>(
    `/api/v1/projects/${encodeURIComponent(context.project_id)}/knowledge-scope?analysis_snapshot_id=${encodeURIComponent(context.analysis_snapshot_id)}`,
    { signal }, 'KnowledgeScope'),
  retrieve: (context: AuthorizedContext, payload: RetrievalRequest, signal?: AbortSignal) => request<RetrievalResponse>(
    `/api/v1/projects/${encodeURIComponent(context.project_id)}/knowledge/retrieve`,
    { method: 'POST', body: JSON.stringify(payload), signal }, 'RetrievalResponseDTO'),
  readiness: (id: string, signal?: AbortSignal) => request<Readiness>(
    `/api/v1/admin/knowledge-versions/${encodeURIComponent(id)}/runtime-readiness`, { signal }, 'KnowledgeRuntimeReadinessResult'),
  demoLogin: (persona: 'A' | 'B') => {
    if (!demoEnabled) return Promise.reject(new ApiError(403, 'DEMO_DISABLED'));
    return request<Session>('/m0-demo/login', { method: 'POST', body: JSON.stringify({ persona }) });
  },
  logout: () => request<{ status: string }>(demoEnabled ? '/m0-demo/logout' : '/api/v1/logout', { method: 'POST' }),
};
