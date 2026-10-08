import type { components } from '../../api/m2d-generated';
import { ApiError, request } from '../../api/client';
export type Review = components['schemas']['ReviewView'];
export type ReviewPage = components['schemas']['ReviewPage'];
export type Decision = components['schemas']['ReviewDecisionRequest'];
export type Correction = components['schemas']['ReviewCorrectionRequest'];
export type Lineage = components['schemas']['ReviewLineage'];
export const reviewsApi = {
  list: (filters: URLSearchParams, signal?: AbortSignal) => request<ReviewPage>(`/api/v1/reviews?${filters}`, { signal }, 'ReviewPage'),
  read: async (id: string, signal?: AbortSignal) => {
    const result = await request<Review>(`/api/v1/reviews/${encodeURIComponent(id)}`, { signal }, 'ReviewView');
    if (result.review_id !== id) throw new ApiError(502, 'REVIEW_IDENTITY_MISMATCH');
    return result;
  },
  decide: (id: string, body: Decision) => request<Review>(`/api/v1/reviews/${encodeURIComponent(id)}/decisions`, { method: 'POST', body: JSON.stringify(body) }, 'ReviewView'),
  correct: (id: string, body: Correction) => request<Lineage>(`/api/v1/reviews/${encodeURIComponent(id)}/corrections`, { method: 'POST', body: JSON.stringify(body) }, 'ReviewLineage'),
  continueSuccessor: (id: string) => request<Review>(`/api/v1/reviews/${encodeURIComponent(id)}/successor/start`, { method: 'POST' }, 'ReviewView'),
  resume: (id: string) => request<Review>(`/api/v1/reviews/${encodeURIComponent(id)}/resume`, { method: 'POST' }, 'ReviewView'),
};
