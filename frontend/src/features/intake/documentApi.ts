import type { components } from '../../api/m2a-generated';
import { ApiError, request, uploadForm } from '../../api/client';
export type DocumentInputs = components['schemas']['DocumentInputsView'];
export type UploadPolicy = components['schemas']['DocumentUploadPolicyView'];
const base = (project: string) => `/api/v1/projects/${encodeURIComponent(project)}/intake`;
function scoped<T extends { project_id: string }>(project: string, value: T): T {
  if (value.project_id !== project) throw new ApiError(502, 'DOCUMENT_PROJECT_MISMATCH');
  return value;
}
export const documentApi = {
  list: async (project: string, signal?: AbortSignal) => scoped(project, await request<DocumentInputs>(`${base(project)}/documents`, { signal }, 'DocumentInputsView')),
  policy: async (project: string, signal?: AbortSignal) => scoped(project, await request<UploadPolicy>(`${base(project)}/documents/policy`, { signal }, 'DocumentUploadPolicyView')),
  upload: async (project: string, version: number, file: File, key: string, progress: (value: number) => void) => {
    const form = new FormData(); form.append('file', file); form.append('expected_version', String(version)); form.append('idempotency_key', key);
    return scoped(project, await uploadForm<DocumentInputs>(`${base(project)}/documents`, form, 'DocumentInputsView', progress));
  },
  action: async (project: string, version: number, key: string, action: 'parse' | 'unlink' | 'supersede', documentVersion?: string) => scoped(project, await request<DocumentInputs>(`${base(project)}/${action === 'supersede' ? action : `documents/${encodeURIComponent(documentVersion!)}/${action}`}`, { method: 'POST', body: JSON.stringify({ expected_version: version, idempotency_key: key }) }, 'DocumentInputsView')),
};
