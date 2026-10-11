import { useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { request } from '../../api/client';
import type { components } from '../../api/m2a-generated';
import type { IntakeView } from './persistence';
type Preview = components['schemas']['CandidatePreview'];
type Decision = components['schemas']['CandidateDecisionInput'];
type Receipt = components['schemas']['CandidateDecisionReceipt'];
const base = (project: string) => `/api/v1/projects/${encodeURIComponent(project)}`;

export function useDocumentCandidates(record: IntakeView | undefined, identity: string, enabled: boolean) {
  const preview = useQuery({ queryKey: ['candidate-preview', identity, record?.project_id, record?.version], queryFn: ({ signal }) => request<Preview>(base(record!.project_id) + '/candidate-preview', { signal }, 'CandidatePreview'), enabled: enabled && record?.status === 'DRAFT', retry: false, gcTime: 0 });
  const key = useRef(crypto.randomUUID());
  const preparation = useMutation({ mutationFn: () => request<Preview>(base(record!.project_id) + '/candidate-preparation', { method: 'POST', body: JSON.stringify({ expected_version: record!.version, idempotency_key: key.current }) }, 'CandidatePreview'), onSuccess: async () => { await preview.refetch(); key.current = crypto.randomUUID(); }, retry: false });
  const decisionKey = useRef<{ payload: string; key: string } | undefined>(undefined);
  const resolution = useMutation({ mutationFn: (decisions: Decision[]) => {
    const payload = JSON.stringify({ version: record!.version, preparation: preview.data!.candidate_preparation_id, digest: preview.data!.candidate_universe_digest, decisions });
    if (decisionKey.current?.payload !== payload) decisionKey.current = { payload, key: crypto.randomUUID() };
    return request<Receipt>(base(record!.project_id) + '/candidate-decisions', { method: 'POST', body: JSON.stringify({ expected_version: record!.version, candidate_preparation_id: preview.data!.candidate_preparation_id, candidate_universe_digest: preview.data!.candidate_universe_digest, decisions, idempotency_key: decisionKey.current.key }) }, 'CandidateDecisionReceipt'); }, onSuccess: async () => { await preview.refetch(); decisionKey.current = undefined; }, retry: false });
  const blocked = !!preview.data && (preview.data.stale || preview.data.candidates.some(item => item.requires_confirmation && item.decision_status === 'UNRESOLVED'));
  return { preview, preparation, resolution, blocked, decisionSetId: preview.data?.candidate_decision_set_id ?? undefined };
}
