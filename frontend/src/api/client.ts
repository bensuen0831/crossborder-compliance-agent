import Ajv from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import openapi from './openapi.json';
import m1Schemas from './m1-schemas.json';
import m2aSchemas from './m2a-schemas.json';
import m2cSchemas from './m2c-schemas.json';
import m2dSchemas from './m2d-schemas.json';
import phase1kbSchemas from './phase1kb-schemas.json';
import type { AuthorizedContext, Health, Metadata, Readiness, RetrievalRequest, RetrievalResponse, Scope, Session } from './contracts';

export class ApiError extends Error {
  constructor(public status: number, message: string, public traceId?: string) {
    super(message);
  }
}

const ajv = new Ajv({ strict: false, allErrors: false });
addFormats(ajv);
const validators = new Map<string, ReturnType<typeof ajv.compile>>();
const presentationSchemas: Record<string, object> = {
  Session: {
    type: 'object', required: ['identity_key', 'display_name', 'tenant_label', 'organization_label', 'department_label', 'permissions', 'contexts', 'demo'],
    properties: {
      identity_key: { type: 'string', minLength: 1 }, display_name: { type: 'string' }, tenant_label: { type: 'string' },
      organization_label: { type: ['string', 'null'] }, department_label: { type: ['string', 'null'] },
      demo: { type: 'boolean' }, permissions: { type: 'array', items: { type: 'string' } },
      admin_context: {
        type: 'object', required: ['actorId', 'tenantId', 'roles', 'grants', 'backendScopes'],
        properties: {
          actorId: { type: 'string', minLength: 1 }, tenantId: { type: 'string', format: 'uuid' },
          ingestionAvailable: { type: 'boolean' },
          organizationId: { type: 'string' }, departmentId: { type: 'string' }, projectId: { type: 'string', format: 'uuid' },
          roles: { type: 'array', items: { type: 'string' } }, backendScopes: { type: 'array', items: { type: 'string' } },
          grants: { type: 'object', additionalProperties: { type: 'array', items: { enum: ['VIEW', 'EDIT', 'REVIEW', 'APPROVE', 'PUBLISH', 'ARCHIVE', 'DOWNLOAD', 'EXPORT', 'OPERATIONS'] } } },
        },
      },
      contexts: { type: 'array', items: { type: 'object', required: ['project_id', 'display_name', 'analysis_snapshot_id', 'policy_id'],
        properties: { project_id: { type: 'string', format: 'uuid' }, display_name: { type: 'string' }, analysis_snapshot_id: { type: 'string', format: 'uuid' }, policy_id: { type: 'string', format: 'uuid' } } } },
    },
  },
  Metadata: { type: 'object', required: ['items', 'registry_version', 'health'], properties: {
    items: { type: 'array', items: { type: 'object', properties: {
      definition_id: { type: 'string' }, jurisdiction_id: { type: 'string' }, display_name: { type: 'string' }, name: { type: 'string' }, code: { type: 'string' },
    } } }, registry_version: { type: 'string' }, health: { type: 'object', required: ['status'], properties: { status: { type: 'string' } } },
  } },
  Health: { type: 'object', required: ['status'], properties: { status: { type: 'string' }, app_env: { type: 'string' } } },
};
export function validateContract<T>(name: string, body: unknown): T {
  let validate = validators.get(name);
  if (!validate) {
    validate = ajv.compile(presentationSchemas[name] ?? { $ref: `#/components/schemas/${name}`, components: { schemas: { ...openapi.components.schemas, ...m1Schemas.components.schemas, ...m2aSchemas.components.schemas, ...m2cSchemas.components.schemas, ...m2dSchemas.components.schemas, ...phase1kbSchemas.components.schemas } } });
    validators.set(name, validate);
  }
  if (!validate(body)) throw new ApiError(502, 'API_CONTRACT_MISMATCH');
  return body as T;
}

const sessionPath = import.meta.env.VITE_SESSION_PATH ?? '/api/v1/session';
export const demoEnabled = import.meta.env.VITE_M0_DEMO === 'true';

export async function request<T>(path: string, options: RequestInit = {}, schema?: string, transport: typeof fetch = fetch): Promise<T> {
  let response: Response;
  try {
    response = await transport(path, { ...options, credentials: 'same-origin', headers: {
      Accept: 'application/json', ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    } });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'NETWORK_UNAVAILABLE');
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const data = body && typeof body === 'object' ? body as Record<string, unknown> : {};
    // Do not display serialized validation inputs, sensitive bodies or stack traces.
    const message = `HTTP_${response.status}`;
    const trace = typeof data.trace_id === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(data.trace_id) ? data.trace_id : undefined;
    throw new ApiError(response.status, message, trace);
  }
  return schema ? validateContract<T>(schema, body) : body as T;
}

export const api = {
  session: (signal?: AbortSignal) => request<Session>(sessionPath, { signal }, 'Session'),
  health: (signal?: AbortSignal) => request<Health>('/health/ready', { signal }, 'Health'),
  metadata: (resource: 'products' | 'scenarios' | 'jurisdictions', signal?: AbortSignal) =>
    request<Metadata>(`/api/v1/metadata/${resource}`, { signal }, 'Metadata'),
  scope: (context: AuthorizedContext, signal?: AbortSignal) => request<Scope>(
    `/api/v1/projects/${encodeURIComponent(context.project_id)}/knowledge-scope?analysis_snapshot_id=${encodeURIComponent(context.analysis_snapshot_id)}`,
    { signal }, 'KnowledgeScope'),
  retrieve: (context: AuthorizedContext, payload: RetrievalRequest, signal?: AbortSignal) => request<RetrievalResponse>(
    `/api/v1/projects/${encodeURIComponent(context.project_id)}/knowledge/retrieve`,
    { method: 'POST', body: JSON.stringify(payload), signal }, 'RetrievalResponseDTO'),
  readiness: (id: string, signal?: AbortSignal) => request<Readiness>(
    `/api/v1/admin/knowledge-versions/${encodeURIComponent(id)}/runtime-readiness`, { signal }, 'KnowledgeRuntimeReadinessResult'),
  demoLogin: (persona: 'A' | 'B' | 'PROJECT') => {
    if (!demoEnabled) return Promise.reject(new ApiError(403, 'DEMO_DISABLED'));
    return request<Session>('/m0-demo/login', { method: 'POST', body: JSON.stringify({ persona }) }, 'Session');
  },
  logout: () => request<{ status: string }>(demoEnabled ? '/m0-demo/logout' : '/api/v1/logout', { method: 'POST' }),
};

// Real multipart progress; share credentials, errors and runtime validators.
export function uploadForm<T>(path: string, form: FormData, schema: string, progress: (value: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', path); xhr.withCredentials = true;
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.upload.onprogress = event => { if (event.lengthComputable) progress(Math.round(event.loaded / event.total * 100)); };
    xhr.onerror = () => reject(new ApiError(0, 'NETWORK_UNAVAILABLE'));
    xhr.onabort = () => reject(new ApiError(0, 'NETWORK_UNAVAILABLE'));
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) { reject(new ApiError(xhr.status, `HTTP_${xhr.status}`)); return; }
      try { resolve(validateContract<T>(schema, JSON.parse(xhr.responseText))); }
      catch { reject(new ApiError(502, 'API_CONTRACT_MISMATCH')); }
    };
    xhr.send(form);
  });
}
