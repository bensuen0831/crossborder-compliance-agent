import { ApiError, request } from '../../api/client';
import type { AuthorizedContext, RetrievalResponse } from '../../api/contracts';
import type { Locale } from '../../i18n';
import type { Applicability, Classification, ContextItem, GovernedOption, Party, WorkflowView } from './contracts';
export const m1Api = {
  workflowStart: async (context: AuthorizedContext) => {
    const value = await request<WorkflowView>(`/api/v1/projects/${context.project_id}/snapshots/${context.analysis_snapshot_id}/workflow`, { method: 'POST', body: '{}' }, 'WorkflowView');
    if (value.project_id !== context.project_id || value.analysis_snapshot_id !== context.analysis_snapshot_id) throw new ApiError(404, 'RESULT_CONTEXT_MISMATCH');
    return value;
  },
  workflowRead: async (run: string) => {
    const value = await request<WorkflowView>(`/api/v1/workflows/${encodeURIComponent(run)}`, {}, 'WorkflowView');
    if (value.workflow_run_id !== run) throw new ApiError(404, 'RESULT_CONTEXT_MISMATCH');
    return value;
  },
  workflowEvidence: async (context: AuthorizedContext, run: string, signal?: AbortSignal) => {
    const value = await request<RetrievalResponse>(`/api/v1/retrieval-runs/${encodeURIComponent(run)}`, { signal }, 'RetrievalResponseDTO');
    if (!value.rag_context_pack || value.rag_context_pack.scope.project_id !== context.project_id || value.rag_context_pack.scope.analysis_snapshot_id !== context.analysis_snapshot_id) throw new ApiError(404, 'RESULT_CONTEXT_MISMATCH');
    return value;
  },
  metadata: (resource: string, locale: Locale, signal?: AbortSignal) => request<{ items: GovernedOption[] }>(`/api/v1/metadata/${encodeURIComponent(resource)}?locale=${locale}`, { signal }, 'Metadata'),
  items: (context: Pick<AuthorizedContext, 'project_id'>, signal?: AbortSignal) => request<ContextItem[]>(`/api/v1/projects/${context.project_id}/data-items`, { signal }),
  documents: (context: AuthorizedContext, signal?: AbortSignal) => request<Record<string, unknown>>(`/api/v1/projects/${context.project_id}/document-analysis-summary`, { signal }),
  parties: (context: Pick<AuthorizedContext, 'project_id'>, signal?: AbortSignal) => request<Party[]>(`/api/v1/projects/${context.project_id}/parties`, { signal }),
  context: (context: AuthorizedContext, signal?: AbortSignal) => request<Record<string, unknown>>(`/api/v1/projects/${context.project_id}/context-resolution`, { signal }),
  flows: (context: AuthorizedContext, signal?: AbortSignal) => request<Record<string, unknown>>(`/api/v1/projects/${context.project_id}/data-flows`, { signal }),
  results: async (context: AuthorizedContext, refs: { classification: string; applicability: string; retrieval: string }, signal?: AbortSignal) => {
    const [classification, applicability, retrieval] = await Promise.all([
      request<Classification>(`/api/v1/classifications/${encodeURIComponent(refs.classification)}`, { signal }, 'ClassificationResult'),
      request<Applicability>(`/api/v1/regulation-applicability/${encodeURIComponent(refs.applicability)}`, { signal }, 'RegulationApplicabilityResult'),
      request<RetrievalResponse>(`/api/v1/retrieval-runs/${encodeURIComponent(refs.retrieval)}`, { signal }, 'RetrievalResponseDTO'),
    ]);
    if (!retrieval.rag_context_pack || !classification.classification_result_id || !applicability.applicability_result_id) throw new ApiError(502, 'API_CONTRACT_MISMATCH');
    for (const result of [classification, applicability]) if (result.project_id !== context.project_id || result.analysis_snapshot_id !== context.analysis_snapshot_id) throw new ApiError(404, 'RESULT_CONTEXT_MISMATCH');
    if (retrieval.rag_context_pack.scope.project_id !== context.project_id || retrieval.rag_context_pack.scope.analysis_snapshot_id !== context.analysis_snapshot_id) throw new ApiError(404, 'RESULT_CONTEXT_MISMATCH');
    if (!applicability.classification_result_ids.includes(classification.classification_result_id) || !applicability.evidence_pack_ids.includes(retrieval.rag_context_pack.evidence_pack.evidence_pack_id)) throw new ApiError(404, 'RESULT_REFERENCE_MISMATCH');
    return { classification, applicability, retrieval: { ...retrieval, rag_context_pack: retrieval.rag_context_pack } };
  },
};
