import { ApiError, request } from '../../api/client';
import type { components } from '../../api/m2c-generated';
export type Stage1Result = components['schemas']['Stage1ComplianceResult'];
export const stage1Read = async (runId: string, signal?: AbortSignal) => {
  const result = await request<Stage1Result>(`/api/v1/workflows/${encodeURIComponent(runId)}/stage1-result`, { signal }, 'Stage1ComplianceResult');
  if (result.workflow_run_id !== runId) throw new ApiError(404, 'RESULT_CONTEXT_MISMATCH');
  return result;
};
