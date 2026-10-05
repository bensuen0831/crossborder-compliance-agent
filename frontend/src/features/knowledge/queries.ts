import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { AuthorizedContext, RetrievalRequest, Session } from '../../api/contracts';

export function useScope(session: Session, context: AuthorizedContext | undefined) {
  return useQuery({
    queryKey: ['scope', session.identity_key, context],
    queryFn: ({ signal }) => api.scope(context!, signal), enabled: !!context,
    staleTime: 0, gcTime: 0, retry: false,
  });
}
export function useRetrieval(session: Session, context: AuthorizedContext | undefined, payload: RetrievalRequest | null) {
  return useQuery({
    queryKey: ['retrieval', session.identity_key, context, payload],
    queryFn: ({ signal }) => api.retrieve(context!, payload!, signal),
    enabled: !!context && !!payload, staleTime: 0, gcTime: 0, retry: false,
  });
}
